# 国金 QMT 内置 Python 策略 API 速查

> 完整 QMT（非 miniQMT）在客户端内部跑策略，核心对象是全局的 `ContextInfo`。
> 下面的字段名/常量是迅投系主流约定，**不同券商/版本可能略有差异，务必以国金 QMT 客户端「策略说明/帮助文档」为准**（回测或模拟时一眼就能看出对不对）。

## 1. 生命周期函数（策略会声明这几个函数，QMT 自动调用）

| 函数 | 调用时机 |
|---|---|
| `init(ContextInfo)` | 策略启动时执行一次，做初始化 |
| `handlebar(ContextInfo)` | K线驱动，每个周期执行一次（周期在运行设置里选） |
| `after_init(ContextInfo)` | init 之后的补充初始化（可选） |
| `stop(ContextInfo)` | 策略停止时执行（可选） |

> 状态要跨 `handlebar` 保存时，直接挂到 `ContextInfo` 上，例如 `ContextInfo.holding = True`，下次 `handlebar` 读 `ctx.holding` 即可。

## 2. 行情

```python
# 历史/最新 K 线（返回结构因版本而异，按下面防御式写法取）
d = ContextInfo.get_market_data_ex(['open', 'close'], ['518880.SH'], period='1m', count=30)
# d['close']['518880.SH'] 可能是 list / pandas.Series / DataFrame

# 实时 tick（含最新价、五档等）
tick = ContextInfo.get_full_tick(['518880.SH'])
# tick['518880.SH']['lastPrice'] 等
```

常用 `period`：`'1m'`(1分钟)、`'5m'`、`'15m'`、`'1d'`。
`count=-1` 或指定 `start_time` / `end_time` 可指定区间。

## 3. 下单（passorder）

```python
ContextInfo.passorder(opType, orderType, accountid, orderCode, prType,
                      modelprice, volume, strategyName, quickOrder, userOrderId, ContextInfo)
```

| 参数 | 含义 | 常用值 |
|---|---|---|
| `opType` | 操作方向 | 23=买入，24=卖出（股票/ETF） |
| `orderType` | 下单类型 | 1101=限价按数量，1102=市价按数量 |
| `accountid` | 资金账号 | 字符串，登录界面可见 |
| `orderCode` | 证券代码 | `'518880.SH'` |
| `prType` | 价格类型 | 0=指定价，5=最新价，8=涨停价，9=跌停价，11=对手方最优价 |
| `modelprice` | 价格 | prType=5 时可传 -1；prType=0 时传指定价 |
| `volume` | 数量 | ETF 必须 100 的整数倍 |
| `strategyName` | 策略名 | 任取 |
| `quickOrder` | 委托通道 | 0=本地普通，1=中速，2=高速(低延迟) |
| `userOrderId` | 自定义报单号 | 建议每次自增保证唯一 |

> 新手建议用 `1101 + prType=5(最新价)`，简单且不易报错。
> **下单方向（23/24）务必在「模拟盘」先验证，方向写反就是实亏。**

## 4. 账户 / 持仓 / 委托 / 成交

```python
# 账户资产
accs = ContextInfo.get_trade_detail_data(资金账号, 'STOCK', 'ACCOUNT')
# 持仓
poss = ContextInfo.get_trade_detail_data(资金账号, 'STOCK', 'POSITION')
# 委托 / 成交
orders = ContextInfo.get_trade_detail_data(资金账号, 'STOCK', 'ORDER')
trades = ContextInfo.get_trade_detail_data(资金账号, 'STOCK', 'DEAL')
```

返回的是对象列表，常用字段（迅投系约定，以文档为准）：

| 对象 | 常用字段 |
|---|---|
| 账户 | `m_strAccountID` 资金账号、`m_dAvailable` 可用资金、`m_dBalance` 总资产 |
| 持仓 | `m_strInstrumentID` 代码、`m_nVolume` 数量、`m_nCanUseVolume` 可用、`m_dOpenPrice` 成本价、`m_dLastPrice` 最新价、`m_dProfit` 盈亏 |

## 5. 几个关键坑

1. **必须先 `set_universe`**：不设置股票池，`handlebar` 里取不到该股票行情。
2. **handlebar 是 K 线驱动**：周期在「运行设置」里选（1分钟/5分钟等），不是 tick 级。
3. **回测与实盘是同一份代码**：在策略「运行设置」里切「回测」/「模拟」/「实盘」模式即可，不需要另写回测程序。
4. **print 输出到 QMT 的日志/控制台**，不是你的命令行终端。
5. **盘中下单前先模拟**，确认方向、数量、报单没写错。