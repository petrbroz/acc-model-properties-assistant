import httpx
from urllib.parse import quote

class DataManagementClient:
    def __init__(self, access_token: str, host: str = "https://developer.api.autodesk.com"):
        self.client = httpx.AsyncClient()
        self.access_token = access_token
        self.host = host

    async def _get_json(self, url: str):
        response = await self.client.get(url, headers={"Authorization": f"Bearer {self.access_token}"})
        if response.status_code >= 400:
            raise Exception(response.text)
        return response.json()

    async def get_hubs(self) -> list[dict]:
        return await self._get_json(f"{self.host}/project/v1/hubs")

    async def get_projects(self, hub_id: str) -> list[dict]:
        return await self._get_json(f"{self.host}/project/v1/hubs/{hub_id}/projects")

    async def get_project_folders(self, hub_id: str, project_id: str) -> list[dict]:
        return await self._get_json(f"{self.host}/project/v1/hubs/{hub_id}/projects/{project_id}/topFolders")

    async def get_folder_contents(self, project_id: str, folder_id: str) -> list[dict]:
        return await self._get_json(f"{self.host}/data/v1/projects/{project_id}/folders/{folder_id}/contents")

    async def get_item_versions(self, project_id: str, item_id: str) -> list[dict]:
        return await self._get_json(f"{self.host}/data/v1/projects/{project_id}/items/{item_id}/versions")

    async def get_version(self, project_id: str, version_id: str) -> dict:
        return await self._get_json(f"{self.host}/data/v1/projects/{project_id}/versions/{quote(version_id, safe='')}")