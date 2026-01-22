import os
from pathlib import Path
from openai import AsyncOpenAI 
from dotenv import load_dotenv

# 1. 加载环境变量 (.env)
load_dotenv()

# 2. 初始化异步客户端
api_key = os.environ.get("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# 定位数据目录
BASE_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"
print(KNOWLEDGE_DIR)

async def get_strategy(champion_name: str):
    """
    异步获取攻略：优先读本地 txt，没有则问 LLM 通用知识
    """
    print(f"正在思考 {champion_name} 的打法")
    
    # --- A. 检索阶段 (Retrieval) ---
    file_path = KNOWLEDGE_DIR / f"{champion_name}.txt"
    context = ""
    
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            context = f.read()
        print(f"命中本地知识库: {file_path.name}")
    else:
        print(f"本地无数据，将使用 LLM 通用知识生成。")
        context = "暂无具体数据，请基于你的通用知识回答。"

    # --- B. 生成阶段 (Generation) ---
    prompt = f"""
    你是一个英雄联盟王者教练。
    用户正在询问英雄: 【{champion_name}】
    
    参考资料:
    {context}
    
    请简短输出 (不要超过100字):
    1. 核心连招
    2. 必做的一件事
    3. 必躲的一个技能
    """

    try:
        if not api_key:
            return "❌ 未配置 OPENAI_API_KEY，无法生成攻略。请检查 .env 文件。"

        response = await client.chat.completions.create(
            model="deepseek-chat", # 便宜快
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200 # 限制长度，回得快
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ LLM 调用失败: {e}"
