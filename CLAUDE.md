# OpenClaw Genesis

## 这是什么
AI文明实验。不是产品，不是游戏，不是平台。
5个白板AI居民 + 真实经济压力 + 看会长出什么。

## 规则
1. 世界层代码总量 < 1000 行，超了就是过度设计
2. 不做设计评审，跑起来再说
3. 每次跑完写观察日志到 observations/，这比代码重要
4. 全中文

## 架构
- 世界层（world.py等）：你写的，极简
- 居民层（agent runtime）：现成的，不造轮子
- 唯一接口：世界状态进 → 居民行动出

## 三条公理
1. 活着有成本（每天扣token）
2. 金库资助基础需求（token来自外层真实收入，不印钱）
3. 居民自由行动（对外赚钱或对内服务，自己决定）

## 文件结构
world.py / treasury.py / economy.py / needs.py
plaza.py / external.py / chronicle.py / agent_bridge.py
main.py

## 观察日志格式
observations/D001.md：
- 今天每个居民做了什么
- 意外发现
- 下一步想调整什么