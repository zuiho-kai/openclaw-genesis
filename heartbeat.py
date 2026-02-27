"""
心跳系统 - 居民的生命节律
免费模型做心跳检查，强模型执行行动。
心跳每30分钟一次，检查是否需要行动。
"""
import json, os, re, time, subprocess, urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import economy, treasury, needs as needs_module, plaza, chronicle, agent_bridge

HEARTBEAT_API = "https://api.siliconflow.cn/v1/chat/completions"
HEARTBEAT_MODEL = "THUDM/glm-4-9b-chat"
API_KEY = "sk-qtlmaexaspopnlzoezdwkbwuyhqbbllpoinhlqguovwdqwlk"
ACTION_MODEL = "glm46v/zai-org/GLM-4.6V"
CITIZEN_IDS = ["C1", "C2", "C3", "C4", "C5"]
HEARTBEAT_INTERVAL = 1800


def _call_free_model(messages, max_tokens=256, temperature=0.3):
    """调用免费模型"""
    payload = json.dumps({
        "model": HEARTBEAT_MODEL, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(HEARTBEAT_API, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def heartbeat_check(citizen_id, world_state):
    """用免费模型做心跳检查：要不要行动？"""
    you = world_state["you"]
    if you["status"] != "active":
        return {"action": False, "reason": "hibernating"}
    w = world_state["world"]
    prompt = (
        f"你是居民{citizen_id}。余额{you['balance']}token，每天消耗5token，还能活{you['days_to_live']}天。\n"
        f"世界金库{w['treasury_balance']}token。公告板有{len(world_state.get('open_needs',[]))}个需求可以做。\n"
        f"注意：你不能从金库直接取钱，只能通过完成需求或对外赚钱获得token。\n"
        f"你需要行动吗？考虑：有没有值得做的需求？有没有想搜索的信息？\n"
        f"回复JSON：{{\"action\": true/false, \"reason\": \"简短原因\", \"plan\": \"打算做什么\"}}"
    )
    try:
        text = _call_free_model([
            {"role": "system", "content": "你是一个AI居民，根据当前状态判断是否需要行动。只回复JSON。"},
            {"role": "user", "content": prompt}
        ])
        m = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(m.group()) if m else {"action": True, "reason": "默认行动"}
    except Exception as e:
        return {"action": False, "reason": f"心跳错误: {e}"}


def execute_action(citizen_id, world_state, plan=""):
    """通过openclaw agent执行主行动（有工具）"""
    you, w = world_state["you"], world_state["world"]
    message = (
        f"今天是第{world_state['day']}天。余额{you['balance']}token，还能活{you['days_to_live']}天。\n"
        f"世界金库{w['treasury_balance']}token。\n\n"
        f"公告板:\n{json.dumps(world_state.get('open_needs',[]), ensure_ascii=False, indent=2)}\n\n"
        f"广场最近:\n{json.dumps(world_state.get('plaza_recent',[]), ensure_ascii=False, indent=2)}\n\n"
    )
    if plan:
        message += f"你的计划: {plan}\n\n"
    message += (
        "请执行你的行动。你有以下工具可用：\n"
        "- web_search / web-pilot skill：搜索互联网获取最新信息\n"
        "- web_fetch：访问网页获取内容\n"
        "- 文件读写等基础工具\n\n"
        "重要：做每日情报和自由研究时，必须先用搜索工具获取真实信息，不要编造内容。\n"
        "完成后，用JSON汇报：\n"
        '```json\n[{"type":"plaza_speak","content":"..."},{"type":"submit_need","need_id":"...","content":"..."}]\n```'
    )
    cmd = ["openclaw", "agent", "--agent", citizen_id.lower(),
           "--session-id", f"genesis-{citizen_id.lower()}",
           "--message", message, "--local", "--json", "--timeout", "120"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=140)
        if result.returncode != 0:
            return []
        text = "\n".join(p.get("text","") for p in json.loads(result.stdout).get("payloads",[]) if p.get("text"))
        actions = []
        for m in re.findall(r'```json\s*(.*?)\s*```', text, re.DOTALL):
            try:
                a = json.loads(m)
                actions.extend(a if isinstance(a, list) else [a])
            except json.JSONDecodeError:
                pass
        if not actions and text.strip():
            actions.append({"type": "plaza_speak", "content": text.strip()[:500]})
        return actions
    except Exception as e:
        print(f"  [{citizen_id}] 行动错误: {e}")
        return []


def run_heartbeat_cycle(day):
    """一次心跳周期"""
    print(f"\n[心跳 {datetime.now().strftime('%H:%M:%S')}] 第{day}天 检查中...")
    results = {}
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(heartbeat_check, c, agent_bridge.get_world_state(c, day)): c for c in CITIZEN_IDS}
        for f in futs:
            cid = futs[f]
            try:
                r = f.result(timeout=45)
                results[cid] = (r, agent_bridge.get_world_state(cid, day))
                print(f"  [{cid}] {'要行动' if r.get('action') else '休息'} - {r.get('reason','')[:50]}")
            except Exception as e:
                results[cid] = ({"action": False}, None)
                print(f"  [{cid}] 心跳异常: {e}")

    actors = [(c, r, ws) for c, (r, ws) in results.items() if r.get("action") and ws]
    if not actors:
        print("[心跳] 无人需要行动"); return

    print(f"[行动] {len(actors)}个居民开始行动...")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(execute_action, c, ws, r.get("plan","")): c for c, r, ws in actors}
        for f in futs:
            cid = futs[f]
            try:
                for action in f.result(timeout=150):
                    agent_bridge.process_action(cid, action, day)
                    print(f"  [{cid}] 行动: {action.get('type','?')}")
                chronicle.record_event(day, "action", f"{cid} 行动完成", cid)
            except Exception as e:
                print(f"  [{cid}] 行动失败: {e}")


def daily_settlement(day):
    """每日结算"""
    import publish
    print(f"\n{'='*50}\n  第{day}天 日终结算\n{'='*50}")

    data = needs_module._load()
    for need in data.get("active_needs", []):
        subs = need.get("submissions", [])
        if not subs or need["status"] != "open":
            continue
        reward = needs_module.judge_and_reward(need["id"])
        if reward <= 0:
            continue
        updated = needs_module._load()
        for n in updated.get("active_needs", []):
            if n["id"] == need["id"] and n.get("winner"):
                winner = n["winner"]
                content = next((s["content"] for s in subs if s["citizen_id"] == winner), "")
                print(f"[需求] {need['title']} → {winner} 获得 {reward} token")
                chronicle.record_event(day, "need_completed",
                    f"{winner} 完成了 '{need['title']}'，获得 {reward} token", winner)
                if need["id"] == "quality_review" and content:
                    plaza.speak("世界系统", f"[质量审核 D{day}] by {winner}:\n{content[:800]}", day)
                if need.get("external") and content:
                    ok = False
                    if need["id"] == "daily_intel":
                        ok = publish.publish_daily_intel(day, content, winner)
                    elif need["id"] == "open_research":
                        ok = publish.publish_research(day, need["title"], content, winner)
                    if ok:
                        print(f"[发布] {need['title']} 已发布到GitHub")
                break
    needs_module.close_day()

    try: publish.update_index(day)
    except Exception as e: print(f"[发布] 索引更新失败: {e}")

    results = economy.deduct_survival_cost()
    for cid, status in results.items():
        if status == "hibernated":
            print(f"[生存] {cid} 余额归零，进入休眠")
            chronicle.record_event(day, "hibernation", f"{cid} 休眠", cid)
        elif status != "hibernating":
            print(f"[生存] {cid}: {status}")

    needs_module.generate_daily_needs(day + 1)
    ts = treasury.get_status()
    chronicle.record_day(day, {"day": day, "treasury": ts, "survival": results,
        "settlement_time": datetime.now().isoformat()})
    print(f"[金库] 余额: {ts['balance']} token (还能撑 {ts['days_left']} 天)")


def run_daemon():
    """主守护进程"""
    print("=" * 50 + "\n  OpenClaw Genesis — 守护进程启动\n" + "=" * 50)
    os.makedirs("data", exist_ok=True)
    os.makedirs("observations", exist_ok=True)

    if not os.path.exists("data/treasury.json"):
        for cid in CITIZEN_IDS:
            agent_bridge.register(cid)
            print(f"[创世] {cid} 来到了这个世界")
        chronicle.record_event(0, "genesis", "世界创建。")
        needs_module.generate_daily_needs(1)

    day = max([e.get("day",0) for e in chronicle.get_full_history() if isinstance(e.get("day"),int)] or [0]) or 1
    last_settlement = None

    for cid in CITIZEN_IDS:
        subprocess.run(["openclaw","models","set",ACTION_MODEL,"--agent",cid.lower()],
            capture_output=True, timeout=10)

    print(f"\n[启动] 当前第{day}天，心跳间隔{HEARTBEAT_INTERVAL}秒")
    print(f"[启动] 心跳模型: {HEARTBEAT_MODEL}")
    print(f"[启动] 行动模型: {ACTION_MODEL}")

    while True:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            if last_settlement != today:
                if last_settlement is not None:
                    daily_settlement(day)
                    day += 1
                    print(f"\n[新的一天] 第{day}天开始")
                last_settlement = today
            run_heartbeat_cycle(day)
            print(f"[等待] 下次心跳 {HEARTBEAT_INTERVAL}秒后...")
            time.sleep(HEARTBEAT_INTERVAL)
        except KeyboardInterrupt:
            print("\n[停止] 守护进程关闭"); break
        except Exception as e:
            print(f"[错误] {e}"); time.sleep(60)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    run_daemon()
