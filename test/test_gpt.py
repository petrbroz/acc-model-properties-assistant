import os
from datetime import datetime
from langchain_openai import ChatOpenAI
from agent import create_agent
import asyncio

async def main(project_id, version_id, access_token):
    model = ChatOpenAI(model="gpt-4o")
    agent = create_agent(model, project_id, version_id, access_token)
    config = {"configurable": {"thread_id": "test-thread"}}
    log_filename = datetime.now().strftime("test_gpt_%Y-%m-%dT%H-%M-%S.log")
    with open(log_filename, "a") as log:
        while True:
            query = input("Enter your query (or press Enter to exit): ")
            if not query:
                break
            log.write(f"User: {query}\n\n")
            print()
            async for step in agent.astream({"messages": [("human", query)]}, config, stream_mode="updates"):
                log.write(f"Assistant: {step}\n\n")
                if "agent" in step:
                    for message in step["agent"]["messages"]:
                        if isinstance(message.content, str) and message.content:
                            print(message.content, end="\n\n")
            log.flush()

if __name__ == "__main__":
    PROJECT_ID = os.getenv("PROJECT_ID")
    VERSION_ID = os.getenv("VERSION_ID")
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
    if not all([PROJECT_ID, VERSION_ID, ACCESS_TOKEN]):
        raise ValueError("Please set PROJECT_ID, VERSION_ID, and ACCESS_TOKEN environment variables")
    asyncio.run(main(PROJECT_ID, VERSION_ID, ACCESS_TOKEN))