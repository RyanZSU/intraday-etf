# AGENTS.md

A股 ETF 日内做T（T+0）量化策略集，面向国金证券「完整版 QMT」。

## 给 AI Agent 的关键约束（编辑代码前必读）

- **只能写 QMT 内置 Python 策略**：用户的 miniQMT（外部 xtquant 连接）已于 2025-09 被禁用，`xtquant` 方案不可用。所有策略用 `ContextInfo` + `passorder`（`init` / `handlebar` 生命周期），不要引入 xtquant。
- **文件首行必须是 `#encoding:gbk`**：QMT 按 GBK 读文件，改成 UTF-8 会导致中文注释乱码、甚至策略解析失败。
- **下单方向要核对**：`passorder` 中 23=买入、24=卖出。方向写反是真金白银的实亏。
- **ETF 最小交易单位 100 份**：所有成交量参数必须是 100 的整数倍。
- **策略文件保持自包含**：每个 `strategies/*.py` 是单独粘贴进 QMT 运行的，文件间重复的 `bar_time` / `bar_minutes` / `today_of` 等工具函数是有意为之——不要为了 DRY 改成跨文件 import（QMT 内置 Python 的 import 路径不可靠）。
- **风控依赖时间戳**：`FLAT_MINUTES`（收盘平仓）和硬止损的「当日暂停」都依赖 `get_market_data_ex` 返回带时间的 K 线（DataFrame/Series 索引）。取不到时间会静默失效，改这块逻辑时注意。
- **标的必须 T+0**：境内股票 ETF（沪深300、芯片、券商等）是 T+1，不能日内做T。换标的时先确认 T+0 属性。

## 目录

- `strategies/*.py` — 5 个策略（网格、双均线、ORB 开盘突破、RSI 均值回归、配对价差单边近似），全部 QMT 内置 Python
- `common/qmt_api_reference.md` — ContextInfo / passorder API 速查
- `README.md` — 给人读的上手指南

## 工作纪律

先回测 → 模拟 → 小资金实盘。日内交易是负和博弈，**如实提示风险、不鼓励重仓**。

## Git

- 身份：Ryan Tan <ryan.tan@live.com>（全局已配置）
- 分支：main
- 提交信息末尾需带 `Co-Authored-By: Claude Code <noreply@anthropic.com>`