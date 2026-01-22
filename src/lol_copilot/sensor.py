import asyncio
from lcu_driver import Connector
from lol_copilot.champion_data import champ_db


connector = Connector()
last_detected_champ = None

@connector.ready
async def connect(connection):
    print('✅ 助手已连接！请在客户端点击英雄头像...')

@connector.ws.register('/lol-champ-select/v1/session', event_types=('UPDATE',))
async def champ_select_handler(connection, event):
    global last_detected_champ
    data = event.data
    local_cell_id = data['localPlayerCellId']
    
    current_champ_info = None
    
    for team_member in data['myTeam']:
        if team_member['cellId'] == local_cell_id:
            cid = team_member.get('championId', 0)
            if cid == 0:
                cid = team_member.get('championPickIntent', 0)
            
            if cid != 0:
                # 获取完整信息 (中文名 + 英文ID)
                current_champ_info = champ_db.get_champion_info(cid)
            break
            
    # 判断逻辑修改
    if current_champ_info:
        # 取出两个名字
        cn_name = current_champ_info['name']   # 潮汐海灵
        en_alias = current_champ_info['alias'] # Fizz
        
        if cn_name != last_detected_champ:
            last_detected_champ = cn_name
            
            print(f"\n⚡ [感知] 目标锁定: {cn_name} ({en_alias})")
            
            # --- 关键点：把英文名 (Fizz) 传给 RAG ---
            # 这样它就会去读 Fizz.txt 了！
            strategy_text = await get_strategy(en_alias)
            
            print("-" * 40)
            print(strategy_text)
            print("-" * 40 + "\n")

def main():
    try:
        connector.start()
    except KeyboardInterrupt:
        print("程序已退出。")

if __name__ == "__main__":
    main()
