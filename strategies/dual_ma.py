#encoding:gbk
"""
ETF 日内双均线（1分钟）—— 国金证券 完整QMT 内置 Python 策略

思路：快线上穿慢线（金叉）买入、下穿（死叉）卖出。T+0 标的当日可反复进出。
风控：跌破持仓成本 STOP_LOSS_PCT 硬止损并当日暂停；FLAT_MINUTES 收盘前自动平仓。

风险：震荡市反复金叉死叉来回割肉。先回测 → 模拟 → 实盘。周期选「1分钟」。
"""

STOCK = '513130.SH'
ACC_ID = '你的资金账号'
FAST = 5
SLOW = 20
VOLUME = 1000           # 每次买卖份额（100 的整数倍）

# ===== 日内风控（通用参数） =====
FLAT_MINUTES = 890
STOP_LOSS_PCT = 0.02
# ================================


def init(ContextInfo):
    ContextInfo.set_universe([STOCK])
    ContextInfo.accID = ACC_ID
    ContextInfo.holding = False
    ContextInfo.entry_price = None
    ContextInfo.day = ''
    ContextInfo.stopped = False
    ContextInfo.order_seq = 0
    print('双均线策略初始化完成，标的=%s FAST=%d SLOW=%d' % (STOCK, FAST, SLOW))


def handlebar(ContextInfo):
    ctx = ContextInfo
    # —— 日内风控 ——
    t = bar_time(ctx, STOCK)
    mm = bar_minutes(t) if t is not None else None
    day = today_of(t) if t is not None else None
    if day is not None and ctx.day != day:
        ctx.day = day
        ctx.stopped = False
    if mm is not None and mm >= FLAT_MINUTES:
        flatten(ctx, '收盘前平仓')
        return
    if ctx.stopped:
        return

    closes = get_closes(ctx, STOCK, SLOW + 2)
    if len(closes) < SLOW + 1:
        return

    fast_now = sum(closes[-FAST:]) / float(FAST)
    slow_now = sum(closes[-SLOW:]) / float(SLOW)
    fast_prev = sum(closes[-FAST - 1:-1]) / float(FAST)
    slow_prev = sum(closes[-SLOW - 1:-1]) / float(SLOW)
    price = closes[-1]

    # —— 硬止损优先 ——
    if (ctx.holding and STOP_LOSS_PCT > 0 and ctx.entry_price is not None
            and price <= ctx.entry_price * (1 - STOP_LOSS_PCT)):
        flatten(ctx, '硬止损')
        ctx.stopped = True
        return

    if fast_prev <= slow_prev and fast_now > slow_now and not ctx.holding:
        buy(ctx, price)
    elif fast_prev >= slow_prev and fast_now < slow_now and ctx.holding:
        flatten(ctx, '死叉卖出')


def buy(ctx, price):
    ctx.order_seq += 1
    ctx.passorder(23, 1101, ctx.accID, STOCK, 5, -1, VOLUME, '双均线', 0, str(ctx.order_seq), ctx)
    ctx.holding = True
    ctx.entry_price = price
    print('[双均线] 金叉买入 @ %.3f' % price)


def flatten(ctx, reason):
    if not ctx.holding:
        return
    ctx.order_seq += 1
    ctx.passorder(24, 1101, ctx.accID, STOCK, 5, -1, VOLUME, '双均线', 0, str(ctx.order_seq), ctx)
    ctx.holding = False
    ctx.entry_price = None
    print('[双均线] %s，平仓' % reason)


def get_closes(ctx, code, count):
    try:
        d = ctx.get_market_data_ex(['close'], [code], period='1m', count=count)
        p = d['close'][code]
        if hasattr(p, 'tolist'):
            p = p.tolist()
        return [float(x) for x in p]
    except Exception:
        return []


# —— 通用工具 ——
def bar_time(ctx, code):
    try:
        d = ctx.get_market_data_ex(['close'], [code], period='1m', count=1)
        s = d['close'][code]
        import pandas as pd
        if isinstance(s, (pd.DataFrame, pd.Series)):
            return s.index[-1]
        return None
    except Exception:
        return None


def bar_minutes(t):
    try:
        return t.hour * 60 + t.minute
    except Exception:
        try:
            hm = str(t).split(' ')[1][:5]
            h, m = hm.split(':')
            return int(h) * 60 + int(m)
        except Exception:
            return None


def today_of(t):
    try:
        import pandas as pd
        if isinstance(t, pd.Timestamp):
            return t.strftime('%Y-%m-%d')
    except Exception:
        pass
    return str(t)[:10]