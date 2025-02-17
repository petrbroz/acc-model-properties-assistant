import json
import httpx

class ModelPropertiesClient:
    def __init__(self, access_token: str, host: str = "https://developer.api.autodesk.com"):
        self.client = httpx.AsyncClient()
        self.access_token = access_token
        self.host = host

    def _build_url(self, project_id: str, subpath: str) -> str:
        return f"{self.host}/construction/index/v2/projects/{project_id[2:]}/indexes{subpath}"

    async def _get_json(self, url: str) -> dict:
        response = await self.client.get(url, headers={"Authorization": f"Bearer {self.access_token}"})
        if response.status_code >= 400:
            raise Exception(response.json())
        return response.json()

    async def _get_ldjson(self, url: str) -> list[dict]:
        response = await self.client.get(url, headers={"Authorization": f"Bearer {self.access_token}"})
        if response.status_code >= 400:
            raise Exception(response.json())
        return [json.loads(line) for line in response.text.splitlines()]

    async def _post_json(self, url: str, json: dict) -> dict:
        response = await self.client.post(url, json=json, headers={"Authorization": f"Bearer {self.access_token}"})
        if response.status_code >= 400:
            raise Exception(response.json())
        return response.json()

    async def create_indexes(self, project_id: str, payload: dict) -> dict:
        return await self._post_json(self._build_url(project_id, ":batch-status"), payload)

    async def get_index(self, project_id: str, index_id: str) -> dict:
        return await self._get_json(self._build_url(project_id, f"/{index_id}"))

    async def get_index_fields(self, project_id: str, index_id: str) -> list[dict]:
        index = await self.get_index(project_id, index_id)
        return await self._get_ldjson(index["fieldsUrl"])

    async def get_index_properties(self, project_id: str, index_id: str) -> list[dict]:
        index = await self.get_index(project_id, index_id)
        return await self._get_ldjson(index["propertiesUrl"])

    async def create_query(self, project_id: str, index_id: str, payload: dict) -> dict:
        return await self._post_json(self._build_url(project_id, f"/{index_id}/queries"), payload)

    async def get_query(self, project_id: str, index_id: str, query_id: str) -> dict:
        return await self._get_json(self._build_url(project_id, f"/{index_id}/queries/{query_id}"))

    async def get_query_fields(self, project_id: str, index_id: str, query_id: str) -> list[dict]:
        query = await self.get_query(project_id, index_id, query_id)
        return await self._get_ldjson(query["fieldsUrl"])

    async def get_query_properties(self, project_id: str, index_id: str, query_id: str) -> list[dict]:
        query = await self.get_query(project_id, index_id, query_id)
        return await self._get_ldjson(query["propertiesUrl"])

    async def get_query_results(self, project_id: str, index_id: str, query_id: str) -> list[dict]:
        query = await self.get_query(project_id, index_id, query_id)
        return await self._get_ldjson(query["queryResultsUrl"])