# FunChat

A better Twitch Chat experience.

## Requirements

- Python 3.10+
- A Twitch account with **Affiliate or Partner** status (channel points are required to create custom rewards)
- Make

## Environment variables

```bash
make setup
cp .env.example .env
```

### **CLIENT_ID**/**CLIENT_SECRET**

1. Go to <https://dev.twitch.tv/console/apps> and click **Register Your Application**.
2. Name it anything, set **OAuth Redirect URLs** to <https://localhost>, category **Chat Bot** or **Other**, client type **Confidential**.
3. Copy the **Client ID**, then click **New Secret** for the **Client Secret**.

### **ACCESS_TOKEN**

1. Put this URL in browser
  <https://auth.twitch.tv/authorize?response_type=token&client_id=CLIENT_ID&redirect_uri=https%3A%2F%2Flocalhost&scope=channel%3Aread%3Aredemption+channel%3Amanage%3Aredemptions+user%3Aread%3Achat>

2. You get redirected to `https://localhost/#access_token=<ACCESS_TOKEN>` Copy the `<ACCESS_TOKEN>`.

### **BROADCASTER_ID**

```bash
curl -H "Client-Id: <CLIENT_ID>" \
     -H "Authorization: Bearer <ACCESS_TOKEN>" \
     "https://api.twitch.tv/helix/users"
```

### **REWARD_ID**

The reward must be created by the **CLIENT_ID** that the app runs with.
Twitch only lets an application read and update redemptions for rewards it created itself.
A reward you make in the Twitch dashboard will **not** work here.

This is a one-time setup step.
You may Postman, `curl`, or any HTTP client.
Every request below needs the following header:

```text
Client-Id: <CLIENT_ID>
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

**Create the reward:**

```text
POST https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id=<BROADCASTER_ID>
```

Request Body:

```json
{
  "title": "Fun Chat",
  "cost": 100
}
```

REWARD_ID should be found within the response body.

## Development

### Formatting

```bash
make format
```

### Run Command

```bash
python main.py
```

Open <http://127.0.0.1:8000> to see the chat overlay.
