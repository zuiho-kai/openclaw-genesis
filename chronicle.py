"""
编年史 - 世界的记忆
自动记录每天发生的事。这比代码重要。
"""
import json
import os
from datetime import datetime

DATA_FILE = "data/chronicle.json"

def _load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": []}

def _save(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def record_day(day, summary):
    """记录一天的总结"""
    data = _load()
    entry = {
        "day": day,
        "summary": summary,
        "time": datetime.now().isoformat()
    }
    data["entries"].append(entry)
    _save(data)
    return entry

def record_event(day, event_type, description, citizen_id=None):
    """记录单个事件"""
    data = _load()
    event = {
        "day": day,
        "type": event_type,
        "description": description,
        "citizen_id": citizen_id,
        "time": datetime.now().isoformat()
    }
    data["entries"].append(event)
    _save(data)
    return event

def get_day(day):
    """获取某天的所有记录"""
    data = _load()
    return [e for e in data["entries"] if e.get("day") == day]

def get_full_history():
    """获取完整编年史"""
    return _load()["entries"]
