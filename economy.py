"""
经济系统 - 居民的钱包和交易
每个居民有余额，每天扣生存成本，可以互相交易。
"""
import json
import os
from datetime import datetime

DATA_FILE = "data/economy.json"

SURVIVAL_COST = 5  # 每天每人扣5 token
INITIAL_BALANCE = 50  # 每个居民初始50 token（从金库拨付）

def _load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"citizens": {}, "transactions": []}

def _save(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def register_citizen(citizen_id):
    """新居民注册，获得初始余额"""
    data = _load()
    if citizen_id in data["citizens"]:
        return data["citizens"][citizen_id]
    data["citizens"][citizen_id] = {
        "balance": INITIAL_BALANCE,
        "total_earned": 0,
        "total_spent": 0,
        "status": "active",  # active / hibernating
        "registered": datetime.now().isoformat()
    }
    _save(data)
    return data["citizens"][citizen_id]

def get_citizen(citizen_id):
    """查询居民经济状态"""
    data = _load()
    return data["citizens"].get(citizen_id)

def get_all_citizens():
    """所有居民经济状态"""
    return _load()["citizens"]

def deduct_survival_cost():
    """每日结算：扣除所有活跃居民的生存成本"""
    data = _load()
    results = {}
    for cid, info in data["citizens"].items():
        if info["status"] != "active":
            results[cid] = "hibernating"
            continue
        info["balance"] -= SURVIVAL_COST
        info["total_spent"] += SURVIVAL_COST
        if info["balance"] <= 0:
            info["balance"] = 0
            info["status"] = "hibernating"
            results[cid] = "hibernated"
        else:
            results[cid] = f"alive ({info['balance']} left)"
    _save(data)
    return results

def pay(from_id, to_id, amount, reason=""):
    """居民间转账"""
    data = _load()
    sender = data["citizens"].get(from_id)
    receiver = data["citizens"].get(to_id)
    if not sender or not receiver:
        return None
    if sender["balance"] < amount:
        return None
    sender["balance"] -= amount
    sender["total_spent"] += amount
    receiver["balance"] += amount
    receiver["total_earned"] += amount
    data["transactions"].append({
        "from": from_id,
        "to": to_id,
        "amount": amount,
        "reason": reason,
        "time": datetime.now().isoformat()
    })
    _save(data)
    return {"sender_balance": sender["balance"], "receiver_balance": receiver["balance"]}

def reward(citizen_id, amount, source="world_needs"):
    """世界奖励居民（完成基础需求等）"""
    data = _load()
    citizen = data["citizens"].get(citizen_id)
    if not citizen:
        return None
    citizen["balance"] += amount
    citizen["total_earned"] += amount
    data["transactions"].append({
        "from": "world",
        "to": citizen_id,
        "amount": amount,
        "reason": source,
        "time": datetime.now().isoformat()
    })
    _save(data)
    return citizen["balance"]
