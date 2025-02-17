import asyncio
import json
import jq
from typing import Annotated
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from aps.acc import ModelPropertiesClient

FILTER_CATEGORIES = ["__name__", "__category__", "Dimensions", "Materials and Finishes"]
MAX_RESULTS = 256

def create_agent(model, project_id, version_id, access_token):
    client = ModelPropertiesClient(access_token)

    # Define tools for the agent (assuming that the index is already available)

    @tool
    async def create_index(
        design_id: Annotated[str, "The ID of the design to build the index for."]
    ) -> str:
        """Builds an index of design elements, property fields, and property values for given design ID. Returns the ID of the created index."""
        payload = {"versions": [{ "versionUrn": design_id }]}
        result = await client.create_indexes(project_id, payload)
        index = result["indexes"][0]
        index_id = index["indexId"]
        while index["state"] == "PROCESSING":
            await asyncio.sleep(1)
            index = await client.get_index(project_id, index_id)
        if index["state"] == "FINISHED":
            return index_id
        else:
            raise Exception(f"Index creation failed with errors: {index["errors"]}")

    @tool
    async def list_index_fields(
        index_id: Annotated[str, "The ID of the index to list fields for."]
    ) -> dict:
        """Lists names of property fields in an index of given ID. Returns a JSON with field categories, names, and their corresponding IDs."""
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
        return categories

    @tool
    async def query_index(
        index_id: Annotated[str, "The ID of the index to query."],
        query_str: Annotated[str, "The Model Property Service Query Language query."],
    ) -> list[dict]:
        """Queries an index of the given ID with a Model Property Service Query Language query. Returns a JSON list with properties of matching design elements."""
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

    @tool
    def execute_jq_query(
        jq_query: Annotated[str, "The jq query to execute. For example: \".[] | .Width\""],
        input_json: Annotated[str, "The JSON input to process with the jq query."]
    ):
        """Processes the given JSON input with the given jq query, and returns the result as a JSON."""
        return jq.compile(jq_query).input_text(input_json).all()

    # Create the agent

    tools = [create_index, list_index_fields, query_index, execute_jq_query]
    system_prompt = [
        "You are an AI assistant providing data analytics for designs hosted in Autodesk Construction Cloud.",
        "You use the Model Properties Query Language and API to retrieve relevant information from individual designs.",
        "When asked about a (Revit) category of elements, look for the property called \"_RC\"",
        "When asked about a (Revit) family type of elements, look for the property called \"_RFT\"",
        "When asked about a name of an element, look for the property called \"__name__\"",
    ]
    with open("MPQL.md", "r") as file:
        guide = file.read()
        guide = guide.replace("{", "{{").replace("}", "}}")
        system_prompt.append(guide)
    system_prompt.append(f"The design ID is \"{version_id}\"")
    prompt_template = ChatPromptTemplate.from_messages([("system", system_prompt), ("placeholder", "{messages}")])
    memory = MemorySaver()
    return create_react_agent(model, tools, prompt=prompt_template, checkpointer=memory)