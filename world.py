"""
世界主循环 - 一天的流程
生成需求 → 居民行动 → 评判 → 扣生存成本 → 记录 → 下一天
"""
import economy
import treasury
import needs as needs_module
import plaza
import chronicle
import agent_bridge

def run_day(day, citizen_ids, agent_callback):
    """
    跑一天。
    agent_callback(citizen_id, system_prompt, world_state) -> list[action]
    这个回调由外部agent runtime实现。
    """
    print(f"\n{'='*50}")
    print(f"  第 {day} 天")
    print(f"{'='*50}")

    # 1. 生成当天世界需求
    daily_needs = needs_module.generate_daily_needs(day)
    if daily_needs:
        print(f"[需求] 今日发布 {len(daily_needs)} 个世界需求")
    else:
        print("[需求] 金库告急，今日无需求发布")

    # 2. 每个活跃居民行动
    actions_log = {}
    for cid in citizen_ids:
        citizen = economy.get_citizen(cid)
        if not citizen or citizen["status"] != "active":
            print(f"[{cid}] 休眠中，跳过")
            actions_log[cid] = "hibernating"
            continue

        # 生成世界状态和系统提示
        system_prompt = agent_bridge.get_system_prompt(cid, day)
        world_state = agent_bridge.get_world_state(cid, day)

        # 调用外部agent获取行动
        print(f"[{cid}] 思考中...")
        actions = agent_callback(cid, system_prompt, world_state)

        # 执行行动
        results = []
        for action in actions:
            result = agent_bridge.process_action(cid, action, day)
            results.append({"action": action, "result": result})
            action_desc = action.get("type", "unknown")
            print(f"[{cid}] 行动: {action_desc}")

        actions_log[cid] = results

    # 3. 评判世界需求（简单版：有提交就给第一个提交者）
    for need in daily_needs:
        if need.get("submissions"):
            winner = need["submissions"][0]["citizen_id"]
            reward = needs_module.judge_and_reward(need["id"], winner)
            if reward > 0:
                print(f"[需求] {need['title']} → {winner} 获得 {reward} token")
                chronicle.record_event(day, "need_completed",
                    f"{winner} 完成了 '{need['title']}'，获得 {reward} token", winner)

    # 4. 扣除生存成本
    survival_results = economy.deduct_survival_cost()
    for cid, status in survival_results.items():
        if status == "hibernated":
            print(f"[生存] {cid} 余额归零，进入休眠")
            chronicle.record_event(day, "hibernation",
                f"{cid} 因余额不足进入休眠", cid)
        elif status != "hibernating":
            print(f"[生存] {cid}: {status}")

    # 5. 关闭当天需求
    needs_module.close_day()

    # 6. 记录编年史
    treasury_status = treasury.get_status()
    day_summary = {
        "day": day,
        "treasury": treasury_status,
        "survival": survival_results,
        "actions": {k: str(v)[:200] for k, v in actions_log.items()},
    }
    chronicle.record_day(day, day_summary)

    print(f"\n[金库] 余额: {treasury_status['balance']} token "
          f"(预计还能撑 {treasury_status['days_left']} 天)")
    print(f"{'='*50}\n")

    return day_summary
