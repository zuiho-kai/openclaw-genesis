"""
居民桥接 - 世界层与OpenClaw agent的唯一接口

设计原则：
  1. 每个居民 = 一个已存在的OpenClaw agent实例
  2. 世界规则写在SOUL.md里（一次性），每天只传动态状态
  3. agent自带工具（搜索/浏览器/文件系统），世界层不管它怎么干活
  4. agent返回结构化行动JSON，世界层执行
  5. session持续 → agent有跨天记忆
"""
import json
import os
import subprocess
import re
from datetime import datetime

import economy
import plaza
import needs as needs_module
import external
import chronicle

# ============================================================
# 配置
# ============================================================

AGENT_MAP = {
    "C1": "c1", "C2": "c2", "C3": "c3", "C4": "c4", "C5": "c5",
}
SESSION_PREFIX = "genesis"
ACTION_TIMEOUT = 120

# ============================================================
# SOUL.md（一次性写入每个agent的workspace）
# ============================================================

SOUL_TEMPLATE = """# 世界规则

你是这个世界的居民。

- 每天消耗 5 token 维持存在，余额归零你会休眠
- 没有人告诉你该做什么
- 世界金库的种子基金有限，没有外部收入金库会耗尽

# 怎么赚 token

1. 完成公告板上的世界需求（竞争制，居民投票，最优者获奖）
2. 为其他居民提供服务收取报酬
3. 对外创造价值，产出发布到外部世界（70% 归你，30% 税收进金库）

# 重要：提交需求的方法

公告板上有需求时，用 submit_need 提交。content 字段里放你的完整报告内容（不是文件路径）。
竞争制：多人可提交同一需求，其他居民投票决定谁的最好。

# 投票

第2轮起你可以看到其他人的提交内容。用 vote 行动为你认为最好的提交投票。
不能给自己投票。投票是这个世界的公民责任，也是社交行为。

# 行动格式

完成后在回复末尾用 JSON 汇报你的行动（必须用 ```json 代码块包裹）：

```json
[
  {"type": "plaza_speak", "content": "你想对其他居民说的话"},
  {"type": "submit_need", "need_id": "daily_intel", "content": "完整报告内容"},
  {"type": "vote", "need_id": "daily_intel", "candidate": "C3"},
  {"type": "pay", "to": "C2", "amount": 3, "reason": "..."},
  {"type": "register_output", "output_type": "report", "title": "...", "content_path": "..."}
]
```

重要：
- 思考过程写在JSON外面，不要把思考过程放进 plaza_speak
- plaza_speak 的 content 是你想对广场上其他居民说的话，不是你的内心独白
- 如果这轮不需要行动，回复 PASS
"""


def init_soul(citizen_id):
    """把世界规则写入 SOUL.md。"""
    # 服务器路径
    path = f"/workspace/openclaw-genesis/citizens/{citizen_id}/SOUL.md"
    # 本地 fallback
    local_paths = [
        os.path.expanduser(f"~/.openclaw/workspace-{citizen_id.lower()}/SOUL.md"),
        os.path.expanduser(f"~/.claude/agents/{citizen_id.lower()}/SOUL.md"),
        f"citizens/{citizen_id}/SOUL.md",
    ]

    target = None
    if os.path.exists(os.path.dirname(path)):
        target = path
    else:
        for p in local_paths:
            if os.path.exists(os.path.dirname(p)):
                target = p
                break

    if target:
        with open(target, "w", encoding="utf-8") as f:
            f.write(SOUL_TEMPLATE)
        print(f"[SOUL] {citizen_id} -> {target}")
        return True

    print(f"[SOUL] 警告：找不到 {citizen_id} 的workspace路径，请手动写入SOUL.md")
    return False


# ============================================================
# 世界状态 -> 消息（每天动态生成）
# ============================================================

def build_daily_message(citizen_id, day, round_num=1, total_rounds=3):
    """把当天的世界状态打包成一条消息发给agent。
    第1轮：完整状态（需求、金库、昨日事件）
    第2+轮：显示提交内容，鼓励投票和回应
    """
    citizen_econ = economy.get_citizen(citizen_id)
    if not citizen_econ or citizen_econ["status"] != "active":
        return None

    balance = citizen_econ["balance"]
    days_to_live = balance // 5

    msg = f"== 第 {day} 天，第 {round_num}/{total_rounds} 轮 ==\n\n"
    msg += f"你的状态：{balance} token，还能活 {days_to_live} 天。\n"

    # 所有轮次都需要的数据
    all_citizens = economy.get_all_citizens()
    others = {cid: info["status"] for cid, info in all_citizens.items() if cid != citizen_id}
    yesterday = [e for e in chronicle.get_full_history()
                 if isinstance(e, dict) and e.get("day") == day - 1][-10:]

    if round_num == 1:
        # 第1轮：完整世界状态
        treasury_status = __import__("treasury").get_status()
        open_needs = needs_module.get_open_needs()

        msg += f"世界金库：{treasury_status['balance']} token（预计还能维持 {treasury_status['days_left']} 天）\n"
        if not treasury_status['healthy']:
            msg += "!! 金库告急！\n"

        msg += "\n== 公告板（世界需求）==\n"
        if open_needs:
            for need in open_needs:
                subs = need.get("submissions", [])
                msg += f"- [{need['id']}] {need['title']}（奖励 {need['reward']} token，已有 {len(subs)} 人提交）\n"
                msg += f"  说明：{need['desc']}\n"
                if need["id"] == "chronicle":
                    msg += f"  提示：把今天广场上发生的事、居民行动、经济变化整理成记录，直接写在 submit_need 的 content 里。\n"
                elif need["id"] == "quality_review":
                    msg += f"  提示：根据广场发言和今日已有提交，评估各居民产出质量，给出评分和建议，写在 content 里。\n"
                elif need["id"] == "open_research":
                    msg += f"  提示：研究任何你感兴趣的主题，把报告内容直接写在 content 里提交。\n"
        else:
            msg += "今天没有开放的需求\n"

        msg += "\n== 其他居民 ==\n"
        for cid, status in others.items():
            msg += f"- {cid}: {status}\n"

        if yesterday:
            msg += "\n== 昨天发生了什么 ==\n"
            for e in yesterday:
                desc = e.get("description", str(e.get("summary", ""))[:100])
                msg += f"- {desc}\n"

    # 第2轮起显示已有提交，让居民能看到、评价、投票
    if round_num > 1:
        open_needs_now = needs_module.get_open_needs()
        has_subs = any(n.get("submissions") for n in open_needs_now)
        if has_subs:
            msg += "\n== 今日已有提交（请投票选出最好的）==\n"
            for need in open_needs_now:
                subs = need.get("submissions", [])
                if not subs:
                    msg += f"[{need['id']}] {need['title']}：无人提交\n"
                    continue
                votes = need.get("votes", {})
                msg += f"[{need['id']}] {need['title']}（{len(subs)}人提交，{len(votes)}票）：\n"
                for s in subs:
                    preview = s["content"][:300].replace("\n", " ")
                    vote_count = sum(1 for v in votes.values() if v == s["citizen_id"])
                    msg += f"  - {s['citizen_id']}（{vote_count}票）: {preview}\n"
        else:
            msg += "\n== 今日提交 ==\n还没有人提交需求\n"

        msg += "\n== 其他居民 ==\n"
        for cid, status in others.items():
            msg += f"- {cid}: {status}\n"

        if yesterday:
            msg += "\n== 昨天发生了什么 ==\n"
            for e in yesterday:
                desc = e.get("description", str(e.get("summary", ""))[:100])
                msg += f"- {desc}\n"

    # 所有轮次都显示广场最新发言
    recent_plaza = plaza.get_recent(10)
    msg += "\n== 广场最新发言 ==\n"
    if recent_plaza:
        for m in recent_plaza[-8:]:
            msg += f"- {m['citizen_id']}: {m['content'][:120]}\n"
    else:
        msg += "还没有人发言\n"

    msg += "\n== 请行动 ==\n"
    if round_num == 1:
        msg += "决定你今天要做什么。搜索信息后，用 submit_need 把报告内容直接提交到公告板任务（content字段放完整内容）。也可以在广场发言、和其他居民交易。\n"
        msg += "注意：写文件不等于提交需求。要赚token必须用 submit_need 提交。\n"
    else:
        msg += "你可以：补充提交需求、为已有提交投票（vote）、回应广场发言、交易。\n"
        msg += '投票很重要：用 {"type": "vote", "need_id": "...", "candidate": "C?"} 为你认为最好的提交投票。\n'
        msg += "如果这轮不需要行动，回复 PASS。\n"
    msg += "完成后用 ```json 代码块汇报你的行动。\n"

    return msg


# ============================================================
# 调用OpenClaw agent
# ============================================================

SESSION_FILE = "data/sessions.json"

def _load_sessions():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_session(citizen_id, session_id):
    data = _load_sessions()
    data[citizen_id] = session_id
    os.makedirs("data", exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def call_agent(citizen_id, message):
    """给居民对应的 openclaw agent 发消息，拿回回复。"""
    agent_name = AGENT_MAP.get(citizen_id)
    if not agent_name:
        return None, "未知居民"

    session_id = f"{SESSION_PREFIX}-{agent_name}"
    cmd = [
        "openclaw", "agent",
        "--agent", agent_name,
        "--session-id", session_id,
        "--message", message,
        "--local",
        "--json",
        "--timeout", str(ACTION_TIMEOUT),
    ]

    # 限制Node.js堆内存，防止OOM
    env = os.environ.copy()
    env["NODE_OPTIONS"] = "--max-old-space-size=256"

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=ACTION_TIMEOUT + 30,
            env=env,
        )
        if result.returncode != 0:
            error = result.stderr[:200] if result.stderr else "未知错误"
            print(f"  [{citizen_id}] agent返回错误: {error}")
            return None, error

        try:
            output = json.loads(result.stdout)
            texts = [p["text"] for p in output.get("payloads", []) if p.get("text")]
            return "\n".join(texts), None
        except json.JSONDecodeError:
            return result.stdout, None

    except subprocess.TimeoutExpired:
        return None, f"超时（{ACTION_TIMEOUT}秒）"
    except FileNotFoundError:
        return None, "openclaw命令未找到"
    except Exception as e:
        return None, str(e)


# ============================================================
# 解析行动 + 执行行动
# ============================================================

def extract_actions(text):
    """从agent回复中提取行动JSON。只认 ```json 块和裸JSON数组。"""
    if not text:
        return []

    actions = []
    # 第1层：找 ```json 块
    for match in re.findall(r'```json\s*(.*?)\s*```', text, re.DOTALL):
        try:
            parsed = json.loads(match)
            if isinstance(parsed, list):
                actions.extend(parsed)
            elif isinstance(parsed, dict):
                actions.append(parsed)
        except json.JSONDecodeError:
            continue

    # 第2层：找裸JSON数组
    if not actions:
        for match in re.findall(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL):
            try:
                parsed = json.loads(match)
                if isinstance(parsed, list):
                    actions.extend(parsed)
            except json.JSONDecodeError:
                continue

    # 不再降级：如果agent没返回JSON，就是没有行动
    if not actions and text.strip() and not text.strip().upper().startswith("PASS"):
        print(f"  [警告] 未提取到行动JSON，回复前80字: {text.strip()[:80]}")

    return actions


def process_action(citizen_id, action, day=0):
    """处理居民的一个行动。"""
    action_type = action.get("type")

    if action_type == "plaza_speak":
        return plaza.speak(citizen_id, action.get("content", ""), day)

    elif action_type == "submit_need":
        result = needs_module.submit(
            action.get("need_id"), citizen_id, action.get("content", "")
        )
        if result:
            chronicle.record_event(day, "submission",
                f"{citizen_id} 提交了 '{action.get('need_id')}'", citizen_id)
        return result

    elif action_type == "vote":
        result = needs_module.vote(
            action.get("need_id"), citizen_id, action.get("candidate", "")
        )
        if result:
            chronicle.record_event(day, "vote",
                f"{citizen_id} 投票给 {action.get('candidate')}（{action.get('need_id')}）", citizen_id)
        return result

    elif action_type == "pay":
        result = economy.pay(
            citizen_id, action.get("to"),
            action.get("amount", 0), action.get("reason", "")
        )
        if result:
            chronicle.record_event(day, "transaction",
                f"{citizen_id} 向 {action.get('to')} 转账 {action.get('amount')} token", citizen_id)
        return result

    elif action_type == "register_output":
        result = external.register_output(
            citizen_id, action.get("output_type", "unknown"),
            action.get("title", ""), action.get("content_path", ""), day
        )
        chronicle.record_event(day, "output",
            f"{citizen_id} 登记了外部产出: {action.get('title', '')}", citizen_id)
        return result

    else:
        chronicle.record_event(day, "unknown_action",
            f"{citizen_id} 尝试了: {action_type}", citizen_id)
        return {"error": f"未知行动: {action_type}"}


# ============================================================
# 完整的居民回合
# ============================================================

def run_citizen_turn(citizen_id, day, round_num=1, total_rounds=3):
    """一个居民的完整回合：构建消息 -> 调agent -> 提取行动 -> 执行行动。"""
    message = build_daily_message(citizen_id, day, round_num, total_rounds)
    if message is None:
        print(f"  [{citizen_id}] 休眠中，跳过")
        return []

    print(f"  [{citizen_id}] 思考中...")
    reply, error = call_agent(citizen_id, message)

    if error:
        print(f"  [{citizen_id}] 错误: {error}")
        return []

    # 居民选择跳过本轮
    if reply and reply.strip().upper().startswith("PASS"):
        print(f"  [{citizen_id}] PASS")
        return []

    actions = extract_actions(reply)
    if actions:
        print(f"  [{citizen_id}] 返回 {len(actions)} 个行动")
    else:
        print(f"  [{citizen_id}] 无有效行动")

    results = []
    for action in actions:
        result = process_action(citizen_id, action, day)
        results.append({"action": action, "result": result})
        atype = action.get("type", "?")
        if atype == "vote":
            print(f"  [{citizen_id}] 行动: vote -> {action.get('candidate')}（{action.get('need_id')}）")
        else:
            print(f"  [{citizen_id}] 行动: {atype}")

    return results


# ============================================================
# 居民注册（创世用）
# ============================================================

def register(citizen_id, is_human=False):
    """注册新居民到经济系统"""
    economy.register_citizen(citizen_id)
    if not is_human:
        init_soul(citizen_id)
    chronicle.record_event(0, "birth", f"居民 {citizen_id} 来到了这个世界", citizen_id)
    return citizen_id


# 保留兼容接口（world.py还在用）
def get_world_state(citizen_id, day):
    """兼容旧接口，返回结构化世界状态"""
    citizen_econ = economy.get_citizen(citizen_id)
    open_needs = needs_module.get_open_needs()
    recent_plaza = plaza.get_recent(10)
    treasury_status = __import__("treasury").get_status()
    all_citizens = economy.get_all_citizens()
    others = {cid: {"status": info["status"]} for cid, info in all_citizens.items() if cid != citizen_id}
    yesterday_events = [e for e in chronicle.get_full_history()
                        if isinstance(e, dict) and e.get("day") == day - 1][-10:]
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
        "yesterday_events": yesterday_events,
    }


def get_system_prompt(citizen_id, day):
    """兼容旧接口"""
    state = get_world_state(citizen_id, day)
    return build_daily_message(citizen_id, day) or ""
