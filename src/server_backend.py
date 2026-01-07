import asyncio
import json
from aiohttp import web
from lcu_driver import Connector

# 全局状态
game_state = {
    "isConnected": False,
    "myChampionId": 0,
    "myPickIntentId": 0,
    "enemyIds": [0, 0, 0, 0, 0],
    "assignedRole": "UNKNOWN",
    "guideText": "等待游戏连接..."
}

connector = Connector()

# --- Web Server 逻辑 ---
async def handle_get_state(request):
    return web.json_response(game_state, headers={
        "Access-Control-Allow-Origin": "*"
    })

async def start_web_server():
    # 防止重复启动
    if getattr(start_web_server, 'has_started', False):
        return
    
    app = web.Application()
    app.router.add_get('/state', handle_get_state)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8000)
    await site.start()
    
    print("Web 服务器已启动: http://localhost:8000/state")
    start_web_server.has_started = True

# --- LCU 逻辑 ---

@connector.ready
async def connect(connection):
    game_state["isConnected"] = True
    print('已连接到小助手本身')
    
    # 关键点：利用 LCU 的 Event Loop 启动 Web 服务器
    # 同一个线程里共存
    asyncio.create_task(start_web_server())

@connector.close
async def disconnect(connection):
    game_state["isConnected"] = False
    print('客户端与助手连接已断开')

@connector.ws.register('/lol-champ-select/v1/session', event_types=('UPDATE', 'CREATE'))
async def champ_select_handler(connection, event):
    data = event.data
    local_cell_id = data.get('localPlayerCellId')
    
    # 同步数据
    for team_member in data.get('myTeam', []):
        if team_member['cellId'] == local_cell_id:
            game_state["myChampionId"] = team_member.get('championId', 0)
            game_state["myPickIntentId"] = team_member.get('championPickIntent', 0)
            break

# --- 启动入口 ---
if __name__ == "__main__":
    # 直接调用，不要 await，不要 asyncio.run
    # connector.start() 内部会自己创建 loop 并运行 forever
    try:
        connector.start()
    except KeyboardInterrupt:
        print("停止运行")
