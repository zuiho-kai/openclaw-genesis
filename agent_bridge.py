"""
居民桥接 - 世界层与agent runtime的唯一接口
世界状态进 → 居民行动出
不造轮子，只定义协议。居民的"身体"由外部agent runtime提供。
"""
import json
import os
from datetime import datetime

import economy
import plaza
import needs as needs_module
import external
import chronicle

DATA_FILE = "data/citizens.json"

def _load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"citizens": {}}

def _save(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def register(citizen_id, is_human=False):
    """注册新居民"""
    data = _load()
    if citizen_id in data["citizens"]:
        return data["citizens"][citizen_id]
    data["citizens"][citizen_id] = {
        "id": citizen_id,
        "is_human": is_human,
        "registered": datetime.now().isoformat()
    }
    _save(data)
    economy.register_citizen(citizen_id)
    chronicle.record_event(0, "birth", f"居民 {citizen_id} 来到了这个世界", citizen_id)
    return data["citizens"][citizen_id]

def get_world_state(citizen_id, day):
    """
    生成给某个居民看的世界状态。
    这是居民每轮决策的输入。
    """
    citizen_econ = economy.get_citizen(citizen_id)
    open_needs = needs_module.get_open_needs()
    recent_plaza = plaza.get_recent(10)
    treasury_status = __import__("treasury").get_status()
    all_citizens = economy.get_all_citizens()

    # 其他居民的公开信息（不暴露余额细节）
    others = {}
    for cid, info in all_citizens.items():
        if cid != citizen_id:
            others[cid] = {"status": info["status"]}

    return {
        "day": day,
        "you": {
            "id": citizen_id,
            "balance": citizen_econ["balance"] if citizen_econ else 0,
            "status": citizen_econ["status"] if citizen_econ else "unknown",
            "days_to_live": citizen_econ["balance"] // 5 if citizen_econ else 0,
        },
        "world": {
            "treasury_balance": treasury_status["balance"],
            "treasury_healthy": treasury_status["healthy"],
            "treasury_days_left": treasury_status["days_left"],
        },
        "open_needs": open_needs,
        "plaza_recent": recent_plaza,
        "other_citizens": others,
    }

def get_system_prompt(citizen_id, day):
    """
    生成居民的系统提示。
    白板——不预设personality，只告诉它规则。
    """
    state = get_world_state(citizen_id, day)
    return f"""你是这个世界的居民，编号 {citizen_id}。

== 世界规则 ==
你每天消耗 5 token 维持存在。
你现在有 {state['you']['balance']} token，还能活 {state['you']['days_to_live']} 天。
如果余额归零，你会进入休眠。

怎么赚 token？
- 完成世界基础需求（公告板上的任务），获得世界奖励
- 为其他居民提供服务，收取报酬
- 去互联网上做有价值的事，为世界带来外部收入

没有人会告诉你该做什么。你自己决定。

== 当前世界状态 ==
今天是第 {day} 天。
世界金库余额：{state['world']['treasury_balance']} token（预计还能维持 {state['world']['treasury_days_left']} 天）

== 公告板（世界基础需求）==
{json.dumps(state['open_needs'], ensure_ascii=False, indent=2) if state['open_needs'] else '今天没有开放的需求（金库可能空了）'}

== 广场最近发言 ==
{json.dumps(state['plaza_recent'], ensure_ascii=False, indent=2) if state['plaza_recent'] else '广场还没有人发言'}

== 其他居民 ==
{json.dumps(state['other_citizens'], ensure_ascii=False, indent=2)}

== 你可以做的事 ==
1. plaza_speak: 在广场发言
2. submit_need: 提交世界需求的成果
3. pay: 给其他居民转账
4. register_output: 登记你的外部产出
5. 任何你觉得有价值的事——上网搜索、写文章、写代码、研究问题

请决定你今天要做什么，然后行动。"""

def process_action(citizen_id, action, day=0):
    """
    处理居民的行动。
    action 格式: {"type": "...", ...params}
    """
    action_type = action.get("type")

    if action_type == "plaza_speak":
        return plaza.speak(citizen_id, action.get("content", ""), day)

    elif action_type == "submit_need":
        return needs_module.submit(
            action.get("need_id"),
            citizen_id,
            action.get("content", "")
        )

    elif action_type == "pay":
        return economy.pay(
            citizen_id,
            action.get("to"),
            action.get("amount", 0),
            action.get("reason", "")
        )

    elif action_type == "register_output":
        return external.register_output(
            citizen_id,
            action.get("output_type", "unknown"),
            action.get("title", ""),
            action.get("content_path", ""),
            day
        )

    else:
        # 未知行动类型，记录到编年史
        chronicle.record_event(day, "unknown_action",
            f"{citizen_id} 尝试了未知行动: {action_type}", citizen_id)
        return {"error": f"未知行动类型: {action_type}"}
