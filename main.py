import sys

# Dummy Audioop fix for environments lacking it (like Python 3.13+ on Linux)
class DummyAudioop:
    error = Exception
    def mul(self, cp, size, factor): return b''
    def max(self, cp, size): return 0
    def lin2lin(self, fragment, width, newwidth): return b''
    def ratecv(self, fragment, width, nchannels, inrate, outrate, state): return (b'', None)
    def ulaw2lin(self, fragment, width): return b''
    def lin2ulaw(self, fragment, width): return b''
    def alaw2lin(self, fragment, width): return b''
    def lin2alaw(self, fragment, width): return b''

sys.modules['audioop'] = DummyAudioop()

import asyncio
import json
import os
import threading
import requests
from flask import Flask
import websockets

# Flask Keep Alive Setup for Railway
app = Flask('')

@app.route('/')
def home():
    return "Railway Discord AFK System is Live 24/7"

def run_flask():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

TARGET_GUILD_ID = "1199149309271232522"
TARGET_VOICE_CHANNELS = [
    "1472330853261512898",
    "1472330786085667007",
    "1505174981011705969",
    "1505175028600148028",
    "1505175047478710353",
    "1505171919794606080",
    "1505175175329480806"
]

VALID_TOKENS = []

def load_and_validate_tokens():
    global VALID_TOKENS
    raw_tokens = os.environ.get("TOKENS", "")
    
    if not raw_tokens:
        print("[X] Error: 'TOKENS' variable is empty or not found in Railway Variables!")
        return

    all_tokens = [t.strip() for t in raw_tokens.split(",") if t.strip()]
    print(f"[*] Found {len(all_tokens)} tokens in variables. Starting validation...")

    def check_token(tok):
        headers = {"Authorization": tok, "Content-Type": "application/json"}
        try:
            res = requests.get("https://discord.com/api/v9/users/@me", headers=headers, timeout=3)
            if res.status_code == 200:
                VALID_TOKENS.append(tok)
                print(f"[+] Token Valid: {res.json().get('username', 'Unknown')}")
            else:
                print(f"[-] Token Invalid (Status {res.status_code})")
        except Exception as e:
            print(f"[X] Network error validating token: {e}")

    threads = []
    for token in all_tokens:
        t = threading.Thread(target=check_token, args=(token,))
        t.daemon = True
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()

    print(f"[✓] Validation completed. Total Active Tokens: {len(VALID_TOKENS)}")

class DiscordVoiceAFK:
    def __init__(self, token, account_index, target_channel_id):
        self.token = token
        self.account_id = f"Account #{account_index}"
        self.target_channel_id = target_channel_id
        self.ws_url = "wss://gateway.discord.gg/?v=9&encoding=json"
        self.heartbeat_interval = None
        self.sequence = None
        self.ws = None

    async def send_heartbeat(self):
        while self.ws:
            if self.heartbeat_interval:
                await asyncio.sleep(self.heartbeat_interval / 1000)
                heartbeat_payload = {"op": 1, "d": self.sequence}
                try:
                    await self.ws.send(json.dumps(heartbeat_payload))
                except:
                    break
            else:
                await asyncio.sleep(1)

    async def update_voice_state(self):
        if self.ws:
            payload = {
                "op": 4,
                "d": {
                    "guild_id": TARGET_GUILD_ID,
                    "channel_id": self.target_channel_id,
                    "self_mute": True,   
                    "self_deaf": True,   
                    "self_video": False
                }
            }
            try:
                await self.ws.send(json.dumps(payload))
            except Exception as e:
                print(f"[X] Failed to update voice state for {self.account_id}: {e}")

    async def start(self):
        print(f"[*] [{self.account_id}] Connecting to Room: {self.target_channel_id}")
        try:
            async with websockets.connect(self.ws_url, max_size=None) as ws:
                self.ws = ws
                hello_msg = await ws.recv()
                hello_data = json.loads(hello_msg)
                
                if hello_data['op'] == 10:  
                    self.heartbeat_interval = hello_data['d']['heartbeat_interval']
                    asyncio.create_task(self.send_heartbeat())
                
                identify_payload = {
                    "op": 2,
                    "d": {
                        "token": self.token,
                        "capabilities": 8189,
                        "properties": {
                            "os": "Linux", "browser": "Discord Client", "release_channel": "stable",
                            "client_version": "1.0.9001", "os_version": "Ubuntu", "os_arch": "x64",
                            "system_locale": "en-US", "client_build_number": 260000, "client_event_source": None
                        },
                        "presence": {"status": "online", "since": 0, "activities": [], "afk": False},
                        "compress": False
                    }
                }
                await ws.send(json.dumps(identify_payload))
                await asyncio.sleep(1.5)
                await self.update_voice_state()
                print(f"[+] [{self.account_id}] Connected Successfully inside Room.")

                while True:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(message)
                        if data.get('s'): self.sequence = data['s']
                        if data.get('op') == 7: break
                    except asyncio.TimeoutError:
                        continue
        except Exception as e:
            print(f"[X] [{self.account_id}] Connection Interrupted: {e}")
        finally:
            self.ws = None

async def start_async_loop():
    clients = []
    for idx, token in enumerate(VALID_TOKENS):
        channel_index = (idx // 2) % len(TARGET_VOICE_CHANNELS)
        target_room = TARGET_VOICE_CHANNELS[channel_index]
        client_obj = DiscordVoiceAFK(token, idx + 1, target_room)
        clients.append(client_obj)

    tasks = [client.start() for client in clients]
    if tasks:
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    print("[*] Starting Bot environment for Railway...")
    
    load_and_validate_tokens()

    if not VALID_TOKENS:
        print("[X] Critical Error: No valid tokens to connect. Exiting...")
        sys.exit(1)

    t_flask = threading.Thread(target=run_flask, daemon=True)
    t_flask.start()

    print("[*] Connecting all accounts to their dedicated channels...")
    asyncio.run(start_async_loop())