import os
import base64
import uvicorn
from typing import Dict
from pydantic import BaseModel
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from agents import create_model_props_agent, Agent

cache_dir = "__cache__"
app = FastAPI()
agents: Dict[str, Agent] = dict() # Cache agents by URN

def _check_access(request: Request):
    authorization = request.headers.get("authorization")
    if not authorization:
        raise HTTPException(status_code=401)
    return authorization.replace("Bearer ", "")

class PromptPayload(BaseModel):
    project_id: str
    version_id: str
    prompt: str

@app.post("/chatbot/prompt")
async def chatbot_prompt(payload: PromptPayload, access_token: str = Depends(_check_access)) -> dict:
    urn = base64.b64encode(payload.version_id.encode()).decode().replace("/", "_").replace("=", "")
    cache_urn_dir = os.path.join(cache_dir, urn)
    os.makedirs(cache_urn_dir, exist_ok=True)
    if not urn in agents:
        agents[urn] = await create_model_props_agent(payload.project_id, payload.version_id, access_token, cache_urn_dir)
    agent = agents[urn]
    responses = await agent.prompt(payload.prompt)
    return { "responses": responses }

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)