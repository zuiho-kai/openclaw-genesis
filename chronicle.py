"""
编年史 - 世界的记忆
自动记录每天发生的事。这比代码重要。
"""
import json
import os
from datetime import datetime

DATA_FILE = "data/chronicle.json"
CHRONICLE_DIR = "chronicle"


def _load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": []}


def _save(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_day_md(day):
    """把某天的所有事件写成独立 md 文件"""
    entries = get_day(day)
    if not entries:
        return

    os.makedirs(CHRONICLE_DIR, exist_ok=True)
    path = os.path.join(CHRONICLE_DIR, f"D{day:03d}.md")

    lines = [f"# 第 {day} 天\n"]
    for e in entries:
        t = e.get("time", "")[:16]
        etype = e.get("type", "")
        desc = e.get("description", "")
        cid = e.get("citizen_id", "")
        summary = e.get("summary", "")

        if etype == "day_summary":
            lines.append(f"\n## 日终总结\n")
            if isinstance(summary, dict):
                ts = summary.get("treasury", {})
                lines.append(f"- 金库余额：{ts.get('balance', '?')} token（还能撑 {ts.get('days_left', '?')} 天）\n")
                for cid2, status in summary.get("survival", {}).items():
                    lines.append(f"- {cid2}: {status}\n")
        else:
            prefix = f"[{t}]" if t else ""
            actor = f" **{cid}**" if cid else ""
            lines.append(f"- {prefix}{actor} {desc}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def record_day(day, summary):
    """记录一天的总结，并写 md 文件"""
    data = _load()
    entry = {
        "day": day,
        "type": "day_summary",
        "summary": summary,
        "time": datetime.now().isoformat()
    }
    data["entries"].append(entry)
    _save(data)
    _write_day_md(day)
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
