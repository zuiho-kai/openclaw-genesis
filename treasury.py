"""
金库 - 世界的经济心脏
token不是凭空印的，来自外层真实收入。
种子基金是唯一的"印钱"，之后全靠居民赚回来。
"""
import json
import os
from datetime import datetime

DATA_FILE = "data/treasury.json"

def _load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "balance": 500,        # 种子基金500 token
        "seed_fund": 500,      # 初始种子（记录用，不再增加）
        "external_income": 0,  # 累计外部收入
        "total_spent": 0,      # 累计支出
        "log": []
    }

def _save(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_balance():
    """金库当前余额"""
    return _load()["balance"]

def deposit(amount, source="external"):
    """外部收入存入金库"""
    data = _load()
    data["balance"] += amount
    data["external_income"] += amount
    data["log"].append({
        "type": "deposit",
        "amount": amount,
        "source": source,
        "time": datetime.now().isoformat(),
        "balance_after": data["balance"]
    })
    _save(data)
    return data["balance"]

def withdraw(amount, purpose="needs"):
    """从金库支出（发放基础需求奖励等）"""
    data = _load()
    if data["balance"] < amount:
        return None  # 金库空了，发不出钱
    data["balance"] -= amount
    data["total_spent"] += amount
    data["log"].append({
        "type": "withdraw",
        "amount": amount,
        "purpose": purpose,
        "time": datetime.now().isoformat(),
        "balance_after": data["balance"]
    })
    _save(data)
    return data["balance"]

def get_status():
    """金库状态概览"""
    data = _load()
    days_left = data["balance"] / 25 if data["balance"] > 0 else 0  # 5居民*5token/天
    return {
        "balance": data["balance"],
        "external_income": data["external_income"],
        "total_spent": data["total_spent"],
        "days_left": round(days_left, 1),
        "healthy": data["balance"] > 50
    }
