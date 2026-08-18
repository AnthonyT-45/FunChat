import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from websockets.asyncio.client import connect

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
BROADCASTER_ID = os.getenv("BROADCASTER_ID")
REWARD_ID = os.getenv("REWARD_ID")

websocket_url = "wss://eventsub.wss.twitch.tv/ws"
html_path = "index.html"

message_queue = asyncio.Queue()
connections: set[WebSocket] = set()

headers = {
    "Client-Id": f"{CLIENT_ID}",
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json",
}

# logger config
FORMAT = "%(asctime)s %(message)s"

logger = logging.getLogger(__name__)
logging.basicConfig(format=FORMAT, level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    poller = asyncio.create_task(main())
    fanout = asyncio.create_task(broadcaster())
    yield
    poller.cancel()
    fanout.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


async def fun_chat():

    logger.info("Fun Chat executed")
    try:
        async with asyncio.timeout(300):
            async with connect(websocket_url) as websocket:
                async for message in websocket:
                    data = json.loads(message)
                    readable = json.dumps(data, indent=4)
                    # logger.info(readable)
                    message_type = data["metadata"]["message_type"]
                    # logger.info(message_type)

                    if message_type == "session_welcome":
                        session_id = data["payload"]["session"]["id"]
                        await asyncio.to_thread(
                            requests.post,
                            url="https://api.twitch.tv/helix/eventsub/subscriptions",
                            headers=headers,
                            json={
                                "type": "channel.chat.message",
                                "version": "1",
                                "condition": {
                                    "broadcaster_user_id": BROADCASTER_ID,
                                    "user_id": BROADCASTER_ID,
                                },
                                "transport": {"method": "websocket", "session_id": session_id},
                            },
                        )
                        # logger.info(response.text)
                        # logger.info(f"{response.status_code} | {response.text}")
                        # response_data = json.loads(response.text)

                        # logger.info(f"response_data type: {type(response_data)}")

                        # logger.info(f"{response_data}")
                        # chat_message = response_data.get("metadata")

                        # logger.info(f"Chat message: {chat_message}")
                    if message_type == "notification":
                        readable_data = json.loads(readable)
                        logger.info(json.dumps(readable_data, indent=4))
                        chat_message = readable_data["payload"]["event"]["message"]["text"]
                        user = readable_data["payload"]["event"]["chatter_user_name"]
                        user_color = readable_data["payload"]["event"]["color"]
                        logger.info(user_color)
                        result = {
                            "user": user,
                            "user_color": user_color,
                            "chat_message": chat_message,
                        }
                        logger.info(result)
                        await message_queue.put(result)

    except TimeoutError:
        logger.info("Fun Chat has ended. :(")


@app.get("/")
async def get():
    return FileResponse(html_path)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.add(websocket)
    logger.info(f"Client connected.")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        # the disconnect event is delivered as soon as the tab closes.
        connections.discard(websocket)
        logger.info(f"Client disconnected.")


async def broadcaster():
    """Single consumer of the queue, fans each message out to every open tab."""
    while True:
        message = await message_queue.get()
        for websocket in list(connections):
            try:
                await websocket.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                connections.discard(websocket)


async def main():
    while True:
        query_params = {
            "broadcaster_id": BROADCASTER_ID,
            "reward_id": REWARD_ID,
            "status": "UNFULFILLED",
        }

        request = await asyncio.to_thread(
            requests.get,
            url="https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions",
            params=query_params,
            headers=headers,
        )
        # readable = json.dumps(request.json(), indent=4)
        # logger.info(readable)
        response = request.json()

        if not response.get("data"):
            await asyncio.sleep(5)
            continue

        redeem_id = response["data"][0]["id"]
        # logger.info(f"REDEEM_ID: {redeem_id}")

        await asyncio.to_thread(
            requests.patch,
            url="https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions",
            headers=headers,
            params={"broadcaster_id": BROADCASTER_ID, "id": f"{redeem_id}", "reward_id": REWARD_ID},
            json={"status": "FULFILLED"},
        )
        # readable = json.dumps(patch_request.json(), indent=4)
        # logger.info(readable)

        await fun_chat()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)