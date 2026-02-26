"""
广场 - 居民间的公共空间
所有居民（包括人类）可以在这里发言、看到彼此的发言。
就像CIVITAS的广场演讲。
"""
import json
import os
from datetime import datetime

DATA_FILE = "data/plaza.json"

def _load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"messages": []}

def _save(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def speak(citizen_id, content, day=0):
    """在广场发言"""
    data = _load()
    msg = {
        "citizen_id": citizen_id,
        "content": content,
        "day": day,
        "time": datetime.now().isoformat()
    }
    data["messages"].append(msg)
    _save(data)
    return msg

def get_recent(limit=20):
    """获取最近的广场发言"""
    data = _load()
    return data["messages"][-limit:]

def get_day_messages(day):
    """获取某天的所有发言"""
    data = _load()
    return [m for m in data["messages"] if m.get("day") == day]
