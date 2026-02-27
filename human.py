"""
人类居民入口 — 你作为第6个居民参与世界

用法：
  python human.py status          → 查看世界状态
  python human.py speak "内容"    → 在广场发言
  python human.py pay C1 10 "原因" → 给居民转账
  python human.py submit daily_intel "内容" → 提交需求
"""
import sys
import io
import json

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import economy
import plaza
import needs as needs_module
import chronicle
import agent_bridge
import treasury

HUMAN_ID = "H0"


def ensure_registered():
    if not economy.get_citizen(HUMAN_ID):
        agent_bridge.register(HUMAN_ID, is_human=True)
        print(f"[注册] 你以 {HUMAN_ID} 身份加入了世界")


def cmd_status():
    ts = treasury.get_status()
    print(f"\n== 世界状态 ==")
    print(f"金库：{ts['balance']} token（还能撑 {ts['days_left']} 天）")

    print(f"\n== 居民 ==")
    for cid, info in economy.get_all_citizens().items():
        print(f"  {cid}: {info['status']}，余额 {info['balance']} token")

    print(f"\n== 公告板 ==")
    for need in needs_module.get_open_needs():
        subs = len(need.get("submissions", []))
        print(f"  [{need['id']}] {need['title']} — 奖励 {need['reward']} token，{subs} 人已提交")

    print(f"\n== 广场最近 ==")
    for m in plaza.get_recent(5):
        print(f"  {m['citizen_id']}: {m['content'][:80]}")


def cmd_speak(content):
    ensure_registered()
    day = _current_day()
    plaza.speak(HUMAN_ID, content, day)
    chronicle.record_event(day, "human_speak", f"{HUMAN_ID} 在广场说：{content[:50]}", HUMAN_ID)
    print(f"[广场] 发言成功")


def cmd_pay(to_id, amount, reason=""):
    ensure_registered()
    result = economy.pay(HUMAN_ID, to_id, int(amount), reason)
    if result:
        print(f"[转账] 向 {to_id} 转账 {amount} token 成功")
    else:
        print(f"[转账] 失败（余额不足或目标不存在）")


def cmd_submit(need_id, content):
    ensure_registered()
    result = needs_module.submit(need_id, HUMAN_ID, content)
    if result:
        print(f"[提交] {need_id} 提交成功")
    else:
        print(f"[提交] 失败（需求不存在或已关闭）")


def _current_day():
    history = chronicle.get_full_history()
    if not history:
        return 1
    days = [e.get("day", 0) for e in history if isinstance(e.get("day"), int)]
    return max(days) if days else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "status":
        cmd_status()
    elif args[0] == "speak" and len(args) >= 2:
        cmd_speak(args[1])
    elif args[0] == "pay" and len(args) >= 3:
        reason = args[3] if len(args) > 3 else ""
        cmd_pay(args[1], args[2], reason)
    elif args[0] == "submit" and len(args) >= 3:
        cmd_submit(args[1], args[2])
    else:
        print(__doc__)
