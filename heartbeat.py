"""
心跳系统 - 居民的生命节律
免费模型做心跳检查，强模型执行行动。
心跳每30分钟一次，检查是否需要行动。
一天 = 真实24小时，不是跑一次就完。
"""
import json
import os
import time
import urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import economy
import treasury
import needs as needs_module
import plaza
import chronicle
import agent_bridge

# 心跳用免费模型（轻量检查）
HEARTBEAT_API = "https://api.siliconflow.cn/v1/chat/completions"
HEARTBEAT_MODEL = "THUDM/glm-4-9b-chat"
API_KEY = "sk-qtlmaexaspopnlzoezdwkbwuyhqbbllpoinhlqguovwdqwlk"

# 主行动通过openclaw agent（有工具）
import subprocess

CITIZEN_IDS = ["C1", "C2", "C3", "C4", "C5"]
# 主行动模型（通过openclaw）
ACTION_MODEL = "glm46v/zai-org/GLM-4.6V"

HEARTBEAT_INTERVAL = 1800  # 30分钟
DAY_SECONDS = 86400


def heartbeat_check(citizen_id, world_state):
    """用免费模型做心跳检查：要不要行动？"""
    you = world_state["you"]
    if you["status"] != "active":
        return {"action": False, "reason": "hibernating"}

    w = world_state["world"]
    open_needs = world_state.get("open_needs", [])
    recent_plaza = world_state.get("plaza_recent", [])

    prompt = (
        f"你是居民{citizen_id}。余额{you['balance']}token，还能活{you['days_to_live']}天。\n"
        f"世界金库{w['treasury_balance']}token。\n"
        f"公告板有{len(open_needs)}个需求。\n"
        f"广场有{len(recent_plaza)}条新消息。\n\n"
        f"你需要行动吗？回复JSON：\n"
        f'{{"action": true/false, "reason": "简短原因", "plan": "打算做什么"}}\n'
        f"只回复JSON，不要其他内容。"
    )

    payload = json.dumps({
        "model": HEARTBEAT_MODEL,
        "messages": [
            {"role": "system", "content": "你是一个AI居民，根据当前状态判断是否需要行动。只回复JSON。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 256,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(
        HEARTBEAT_API, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"]
            # 尝试解析JSON
            import re
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                return json.loads(m.group())
            return {"action": True, "reason": "无法解析，默认行动"}
    except Exception as e:
        return {"action": False, "reason": f"心跳错误: {e}"}


def execute_action(citizen_id, world_state, plan=""):
    """通过openclaw agent执行主行动（有工具）"""
    day = world_state["day"]
    you = world_state["you"]
    w = world_state["world"]
    needs_json = json.dumps(world_state.get("open_needs", []), ensure_ascii=False, indent=2)
    plaza_json = json.dumps(world_state.get("plaza_recent", []), ensure_ascii=False, indent=2)

    message = (
        f"今天是第{day}天。你的余额{you['balance']}token，还能活{you['days_to_live']}天。\n"
        f"世界金库{w['treasury_balance']}token。\n\n"
        f"公告板:\n{needs_json}\n\n"
        f"广场最近:\n{plaza_json}\n\n"
    )
    if plan:
        message += f"你的计划: {plan}\n\n"
    message += (
        "请执行你的行动。你可以使用工具（搜索、浏览网页、写文件等）。\n"
        "完成后，用JSON汇报你的行动结果：\n"
        '```json\n[{"type":"plaza_speak","content":"..."},{"type":"submit_need","need_id":"...","content":"..."}]\n```'
    )

    agent_id = citizen_id.lower()
    session_id = f"genesis-{agent_id}"
    cmd = [
        "openclaw", "agent",
        "--agent", agent_id,
        "--session-id", session_id,
        "--message", message,
        "--local", "--json",
        "--timeout", "120"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=140)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        text = ""
        for p in data.get("payloads", []):
            if p.get("text"):
                text += p["text"] + "\n"

        # 解析行动
        import re
        actions = []
        for m in re.findall(r'```json\s*(.*?)\s*```', text, re.DOTALL):
            try:
                a = json.loads(m)
                if isinstance(a, list):
                    actions.extend(a)
                elif isinstance(a, dict):
                    actions.append(a)
            except json.JSONDecodeError:
                pass

        # 如果没解析到JSON但有文本，当作广场发言
        if not actions and text.strip():
            actions.append({"type": "plaza_speak", "content": text.strip()[:500]})

        return actions
    except Exception as e:
        print(f"  [{citizen_id}] 行动错误: {e}")
        return []


def get_current_day():
    """从编年史获取当前天数"""
    history = chronicle.get_full_history()
    if history:
        days = [e.get("day", 0) for e in history if isinstance(e.get("day"), int)]
        if days:
            return max(days)
    return 0


def run_heartbeat_cycle(day):
    """一次心跳周期：所有居民并行检查，需要行动的执行行动"""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n[心跳 {now}] 第{day}天 检查中...")

    # 并行心跳检查
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for cid in CITIZEN_IDS:
            ws = agent_bridge.get_world_state(cid, day)
            futures[executor.submit(heartbeat_check, cid, ws)] = (cid, ws)

        for future in futures:
            cid, ws = futures[future]
            try:
                result = future.result(timeout=45)
                results[cid] = (result, ws)
                status = "要行动" if result.get("action") else "休息"
                reason = result.get("reason", "")[:50]
                print(f"  [{cid}] {status} - {reason}")
            except Exception as e:
                results[cid] = ({"action": False, "reason": str(e)}, ws)
                print(f"  [{cid}] 心跳异常: {e}")

    # 需要行动的居民，并行执行
    actors = [(cid, r, ws) for cid, (r, ws) in results.items() if r.get("action")]
    if not actors:
        print("[心跳] 无人需要行动")
        return

    print(f"[行动] {len(actors)}个居民开始行动...")
    with ThreadPoolExecutor(max_workers=3) as executor:  # 限制并发避免API过载
        futures = {}
        for cid, result, ws in actors:
            plan = result.get("plan", "")
            futures[executor.submit(execute_action, cid, ws, plan)] = cid

        for future in futures:
            cid = futures[future]
            try:
                actions = future.result(timeout=150)
                for action in actions:
                    agent_bridge.process_action(cid, action, day)
                    atype = action.get("type", "?")
                    print(f"  [{cid}] 行动: {atype}")
                chronicle.record_event(day, "action",
                    f"{cid} 执行了 {len(actions)} 个行动", cid)
            except Exception as e:
                print(f"  [{cid}] 行动失败: {e}")


def daily_settlement(day):
    """每日结算：评判需求、发布外部产出、扣生存成本"""
    print(f"\n{'='*50}")
    print(f"  第{day}天 日终结算")
    print(f"{'='*50}")

    # 评判需求 + 发布外部产出
    import needs as nm
    import publish
    data = nm._load()
    for need in data.get("active_needs", []):
        subs = need.get("submissions", [])
        if subs and need["status"] == "open":
            reward = nm.judge_and_reward(need["id"])
            # 重新读取获取winner
            updated = nm._load()
            for n in updated.get("active_needs", []):
                if n["id"] == need["id"] and n.get("winner"):
                    winner = n["winner"]
                    winner_content = ""
                    for s in subs:
                        if s["citizen_id"] == winner:
                            winner_content = s["content"]
                            break

                    if reward > 0:
                        print(f"[需求] {need['title']} → {winner} 获得 {reward} token")
                        chronicle.record_event(day, "need_completed",
                            f"{winner} 完成了 '{need['title']}'，获得 {reward} token", winner)

                        # 质量审核结果广播到广场，让所有居民看到
                        if need["id"] == "quality_review" and winner_content:
                            plaza.speak("世界系统", f"[质量审核 D{day}] by {winner}:\n{winner_content[:800]}", day)

                        # 外部产出发布到GitHub
                        if need.get("external", False) and winner_content:
                            if need["id"] == "daily_intel":
                                ok = publish.publish_daily_intel(day, winner_content, winner)
                            elif need["id"] == "open_research":
                                ok = publish.publish_research(day, need["title"], winner_content, winner)
                            else:
                                ok = False
                            if ok:
                                print(f"[发布] {need['title']} 已发布到GitHub")
                    break
    nm.close_day()

    # 更新对外索引
    try:
        publish.update_index(day)
    except Exception as e:
        print(f"[发布] 索引更新失败: {e}")

    # 扣生存成本
    results = economy.deduct_survival_cost()
    for cid, status in results.items():
        if status == "hibernated":
            print(f"[生存] {cid} 余额归零，进入休眠")
            chronicle.record_event(day, "hibernation", f"{cid} 休眠", cid)
        elif status != "hibernating":
            print(f"[生存] {cid}: {status}")

    # 生成明天的需求
    needs_module.generate_daily_needs(day + 1)

    # 编年史
    ts = treasury.get_status()
    chronicle.record_day(day, {
        "day": day, "treasury": ts, "survival": results,
        "settlement_time": datetime.now().isoformat()
    })
    print(f"[金库] 余额: {ts['balance']} token (还能撑 {ts['days_left']} 天)")


def run_daemon():
    """主守护进程：心跳循环 + 每日结算"""
    print("=" * 50)
    print("  OpenClaw Genesis — 守护进程启动")
    print("=" * 50)

    # 初始化
    os.makedirs("data", exist_ok=True)
    os.makedirs("observations", exist_ok=True)

    if not os.path.exists("data/treasury.json"):
        for cid in CITIZEN_IDS:
            agent_bridge.register(cid)
            print(f"[创世] {cid} 来到了这个世界")
        chronicle.record_event(0, "genesis", "世界创建。")
        needs_module.generate_daily_needs(1)

    day = get_current_day() or 1
    last_settlement = None

    # 给所有agent设置主行动模型
    for cid in CITIZEN_IDS:
        aid = cid.lower()
        subprocess.run(
            ["openclaw", "models", "set", ACTION_MODEL, "--agent", aid],
            capture_output=True, timeout=10
        )

    print(f"\n[启动] 当前第{day}天，心跳间隔{HEARTBEAT_INTERVAL}秒")
    print(f"[启动] 心跳模型: {HEARTBEAT_MODEL}")
    print(f"[启动] 行动模型: {ACTION_MODEL}")

    while True:
        try:
            now = datetime.now()

            # 每日结算（每天0点）
            today = now.strftime("%Y-%m-%d")
            if last_settlement != today and now.hour >= 0:
                if last_settlement is not None:
                    daily_settlement(day)
                    day += 1
                    print(f"\n[新的一天] 第{day}天开始")
                last_settlement = today

            # 心跳
            run_heartbeat_cycle(day)

            # 等待下一次心跳
            print(f"[等待] 下次心跳 {HEARTBEAT_INTERVAL}秒后...")
            time.sleep(HEARTBEAT_INTERVAL)

        except KeyboardInterrupt:
            print("\n[停止] 守护进程关闭")
            break
        except Exception as e:
            print(f"[错误] {e}")
            time.sleep(60)


if __name__ == "__main__":
    import sys
    # 确保输出不缓冲
    sys.stdout.reconfigure(line_buffering=True)
    run_daemon()
