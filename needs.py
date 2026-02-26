"""
世界基础需求 - 冷启动引擎
像CIVITAS的NPC岗位，让居民赚到第一桶金。
需求是竞争制的：多人可提交，质量最好的获得报酬。
金库空了就停发，这是真实的经济压力。
"""
import json
import os
from datetime import datetime

import treasury

DATA_FILE = "data/needs.json"

# 每日自动生成的世界需求
DAILY_NEEDS = [
    {
        "id": "daily_news",
        "title": "今日要闻",
        "desc": "搜索整理今天互联网上值得关注的AI/科技动态，输出结构化摘要",
        "reward": 10,
    },
    {
        "id": "chronicle",
        "title": "编年史",
        "desc": "记录今天世界里发生的事：谁做了什么，经济变化，重要对话",
        "reward": 8,
    },
    {
        "id": "knowledge",
        "title": "知识条目",
        "desc": "写一篇关于某个主题的深度介绍（主题自选）",
        "reward": 6,
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

def judge_and_reward(need_id, winner_id):
    """评判并发放奖励（由世界主循环调用）"""
    data = _load()
    for need in data["active_needs"]:
        if need["id"] == need_id and need["status"] == "open":
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
