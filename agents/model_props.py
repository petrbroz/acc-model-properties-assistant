import os
import asyncio
import json
import jq
from datetime import datetime
from typing import Annotated
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from aps.acc import ModelPropertiesClient

_llm = ChatOpenAI(model="gpt-4o")
_filter_categories = ["__name__", "__category__", "Dimensions", "Materials and Finishes"]
_max_results = 256

def _load_content(relative_path: str) -> str:
    with open(os.path.join(os.path.dirname(__file__), relative_path)) as f:
        return f.read()

async def _create_index(project_id: str, design_id: str, access_token: str, cache_urn_dir: str):
    client = ModelPropertiesClient(access_token)
    index_path = os.path.join(cache_urn_dir, "index.json")
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

async def _list_index_properties(project_id: str, index_id: str, access_token: str, cache_urn_dir: str):
    client = ModelPropertiesClient(access_token)
    fields_path = os.path.join(cache_urn_dir, "fields.json")
    if not os.path.exists(fields_path):
        fields = await client.get_index_fields(project_id, index_id)
        categories = {}
        for field in fields:
            category = field["category"]
            if category not in _filter_categories: # Filter out irrelevant categories
                continue
            name = field["name"]
            key = field["key"]
            if category not in categories:
                categories[category] = {}
            categories[category][name] = key
        with open(fields_path, "w") as f: json.dump(categories, f)
    with open(fields_path) as f:
        return json.load(f)

async def _query_index(project_id: str, index_id: str, query_str: str, access_token: str, cache_urn_dir: str):
    client = ModelPropertiesClient(access_token)
    payload = json.loads(query_str)
    query = await client.create_query(project_id, index_id, payload)
    while query["state"] == "PROCESSING":
        await asyncio.sleep(1)
        query = await client.get_query(project_id, index_id, query["queryId"])
    if query["state"] == "FINISHED":
        results = await client.get_query_results(project_id, index_id, query["queryId"])
        if len(results) > _max_results:
            raise Exception(f"Query returned too many results ({len(results)}), please refine the query.")
        else:
            return results
    else:
        raise Exception(f"Query failed with errors: {query["errors"]}")

class ModelPropertiesAgent:
    def __init__(self, project_id: str, version_id: str, access_token: str, cache_urn_dir: str):
        @tool
        async def create_index(
            design_id: Annotated[str, "The ID of the input design file hosted in Autodesk Construction Cloud."]
        ) -> str:
            """Builds a **Model Properties index** for a given design ID, including all available properties, and property values for individual design elements. Returns the ID of the created index."""
            return await _create_index(project_id, design_id, access_token, cache_urn_dir)

        @tool
        async def list_index_properties(
            index_id: Annotated[str, "The ID of the **Model Properties index** to list the available properties for."]
        ) -> dict:
            """Lists available properties for a **Model Properties index** of given ID. Returns a JSON with property categories, names, and keys."""
            return await _list_index_properties(project_id, index_id, access_token, cache_urn_dir)

        @tool
        async def query_index(
            index_id: Annotated[str, "The ID of the **Model Properties index** to query."],
            query_str: Annotated[str, "The Model Property Service Query Language query."],
        ) -> list[dict]:
            """Queries a **Model Properties index** of the given ID with a Model Property Service Query Language query. Returns a JSON list with properties of matching design elements."""
            return await _query_index(project_id, index_id, query_str, access_token, cache_urn_dir)

        @tool
        def execute_jq_query(
            jq_query: Annotated[str, "The jq query to execute. For example: \".[] | .Width\""],
            input_json: Annotated[str, "The JSON input to process with the jq query."]
        ):
            """Processes the given JSON input with the given jq query, and returns the result as a JSON."""
            return jq.compile(jq_query).input_text(input_json).all()

        tools = [create_index, list_index_properties, query_index, execute_jq_query]
        system_prompts = [
            _load_content("SYSTEM_PROMPTS.md").replace("{", "{{").replace("}", "}}"),
            _load_content("MPQL.md").replace("{", "{{").replace("}", "}}"),
            f"Unless specified otherwise, you are working with design ID \"{version_id}\""
        ]
        prompt_template = ChatPromptTemplate.from_messages([("system", system_prompts), ("placeholder", "{messages}")])
        self._agent = create_react_agent(_llm, tools, prompt=prompt_template, checkpointer=MemorySaver())
        self._config = {"configurable": {"thread_id": version_id}}
        self._logs_path = os.path.join(cache_urn_dir, "logs.txt")

    def _log(self, message: str):
        with open(self._logs_path, "a") as log:
            log.write(f"[{datetime.now().isoformat()}] {message}\n\n")

    async def prompt(self, prompt: str) -> list[str]:
        self._log(f"User: {prompt}")
        responses = []
        async for step in self._agent.astream({"messages": [("human", prompt)]}, self._config, stream_mode="updates"):
            self._log(f"Assistant: {step}")
            if "agent" in step:
                for message in step["agent"]["messages"]:
                    if isinstance(message.content, str) and message.content:
                        responses.append(message.content)
        return responses