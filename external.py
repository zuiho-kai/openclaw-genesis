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

TAX_RATE = 0.30  # 外层收入30%进金库

def record_income(amount, citizen_id, source_desc):
    """记录外部收入，70%归居民，30%进金库（税）"""
    import economy
    data = _load()
    treasury_share = round(amount * TAX_RATE, 2)
    citizen_share = round(amount - treasury_share, 2)

    # 30% 进金库
    treasury.deposit(treasury_share, source=f"tax:{source_desc}")
    # 70% 给居民
    economy.reward(citizen_id, citizen_share, source=f"external:{source_desc}")

    data["income_log"].append({
        "amount": amount,
        "citizen_id": citizen_id,
        "citizen_share": citizen_share,
        "treasury_share": treasury_share,
        "source": source_desc,
        "time": datetime.now().isoformat()
    })
    _save(data)
    return {"citizen_share": citizen_share, "treasury_share": treasury_share}

def get_outputs(citizen_id=None):
    """查询外部产出"""
    data = _load()
    if citizen_id:
        return [o for o in data["outputs"] if o["citizen_id"] == citizen_id]
    return data["outputs"]
