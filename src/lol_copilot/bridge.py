import asyncio
import json
from lcu_driver import Connector
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Global state to be consumed by the web app
game_state = {
    "isConnected": False,
    "myChampionId": 0,
    "enemyIds": [0, 0, 0, 0, 0],
    "assignedRole": "UNKNOWN"
}

connector = Connector()

@connector.ready
async def connect(connection):
    game_state["isConnected"] = True
    print('✅ LCU Bridge Connected')

@connector.close
async def disconnect(connection):
    game_state["isConnected"] = False
    print('❌ LCU Bridge Disconnected')

@connector.ws.register('/lol-champ-select/v1/session', event_types=('UPDATE', 'CREATE'))
async def champ_select_handler(connection, event):
    data = event.data
    local_cell_id = data.get('localPlayerCellId')
    
    # 1. Detect My Champion & Role
    for member in data.get('myTeam', []):
        if member['cellId'] == local_cell_id:
            # Check picked champion or hover intent
            cid = member.get('championId') or member.get('championPickIntent') or 0
            game_state["myChampionId"] = cid
            game_state["assignedRole"] = member.get('assignedPosition', 'UNKNOWN').upper()
            break
            
    # 2. Detect Enemy Team (All 5)
    enemies = []
    for member in data.get('theirTeam', []):
        eid = member.get('championId') or member.get('championPickIntent') or 0
        enemies.append(eid)
    
    # Pad to 5 slots
    while len(enemies) < 5:
        enemies.append(0)
    game_state["enemyIds"] = enemies[:5]

# --- Simple Local API Server ---
class StateHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/state':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(game_state).encode())
        else:
            self.send_response(404)
            self.end_headers()

def run_api():
    server = HTTPServer(('localhost', 8000), StateHandler)
    print("📡 Local API running at http://localhost:8000/state")
    server.serve_forever()

if __name__ == "__main__":
    # Run API in a separate thread
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    
    # Start LCU connector
    connector.start()