import logging
import time
import requests
import os
import json
import asyncio
from websockets.asyncio.client import connect
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
BROADCASTER_ID = os.getenv("BROADCASTER_ID")
REWARD_ID = os.getenv("REWARD_ID")

websocket_url = "wss://eventsub.wss.twitch.tv/ws"

headers = {
            'Client-Id': f"{CLIENT_ID}",
            'Authorization': f"Bearer {ACCESS_TOKEN}",
            'Accept': "application/json"
        }

# logger config
FORMAT = '%(asctime)s %(message)s'

logger = logging.getLogger(__name__)
logging.basicConfig(format=FORMAT, level=logging.INFO)

async def fun_chat():
        
    logger.info("Fun Chat executed") 
    # todo: fix timeout error, gracefully exit
    async with asyncio.timeout(300):
        async with connect(websocket_url) as websocket:
            async for message in websocket:
                data = json.loads(message)
                readable = json.dumps(data, indent=4)
                logger.info(readable)
                message_type = data["metadata"]["message_type"]
                logger.info(message_type)

                if message_type == "session_welcome":
                    session_id = data["payload"]["session"]["id"]
                    response = requests.post(url="https://api.twitch.tv/helix/eventsub/subscriptions", headers=headers, json={"type": "channel.chat.message","version":"1","condition":{"broadcaster_user_id":BROADCASTER_ID, "user_id": BROADCASTER_ID},"transport":{"method": "websocket", "session_id": session_id}})
                    logger.info(f"{response.status_code} | {response.text}")
 
async def main():
    while True:
        query_params = {
            "broadcaster_id": BROADCASTER_ID,
            "reward_id": REWARD_ID,
            "status": "UNFULFILLED"
        }

        request = requests.get(url="https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions", params=query_params, headers=headers)
        readable = json.dumps(request.json(), indent=4)
        logger.info(readable)
        response = request.json()

        if not response.get("data"):
            time.sleep(5)
            continue

        redeem_id = response["data"][0]["id"]
        logger.info(f"REDEEM_ID: {redeem_id}")

        await fun_chat()

        patch_request = requests.patch(url="https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions", headers=headers, params={"broadcaster_id": BROADCASTER_ID, "id": f"{redeem_id}", "reward_id": REWARD_ID}, json={"status": "FULFILLED"})
        readable = json.dumps(patch_request.json(), indent=4)
        logger.info(readable)

if __name__ == "__main__":
    asyncio.run(main())


# POST call to create a reward with same CLIENT_ID

# request = requests.post(url="https://api.twitch.tv/helix/channel_points/custom_rewards", params=query_params, headers=headers, json=request_body)
# request_dict = request.json()
# logger.info(request_dict)

# GET call to retrieve reward_id

# request = requests.get(url="https://api.twitch.tv/helix/channel_points/custom_rewards", params=query_params, headers=headers)
# request_dict = request.json()
# logger.info(request_dict)