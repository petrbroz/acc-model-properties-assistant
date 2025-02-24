import os
import asyncio
import json
import jq
from datetime import datetime
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool, BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from typing import Annotated
from aps.acc import ModelPropertiesClient

with open(os.path.join(os.path.dirname(__file__), "SYSTEM_PROMPTS.md")) as f:
    SYSTEM_PROMPTS = f.read().replace("{", "{{").replace("}", "}}")
with open(os.path.join(os.path.dirname(__file__), "MPQL.md")) as f:
    MPQL = f.read().replace("{", "{{").replace("}", "}}")
FILTER_CATEGORIES = ["__name__", "__category__", "Dimensions", "Materials and Finishes"]
MAX_RESULTS = 256

class Agent:
    def __init__(self, llm: BaseChatModel, prompt_template: ChatPromptTemplate, tools: list[BaseTool], cache_urn_dir: str):
        self._agent = create_react_agent(llm, tools, prompt=prompt_template, checkpointer=MemorySaver())
        self._config = {"configurable": {"thread_id": os.path.basename(cache_urn_dir)}}
        self._logs_path = os.path.join(cache_urn_dir, "logs.txt")

    def _log(self, message: str):
        with open(self._logs_path, "a") as log:
            log.write(f"[{datetime.now().isoformat()}] {message}\n\n")

    async def prompt(self, prompt: str) -> list[str]:
        self._log(f"User: {prompt}")
        responses = []
        async for step in self._agent.astream({"messages": [("human", prompt)]}, config=self._config, stream_mode="updates"):
            if "agent" in step:
                for message in step["agent"]["messages"]:
                    self._log(message.pretty_repr())
                    if isinstance(message.content, str) and message.content:
                        responses.append(message.content)
            if "tools" in step:
                for message in step["tools"]["messages"]:
                    self._log(message.pretty_repr())
        return responses

async def _create_index(project_id: str, design_id: str, access_token: str, cache_dir: str):
    client = ModelPropertiesClient(access_token)
    index_path = os.path.join(cache_dir, "index.json")
    if not os.path.exists(index_path):
        payload = {"versions": [{ "versionUrn": design_id }]}
        result = await client.create_indexes(project_id, payload)
        index = result["indexes"][0]
        index_id = index["indexId"]
        while index["state"] == "PROCESSING":
            await asyncio.sleep(1)
            index = await client.get_index(project_id, index_id)
        with open(index_path, "w") as f: json.dump(index, f)
    with open(index_path) as f:
        index = json.load(f)
        if "errors" in index:
            raise Exception(f"Index creation failed with errors: {index["errors"]}")
        return index["indexId"]

async def _list_index_properties(project_id: str, index_id: str, access_token: str, cache_dir: str):
    client = ModelPropertiesClient(access_token)
    fields_path = os.path.join(cache_dir, "fields.json")
    if not os.path.exists(fields_path):
        fields = await client.get_index_fields(project_id, index_id)
        categories = {}
        for field in fields:
            category = field["category"]
            if category not in FILTER_CATEGORIES: # Filter out irrelevant categories
                continue
            name = field["name"]
            key = field["key"]
            if category not in categories:
                categories[category] = {}
            categories[category][name] = key
        with open(fields_path, "w") as f: json.dump(categories, f)
    with open(fields_path) as f:
        return json.load(f)

async def _query_index(project_id: str, index_id: str, query_str: str, access_token: str, cache_dir: str):
    client = ModelPropertiesClient(access_token)
    payload = json.loads(query_str)
    query = await client.create_query(project_id, index_id, payload)
    while query["state"] == "PROCESSING":
        await asyncio.sleep(1)
        query = await client.get_query(project_id, index_id, query["queryId"])
    if query["state"] == "FINISHED":
        results = await client.get_query_results(project_id, index_id, query["queryId"])
        if len(results) > MAX_RESULTS:
            raise Exception(f"Query returned too many results ({len(results)}), please refine the query.")
        else:
            return results
    else:
        raise Exception(f"Query failed with errors: {query["errors"]}")

async def create_model_props_agent(project_id: str, version_id: str, access_token: str, cache_dir: str):
    @tool
    async def create_index(
        design_id: Annotated[str, "The ID of the input design file hosted in Autodesk Construction Cloud."]
    ) -> str:
        """Builds a **Model Properties index** for a given design ID, including all available properties, and property values for individual design elements. Returns the ID of the created index."""
        return await _create_index(project_id, design_id, access_token, cache_dir)

    @tool
    async def list_index_properties(
        index_id: Annotated[str, "The ID of the **Model Properties index** to list the available properties for."]
    ) -> dict:
        """Lists available properties for a **Model Properties index** of given ID. Returns a JSON with property categories, names, and keys."""
        return await _list_index_properties(project_id, index_id, access_token, cache_dir)

    @tool
    async def query_index(
        index_id: Annotated[str, "The ID of the **Model Properties index** to query."],
        query_str: Annotated[str, "The Model Property Service Query Language query."],
    ) -> list[dict]:
        """Queries a **Model Properties index** of the given ID with a Model Property Service Query Language query. Returns a JSON list with properties of matching design elements."""
        return await _query_index(project_id, index_id, query_str, access_token, cache_dir)

    @tool
    def execute_jq_query(
        jq_query: Annotated[str, "The jq query to execute. For example: \".[] | .Width\""],
        input_json: Annotated[str, "The JSON input to process with the jq query."]
    ):
        """Processes the given JSON input with the given jq query, and returns the result as a JSON."""
        return jq.compile(jq_query).input_text(input_json).all()

    llm = ChatOpenAI(model="gpt-4o")
    tools = [create_index, list_index_properties, query_index, execute_jq_query]
    system_prompts = [
        SYSTEM_PROMPTS,
        MPQL,
        f"Unless specified otherwise, you are working with design ID \"{version_id}\""
    ]
    prompt_template = ChatPromptTemplate.from_messages([("system", system_prompts), ("placeholder", "{messages}")])
    return Agent(llm, prompt_template, tools, cache_dir)
