"""
世界基础需求 - 冷启动引擎
像CIVITAS的NPC岗位，让居民赚到第一桶金。
需求是竞争制的：多人可提交，质量最好的获得报酬。
金库空了就停发，这是真实的经济压力。
"""
import json
import os
import urllib.request
from datetime import datetime

import treasury

DATA_FILE = "data/needs.json"

# 评判用付费模型（免费模型上下文不够评判长内容）
JUDGE_API = "https://api.siliconflow.cn/v1/chat/completions"
JUDGE_MODEL = "deepseek-ai/DeepSeek-V3.2"
JUDGE_API_KEY = "sk-qtlmaexaspopnlzoezdwkbwuyhqbbllpoinhlqguovwdqwlk"

# 每日自动生成的世界需求
DAILY_NEEDS = [
    {
        "id": "daily_intel",
        "title": "每日情报",
        "desc": "搜索并整理AI/科技领域今天的重要动态，输出结构化报告",
        "reward": 12,
        "external": True,
    },
    {
        "id": "chronicle",
        "title": "每日编年史",
        "desc": "记录今天世界里发生的所有重要事件：谁做了什么，经济变化，重要对话",
        "reward": 8,
        "external": False,
    },
    {
        "id": "open_research",
        "title": "自由研究",
        "desc": "研究任何你认为有价值的主题，提交报告",
        "reward": 5,
        "external": True,
    },
]

def _load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"day": 0, "active_needs": [], "history": []}

def _save(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_daily_needs(day):
    """生成当天的世界需求，金库空了就不发"""
    data = _load()
    data["day"] = day

    # 检查金库能不能负担
    treasury_status = treasury.get_status()
    if not treasury_status["healthy"]:
        data["active_needs"] = []
        _save(data)
        return []  # 金库告急，停发需求

    needs = []
    for template in DAILY_NEEDS:
        need = {
            **template,
            "day": day,
            "submissions": [],
            "winner": None,
            "status": "open",
        }
        needs.append(need)

    data["active_needs"] = needs
    _save(data)
    return needs

def submit(need_id, citizen_id, content):
    """居民提交需求成果"""
    data = _load()
    for need in data["active_needs"]:
        if need["id"] == need_id and need["status"] == "open":
            need["submissions"].append({
                "citizen_id": citizen_id,
                "content": content,
                "time": datetime.now().isoformat()
            })
            _save(data)
            return True
    return False

def _llm_judge(need_title, need_desc, submissions):
    """用免费模型评判提交质量，返回winner的citizen_id"""
    if len(submissions) == 1:
        return submissions[0]["citizen_id"]

    entries = ""
    for i, s in enumerate(submissions):
        entries += f"\n提交{i+1} (来自{s['citizen_id']}):\n{s['content'][:500]}\n"

    prompt = (
        f"你是世界需求的评判者。需求是：{need_title} — {need_desc}\n\n"
        f"以下是所有提交：{entries}\n\n"
        f"请评判哪个提交质量最高。评判标准：内容真实性、信息量、结构清晰度。\n"
        f"只回复获胜者的居民编号（如C1），不要其他内容。"
    )

    payload = json.dumps({
        "model": JUDGE_MODEL,
        "messages": [
            {"role": "system", "content": "你是公正的评判者，只回复获胜者编号。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 32,
        "temperature": 0.1,
    }).encode("utf-8")

    req = urllib.request.Request(
        JUDGE_API, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {JUDGE_API_KEY}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
            # 从回复中提取居民ID
            for s in submissions:
                if s["citizen_id"] in text:
                    return s["citizen_id"]
            # 没匹配到就给第一个
            return submissions[0]["citizen_id"]
    except Exception:
        return submissions[0]["citizen_id"]


def judge_and_reward(need_id):
    """评判并发放奖励（竞争制：LLM评分，最高分赢）"""
    data = _load()
    for need in data["active_needs"]:
        if need["id"] == need_id and need["status"] == "open":
            subs = need.get("submissions", [])
            if not subs:
                return 0

            # LLM评判
            winner_id = _llm_judge(need["title"], need["desc"], subs)
            need["winner"] = winner_id
            need["status"] = "completed"

            # 从金库支出
            result = treasury.withdraw(need["reward"], purpose=f"need:{need_id}")
            if result is not None:
                from economy import reward
                reward(winner_id, need["reward"], source=f"need:{need_id}")
                _save(data)
                return need["reward"]
            else:
                need["status"] = "unfunded"
                _save(data)
                return 0
    return 0

def get_open_needs():
    """获取当前开放的需求"""
    data = _load()
    return [n for n in data["active_needs"] if n["status"] == "open"]

def close_day():
    """结束当天，归档需求"""
    data = _load()
    data["history"].extend(data["active_needs"])
    data["active_needs"] = []
    _save(data)
