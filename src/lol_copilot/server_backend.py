"""
LOL Copilot Backend Server
整合 LCU Bridge + Web API
"""
import asyncio
import json
from aiohttp import web
from aiohttp.web import middleware
from lcu_driver import Connector

from lol_copilot.champion_data import champ_db
from lol_copilot.rag.engine import get_strategy, client as llm_client

# 全局游戏状态
game_state = {
    "isConnected": False,
    "myChampionId": 0,
    "myPickIntentId": 0,
    "enemyIds": [0, 0, 0, 0, 0],
    "assignedRole": "UNKNOWN",
}

# 聊天历史 (用于上下文对话)
chat_history = []

connector = Connector()


# --- CORS Middleware ---
@middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# --- Web API Handlers ---

async def handle_get_state(request):
    """GET /state - 获取当前游戏状态"""
    return web.json_response(game_state)


async def handle_get_champions(request):
    """GET /champions - 获取全部英雄列表"""
    champions = []
    for cid, info in champ_db.data_map.items():
        champions.append({
            "id": cid,
            "name": info["name"],
            "alias": info["alias"],
            "icon": f"https://ddragon.leagueoflegends.com/cdn/{champ_db.version}/img/champion/{info['alias']}.png"
        })
    return web.json_response({
        "version": champ_db.version,
        "champions": champions
    })


async def handle_get_strategy(request):
    """GET /strategy/{champion_id} - 获取指定英雄的 AI 攻略"""
    champion_id = request.match_info.get("champion_id", "0")

    try:
        cid = int(champion_id)
    except ValueError:
        return web.json_response({"error": "Invalid champion ID"}, status=400)

    if cid == 0:
        return web.json_response({"error": "No champion selected"}, status=400)

    # 获取英雄信息
    champ_info = champ_db.get_champion_info(cid)
    champ_name = champ_info["name"]
    champ_alias = champ_info["alias"]

    # 调用 RAG 获取攻略
    strategy_text = await get_strategy(champ_alias)

    return web.json_response({
        "championId": cid,
        "championName": champ_name,
        "championAlias": champ_alias,
        "strategy": strategy_text
    })


async def handle_analyze_enemies(request):
    """POST /analyze-enemies - 分析敌方阵容"""
    try:
        data = await request.json()
        enemy_ids = data.get("enemyIds", game_state["enemyIds"])
    except:
        enemy_ids = game_state["enemyIds"]

    # 获取敌方英雄信息
    enemies = []
    for eid in enemy_ids:
        if eid and eid != 0:
            info = champ_db.get_champion_info(eid)
            enemies.append({
                "id": eid,
                "name": info["name"],
                "alias": info["alias"]
            })

    if not enemies:
        return web.json_response({
            "enemies": [],
            "analysis": "暂无敌方阵容信息"
        })

    # 构建分析 prompt
    enemy_names = ", ".join([e["name"] for e in enemies])
    prompt = f"""
    你是一个英雄联盟王者教练。
    敌方阵容: {enemy_names}

    请简短分析 (不超过150字):
    1. 敌方阵容特点 (AP/AD比例、前后排)
    2. 最需要注意的敌方英雄
    3. 团战建议
    """

    try:
        response = await llm_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        analysis = response.choices[0].message.content
    except Exception as e:
        analysis = f"分析失败: {e}"

    return web.json_response({
        "enemies": enemies,
        "analysis": analysis
    })


async def handle_chat(request):
    """POST /chat - 与 AI 对话"""
    global chat_history

    try:
        data = await request.json()
        user_message = data.get("message", "").strip()
    except:
        return web.json_response({"error": "Invalid request"}, status=400)

    if not user_message:
        return web.json_response({"error": "Message is required"}, status=400)

    # 构建上下文
    # 获取当前英雄信息
    my_champ = ""
    if game_state["myChampionId"]:
        info = champ_db.get_champion_info(game_state["myChampionId"])
        my_champ = info["name"]

    enemy_names = []
    for eid in game_state["enemyIds"]:
        if eid and eid != 0:
            info = champ_db.get_champion_info(eid)
            enemy_names.append(info["name"])

    system_prompt = f"""你是一个英雄联盟王者教练助手。
当前玩家英雄: {my_champ if my_champ else '未选择'}
敌方阵容: {', '.join(enemy_names) if enemy_names else '未知'}
请用简洁的中文回答玩家的问题。"""

    # 添加用户消息到历史
    chat_history.append({"role": "user", "content": user_message})

    # 保持历史不超过10条
    if len(chat_history) > 10:
        chat_history = chat_history[-10:]

    messages = [{"role": "system", "content": system_prompt}] + chat_history

    try:
        response = await llm_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        assistant_message = response.choices[0].message.content

        # 添加助手回复到历史
        chat_history.append({"role": "assistant", "content": assistant_message})

    except Exception as e:
        assistant_message = f"对话失败: {e}"

    return web.json_response({
        "reply": assistant_message
    })


async def handle_clear_chat(request):
    """POST /chat/clear - 清空聊天历史"""
    global chat_history
    chat_history = []
    return web.json_response({"success": True})


# --- Web Server Setup ---

async def start_web_server():
    """启动 Web API 服务器"""
    if getattr(start_web_server, 'has_started', False):
        return

    app = web.Application(middlewares=[cors_middleware])

    # 路由配置
    app.router.add_get('/state', handle_get_state)
    app.router.add_get('/champions', handle_get_champions)
    app.router.add_get('/strategy/{champion_id}', handle_get_strategy)
    app.router.add_post('/analyze-enemies', handle_analyze_enemies)
    app.router.add_post('/chat', handle_chat)
    app.router.add_post('/chat/clear', handle_clear_chat)

    # OPTIONS 预检请求支持
    app.router.add_route('OPTIONS', '/{path:.*}', lambda r: web.Response())

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8000)
    await site.start()

    print("=" * 50)
    print("LOL Copilot API Server")
    print("=" * 50)
    print("Endpoints:")
    print("  GET  /state              - 游戏状态")
    print("  GET  /champions          - 英雄列表")
    print("  GET  /strategy/{id}      - 英雄攻略")
    print("  POST /analyze-enemies    - 敌方分析")
    print("  POST /chat               - AI 对话")
    print("  POST /chat/clear         - 清空对话")
    print("=" * 50)
    print("Server running at http://localhost:8000")
    print("=" * 50)

    start_web_server.has_started = True


# --- LCU Event Handlers ---

@connector.ready
async def connect(connection):
    game_state["isConnected"] = True
    print("LCU Connected")
    asyncio.create_task(start_web_server())


@connector.close
async def disconnect(connection):
    game_state["isConnected"] = False
    print("LCU Disconnected")


@connector.ws.register('/lol-champ-select/v1/session', event_types=('UPDATE', 'CREATE'))
async def champ_select_handler(connection, event):
    data = event.data
    local_cell_id = data.get('localPlayerCellId')

    # 1. 检测我方英雄和位置
    for member in data.get('myTeam', []):
        if member['cellId'] == local_cell_id:
            cid = member.get('championId') or member.get('championPickIntent') or 0
            game_state["myChampionId"] = cid
            game_state["myPickIntentId"] = member.get('championPickIntent', 0)
            game_state["assignedRole"] = member.get('assignedPosition', 'UNKNOWN').upper()
            break

    # 2. 检测敌方阵容
    enemies = []
    for member in data.get('theirTeam', []):
        eid = member.get('championId') or member.get('championPickIntent') or 0
        enemies.append(eid)

    while len(enemies) < 5:
        enemies.append(0)
    game_state["enemyIds"] = enemies[:5]


# --- Entry Point ---

def main():
    print("Starting LOL Copilot...")
    print("Waiting for League Client...")
    try:
        connector.start()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
