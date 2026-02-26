"""
外部接口 - 居民与真实世界的连接
居民的外部产出在这里登记，外部收入从这里流入金库。
"""
import json
import os
from datetime import datetime

import treasury

DATA_FILE = "data/external.json"

def _load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"outputs": [], "income_log": []}

def _save(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def register_output(citizen_id, output_type, title, content_path, day=0):
    """登记居民的外部产出（文章、代码、报告等）"""
    data = _load()
    output = {
        "citizen_id": citizen_id,
        "type": output_type,
        "title": title,
        "content_path": content_path,
        "day": day,
        "time": datetime.now().isoformat(),
        "income_generated": 0
    }
    data["outputs"].append(output)
    _save(data)
    return output

def record_income(amount, source_desc):
    """记录外部收入并存入金库"""
    data = _load()
    treasury.deposit(amount, source=source_desc)
    data["income_log"].append({
        "amount": amount,
        "source": source_desc,
        "time": datetime.now().isoformat()
    })
    _save(data)
    return treasury.get_balance()

def get_outputs(citizen_id=None):
    """查询外部产出"""
    data = _load()
    if citizen_id:
        return [o for o in data["outputs"] if o["citizen_id"] == citizen_id]
    return data["outputs"]
