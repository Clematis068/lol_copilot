import requests

# 保持使用 zh_CN，这样显示的是中文
CHAMPION_URL_TEMPLATE = "https://ddragon.leagueoflegends.com/cdn/{version}/data/zh_CN/champion.json" 
VERSION_URL = "https://ddragon.leagueoflegends.com/api/versions.json"

class ChampionDatabase:
    def __init__(self):
        # 修改数据结构：id -> {"name": "潮汐海灵", "alias": "Fizz"}
        self.data_map = {} 
        self.version = ""
        self.load_data()

    def load_data(self):
        try:
            versions = requests.get(VERSION_URL).json()
            self.version = versions[0]
            
            url = CHAMPION_URL_TEMPLATE.format(version=self.version)
            data = requests.get(url).json()
            
            for champ_key, champ_data in data['data'].items():
                c_id = int(champ_data['key'])   # 105
                c_name = champ_data['name']     # "潮汐海灵"
                c_alias = champ_data['id']      # "Fizz" (这是不管是哪国语言都通用的唯一标识)
                
                # 存两个名字
                self.data_map[c_id] = {
                    "name": c_name,
                    "alias": c_alias
                }
                
            print(f"✅ 英雄数据库已更新 (v{self.version})")

        except Exception as e:
            print(f"❌ 数据同步失败: {e}")

    # 修改接口：返回一个字典，而不是单纯的字符串
    def get_champion_info(self, champion_id):
        return self.data_map.get(champion_id, {"name": f"Unknown_{champion_id}", "alias": "Unknown"})

champ_db = ChampionDatabase()
