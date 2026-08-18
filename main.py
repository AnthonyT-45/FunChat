import asyncio
import json
import logging
import os
import random
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

# effects list
EFFECTS = ["shiny", "big"]
# might change to launch params / env vars
EFFECT_DURATION = 300
EFFECT_CHANCE = 0.33

armed_until = 0.0

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

badges: dict[str, dict[str, dict[str, str]]] = {}


def merge_badges(payload: dict) -> None:
    for badge_set in payload.get("data", []):
        versions = badges.setdefault(badge_set["set_id"], {})
        for version in badge_set["versions"]:
            versions[version["id"]] = {
                "url": version["image_url_4x"],
                "title": version.get("title") or badge_set["set_id"],
            }


async def load_badges() -> None:
    for url, params in (
        ("https://api.twitch.tv/helix/chat/badges/global", None),
        ("https://api.twitch.tv/helix/chat/badges", {"broadcaster_id": BROADCASTER_ID}),
    ):
        try:
            request = await asyncio.to_thread(requests.get, url=url, headers=headers, params=params)
            request.raise_for_status()
            merge_badges(request.json())
        except requests.RequestException as error:
            logger.info(f"Could not load badges from {url}: {error}")
    logger.info(f"Loaded {len(badges)} badge sets.")


def badge_images(chatter_badges: list[dict]) -> list[dict[str, str]]:
    images = []
    for badge in chatter_badges:
        version = badges.get(badge["set_id"], {}).get(badge["id"])
        if version:
            images.append(version)
        else:
            logger.info(f"Unknown badge: {badge['set_id']}/{badge['id']}")
    return images


@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_badges()
    listener = asyncio.create_task(chat_listener())
    fanout = asyncio.create_task(broadcaster())
    yield
    listener.cancel()
    fanout.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


async def subscribe(session_id: str) -> None:
    subscriptions = [
        (
            "channel.chat.message",
            {"broadcaster_user_id": BROADCASTER_ID, "user_id": BROADCASTER_ID},
        ),
        (
            "channel.channel_points_custom_reward_redemption.add",
            {"broadcaster_user_id": BROADCASTER_ID, "reward_id": REWARD_ID},
        ),
    ]
    for subscription_type, condition in subscriptions:
        response = await asyncio.to_thread(
            requests.post,
            url="https://api.twitch.tv/helix/eventsub/subscriptions",
            headers=headers,
            json={
                "type": subscription_type,
                "version": "1",
                "condition": condition,
                "transport": {"method": "websocket", "session_id": session_id},
            },
        )
        if response.ok:
            logger.info(f"Subscribed to {subscription_type}.")
        else:
            logger.info(
                f"Could not subscribe to {subscription_type}: "
                f"{response.status_code} | {response.text}"
            )


async def fulfill(redeem_id: str, reward_id: str) -> None:
    response = await asyncio.to_thread(
        requests.patch,
        url="https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions",
        headers=headers,
        params={"broadcaster_id": BROADCASTER_ID, "id": redeem_id, "reward_id": reward_id},
        json={"status": "FULFILLED"},
    )
    if not response.ok:
        logger.info(f"Could not fulfill {redeem_id}: {response.status_code} | {response.text}")


def roll_effect() -> str | None:
    if asyncio.get_running_loop().time() > armed_until:
        return None
    if random.random() >= EFFECT_CHANCE:
        return None
    return random.choice(EFFECTS)


async def handle_notification(payload: dict) -> None:
    global armed_until

    subscription_type = payload["subscription"]["type"]
    event = payload["event"]

    if subscription_type == "channel.chat.message":
        await message_queue.put(
            {
                "type": "chat",
                "user": event["chatter_user_name"],
                "user_color": event["color"],
                "chat_message": event["message"]["text"],
                "badges": badge_images(event.get("badges", [])),
                "effect": roll_effect(),
            }
        )

    if subscription_type == "channel.channel_points_custom_reward_redemption.add":
        armed_until = asyncio.get_running_loop().time() + EFFECT_DURATION
        logger.info(f"{event['user_name']} started fun chat for {EFFECT_DURATION}s.")
        await fulfill(event["id"], event["reward"]["id"])


async def chat_listener() -> None:
    url = websocket_url
    resubscribe = True

    while True:
        reconnecting = False
        try:
            async with connect(url) as websocket:
                async for message in websocket:
                    data = json.loads(message)
                    message_type = data["metadata"]["message_type"]

                    if message_type == "session_welcome":
                        if resubscribe:
                            await subscribe(data["payload"]["session"]["id"])
                        logger.info("Fun Chat is live.")

                    if message_type == "notification":
                        await handle_notification(data["payload"])

                    if message_type == "session_reconnect":
                        url = data["payload"]["session"]["reconnect_url"]
                        resubscribe = False
                        reconnecting = True
                        break

                    if message_type == "revocation":
                        logger.info(f"Subscription revoked: {json.dumps(data['payload'])}")

        except Exception as error:
            logger.info(f"EventSub connection lost ({error}), retrying in 5s.")
            await asyncio.sleep(5)

        if not reconnecting:
            url = websocket_url
            resubscribe = True


@app.get("/")
async def get():
    return FileResponse(html_path)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.add(websocket)
    logger.info("Client connected.")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        # the disconnect event is delivered as soon as the tab closes.
        connections.discard(websocket)
        logger.info("Client disconnected.")


async def broadcaster():
    # fans each message out to every open tab.
    while True:
        message = await message_queue.get()
        for websocket in list(connections):
            try:
                await websocket.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                connections.discard(websocket)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
