import os
import uvicorn
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from langchain_openai import ChatOpenAI
from aps import DataManagementClient
from agent import create_agent

app = FastAPI()

def check_access(request: Request):
    authorization = request.headers.get("authorization")
    if not authorization:
        raise HTTPException(status_code=401)
    return authorization.replace("Bearer ", "")

@app.get("/hubs")
async def get_hubs(access_token: str = Depends(check_access)) -> dict:
    data_management_client = DataManagementClient(access_token)
    return await data_management_client.get_hubs()

@app.get("/hubs/{hub_id}/projects")
async def get_projects(hub_id: str, access_token: str = Depends(check_access)) -> dict:
    data_management_client = DataManagementClient(access_token)
    return await data_management_client.get_projects(hub_id)

@app.get("/hubs/{hub_id}/projects/{project_id}/contents")
async def get_folder_contents(hub_id: str, project_id: str, folder_id: str | None = None, access_token: str = Depends(check_access)) -> dict:
    data_management_client = DataManagementClient(access_token)
    if folder_id is None:
        return await data_management_client.get_project_folders(hub_id, project_id)
    else:
        return await data_management_client.get_folder_contents(project_id, folder_id)

model = ChatOpenAI(model="gpt-4o")
agents = {} # Cache agents by URN

class PromptPayload(BaseModel):
    project_id: str
    version_id: str
    prompt: str

@app.post("/chatbot/prompt")
async def chatbot_prompt(payload: PromptPayload, access_token: str = Depends(check_access)) -> dict:
    data_management_client = DataManagementClient(access_token)
    response = await data_management_client.get_version(payload.project_id, payload.version_id)
    version = response["data"]
    urn = version["relationships"]["derivatives"]["data"]["id"]
    cache_folder = f"__cache__/{urn}"
    os.makedirs(cache_folder, exist_ok=True)
    if urn not in agents:
        agents[urn] = create_agent(model, payload.project_id, payload.version_id, access_token)
    agent = agents[urn]
    config = {"configurable": {"thread_id": urn}}
    responses = []
    with open(f"{cache_folder}/logs.txt", "a") as log:
        log.write(f"[{datetime.now().isoformat()}] User: {payload.prompt}\n\n")
        async for step in agent.astream({"messages": [("human", payload.prompt)]}, config, stream_mode="updates"):
            log.write(f"[{datetime.now().isoformat()}] Assistant: {step}\n\n")
            if "agent" in step:
                for message in step["agent"]["messages"]:
                    if isinstance(message.content, str) and message.content:
                        responses.append(message.content)
    return { "responses": responses }

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)