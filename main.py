"""
OpenClaw Genesis — 唯一入口

用法：
  python main.py        → 跑1天
  python main.py 3      → 跑3天
  python main.py daemon → 守护进程，每天自动跑一天
"""
import os
import sys
import io
import time
from datetime import datetime, date
ROUNDS_PER_DAY = 3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import treasury
import economy
import needs as needs_module
import plaza
import chronicle
import agent_bridge
import publish
import external

CITIZEN_IDS = ["C1", "C2", "C3", "C4", "C5"]


# ============================================================
# 创世
# ============================================================

def init_world():
    """只跑一次"""
    os.makedirs("data", exist_ok=True)
    os.makedirs("observations", exist_ok=True)

    if os.path.exists("data/treasury.json"):
        return  # 已初始化

    print("=" * 50)
    print("  OpenClaw Genesis — 创世纪")
    print("=" * 50)

    for cid in CITIZEN_IDS:
        agent_bridge.register(cid)
        print(f"[创世] {cid} 来到了这个世界")

    ts = treasury.get_status()
    print(f"[金库] 种子基金: {ts['balance']} token，预计维持 {ts['days_left']} 天")
    chronicle.record_event(0, "genesis", "世界创建。5个白板居民，500 token种子基金。")
    needs_module.generate_daily_needs(1)


# ============================================================
# 一天
# ============================================================

def run_day(day):
    """跑完整的一天，返回True继续/False世界终结"""
    print(f"\n{'=' * 50}")
    print(f"  第 {day} 天")
    print(f"{'=' * 50}")

    # 1. 确保当天需求已生成
    if not needs_module.get_open_needs():
        daily_needs = needs_module.generate_daily_needs(day)
        if daily_needs:
            print(f"[需求] 发布 {len(daily_needs)} 个世界需求")
        else:
            print("[需求] 金库告急，今日无需求")

    # 2. 多轮串行行动（节省内存，且后轮居民能看到前轮发言）
    actions_log = {cid: [] for cid in CITIZEN_IDS}
    for round_num in range(1, ROUNDS_PER_DAY + 1):
        print(f"\n[第{round_num}轮/{ROUNDS_PER_DAY}]")
        for cid in CITIZEN_IDS:
            try:
                results = agent_bridge.run_citizen_turn(cid, day, round_num)
                actions_log[cid].extend(results)
            except Exception as e:
                print(f"  [{cid}] 异常: {e}")

    # 3. 评判世界需求
    print("\n[评判] 评选世界需求...")
    data = needs_module._load()
    for need in data.get("active_needs", []):
        if not need.get("submissions") or need["status"] != "open":
            continue
        reward = needs_module.judge_and_reward(need["id"])
        if reward <= 0:
            continue
        updated = needs_module._load()
        for n in updated.get("active_needs", []) + updated.get("history", []):
            if n["id"] == need["id"] and n.get("winner"):
                winner = n["winner"]
                print(f"  {need['title']} → {winner} 获得 {reward} token")
                chronicle.record_event(day, "need_completed",
                    f"{winner} 完成了 '{need['title']}'，获得 {reward} token", winner)
                if need.get("external"):
                    subs = need.get("submissions", [])
                    content = next((s["content"] for s in subs if s["citizen_id"] == winner), "")
                    if content:
                        _try_publish(day, need, content, winner)
                break

    # 4. 扣除生存成本
    print("\n[生存] 扣除每日成本...")
    survival = economy.deduct_survival_cost()
    for cid, status in survival.items():
        if status == "hibernated":
            print(f"  {cid} 余额归零，休眠")
            chronicle.record_event(day, "hibernation", f"{cid} 休眠", cid)
        elif status != "hibernating":
            print(f"  {cid}: {status}")

    # 5. 关闭当天需求 + 更新发布索引
    needs_module.close_day()
    try:
        publish.update_index(day)
    except Exception:
        pass

    # 6. 编年史
    ts = treasury.get_status()
    chronicle.record_day(day, {
        "day": day,
        "treasury": ts,
        "survival": survival,
        "actions_count": {cid: len(acts) for cid, acts in actions_log.items()},
        "time": datetime.now().isoformat(),
    })

    print(f"\n[金库] 余额: {ts['balance']} token（还能撑 {ts['days_left']} 天）")
    active = sum(1 for cid in CITIZEN_IDS
                 if economy.get_citizen(cid) and economy.get_citizen(cid)["status"] == "active")
    print(f"[人口] {active}/{len(CITIZEN_IDS)} 活跃")
    print(f"{'=' * 50}\n")

    if active == 0:
        print("[世界] 所有居民已休眠。世界陷入沉寂。")
        chronicle.record_event(day, "extinction", "所有居民休眠。")
        return False
    return True


def _try_publish(day, need, content, winner):
    """尝试发布到外部，成功给1 token外部收入"""
    try:
        ok = False
        if need["id"] == "daily_intel":
            ok = publish.publish_daily_intel(day, content, winner)
        elif need["id"] == "open_research":
            ok = publish.publish_research(day, need["title"], content, winner)
        if ok:
            print(f"  [发布] {need['title']} → GitHub Pages")
            external.record_income(1, winner, f"publish:{need['id']}")
            print(f"  [外部收入] {winner} 获得 1 token（发布奖励）")
    except Exception as e:
        print(f"  [发布] 失败: {e}")


# ============================================================
# 天数推断
# ============================================================

def get_current_day():
    history = chronicle.get_full_history()
    if not history:
        return 1
    days = [e.get("day", 0) for e in history if isinstance(e.get("day"), int)]
    return max(days) + 1 if days else 1


# ============================================================
# 入口
# ============================================================

def run_once(days=1):
    init_world()
    current_day = get_current_day()
    for d in range(current_day, current_day + days):
        if not run_day(d):
            break
    print("[完毕] 记得写观察日志到 observations/ 目录。")


def run_daemon():
    """守护进程：每天自动跑一天"""
    init_world()
    current_day = get_current_day()
    last_run_date = None

    print(f"[守护] 启动，当前第 {current_day} 天，每天自动运行一轮\n")

    while True:
        try:
            today = date.today().isoformat()
            if last_run_date != today:
                if not run_day(current_day):
                    print("[守护] 世界终结，退出")
                    break
                last_run_date = today
                current_day += 1
            print("[守护] 今日完成，等待明天...")
            time.sleep(3600)
        except KeyboardInterrupt:
            print("\n[守护] 手动停止")
            break
        except Exception as e:
            print(f"[守护] 错误: {e}")
            time.sleep(300)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        run_daemon()
    else:
        days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
        run_once(days=days)
