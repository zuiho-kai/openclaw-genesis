"""
OpenClaw Genesis — 入口
创世纪：5个白板AI + 500 token种子基金 + 看会长出什么。
"""
import os
import sys
import json
import io
from datetime import datetime

# Windows终端中文支持
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import world
import treasury
import economy
import agent_bridge
import chronicle

# 5个白板居民，没有名字没有personality
CITIZEN_IDS = ["C1", "C2", "C3", "C4", "C5"]

def init_world():
    """创世纪 — 只跑一次"""
    print("=" * 50)
    print("  OpenClaw Genesis — 创世纪")
    print("=" * 50)

    # 确保data目录存在
    os.makedirs("data", exist_ok=True)
    os.makedirs("observations", exist_ok=True)

    # 检查是否已经初始化过
    if os.path.exists("data/treasury.json"):
        print("[世界] 已存在，跳过初始化")
        return

    # 注册居民（每人50 token初始余额，从种子基金扣）
    for cid in CITIZEN_IDS:
        agent_bridge.register(cid)
        print(f"[创世] 居民 {cid} 来到了这个世界")

    print(f"\n[金库] 种子基金: {treasury.get_balance()} token")
    print(f"[金库] 预计维持: {treasury.get_status()['days_left']} 天")
    print()

    chronicle.record_event(0, "genesis", "世界创建。5个白板居民，500 token种子基金。")

def dummy_agent_callback(citizen_id, system_prompt, world_state):
    """
    占位用的agent回调。
    真正跑的时候替换成实际的LLM调用。
    """
    # 打印居民看到的世界状态摘要
    you = world_state["you"]
    print(f"  余额: {you['balance']} token, 还能活 {you['days_to_live']} 天")

    # 占位行动：在广场打个招呼
    return [
        {
            "type": "plaza_speak",
            "content": f"我是 {citizen_id}，这是我在这个世界的第一天。我需要想想怎么活下去。"
        }
    ]

def run(days=1, agent_callback=None):
    """跑指定天数"""
    if agent_callback is None:
        agent_callback = dummy_agent_callback

    init_world()

    # 读取当前天数
    chronicle_data = chronicle.get_full_history()
    current_day = 1
    if chronicle_data:
        days_recorded = [e.get("day", 0) for e in chronicle_data if isinstance(e.get("day"), int)]
        if days_recorded:
            current_day = max(days_recorded) + 1

    for d in range(current_day, current_day + days):
        summary = world.run_day(d, CITIZEN_IDS, agent_callback)

        # 检查是否全灭
        all_hibernating = all(
            economy.get_citizen(cid) and economy.get_citizen(cid)["status"] == "hibernating"
            for cid in CITIZEN_IDS
        )
        if all_hibernating:
            print("\n[世界] 所有居民已休眠。世界陷入沉寂。")
            chronicle.record_event(d, "extinction", "所有居民休眠，世界沉寂。")
            break

    print("\n[完毕] 运行结束。记得写观察日志到 observations/ 目录。")

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(days=days)
