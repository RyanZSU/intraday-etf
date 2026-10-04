#encoding:gbk
"""
跨境 ETF 价差套利（单边近似版）—— 国金 完整QMT 内置 Python 策略

重要前提：真正配对套利要「多一只、空一只」，散户融不到券，这里只能【单边近似】：
    用 log 价差的 z 分数判断哪只相对便宜，只买入便宜的那只，等价差回归再平。
    它【不是】市场中性，价差若不回归一样会亏。

价差定义：spread[i] = ln(close_A[i]) - ln(close_B[i])；z = (spread_now - mean) / std
开仓：z < -Z_ENTRY 买 A；z > +Z_ENTRY 买 B。平仓：z 回到 0；止损：z 扩到 Z_STOP。
风控：跌破单腿成本 STOP_LOSS_PCT 硬止损；FLAT_MINUTES 收盘前自动平仓。

选股：两只须追踪同一指数、都是 T+0。示例 513130 vs 513180（恒生科技），换标的务必核对。
风险：假协整、隔夜跳空、利润薄。强烈建议只跑回测/模拟。周期选「1分钟」。
"""

import math

STOCK_A = '513130.SH'
STOCK_B = '513180.SH'
ACC_ID = '你的资金账号'
LOOKBACK = 30
Z_ENTRY = 2.0
Z_STOP = 3.5
VOLUME_A = 1000
VOLUME_B = 1000

# ===== 日内风控（通用参数） =====
FLAT_MINUTES = 890
STOP_LOSS_PCT = 0.02    # 硬止损：跌破单腿成本 2% 清仓并当日暂停。设 0 关闭
# ================================


def init(ContextInfo):
    ContextInfo.set_universe([STOCK_A, STOCK_B])
    ContextInfo.accID = ACC_ID
    ContextInfo.holding = None      # None / 'A' / 'B'
    ContextInfo.entry_price = None  # 单腿入场价
    ContextInfo.day = ''
    ContextInfo.stopped = False
    ContextInfo.order_seq = 0
    print('配对价差策略初始化完成，%s vs %s' % (STOCK_A, STOCK_B))


def handlebar(ContextInfo):
    ctx = ContextInfo
    # —— 日内风控 ——
    t = bar_time(ctx, STOCK_A)
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

    a = get_closes(ctx, STOCK_A, LOOKBACK + 10)
    b = get_closes(ctx, STOCK_B, LOOKBACK + 10)
    n = min(len(a), len(b))
    if n < LOOKBACK + 1:
        return

    a = a[-n:]
    b = b[-n:]
    spreads = [math.log(x) - math.log(y) for x, y in zip(a, b)]
    window = spreads[:-1]
    mean = sum(window) / float(len(window))
    var = sum((s - mean) ** 2 for s in window) / float(len(window))
    std = math.sqrt(var)
    if std == 0:
        return
    z_now = (spreads[-1] - mean) / std

    price_a = a[-1]
    price_b = b[-1]

    if ctx.holding is None:
        if z_now <= -Z_ENTRY:
            buy(ctx, STOCK_A, VOLUME_A, price_a)
            print('[配对] z=%.2f A相对便宜，买入A' % z_now)
        elif z_now >= Z_ENTRY:
            buy(ctx, STOCK_B, VOLUME_B, price_b)
            print('[配对] z=%.2f B相对便宜，买入B' % z_now)
    else:
        leg_price = price_a if ctx.holding == 'A' else price_b
        # 硬止损优先（单腿）
        if STOP_LOSS_PCT > 0 and ctx.entry_price is not None \
                and leg_price <= ctx.entry_price * (1 - STOP_LOSS_PCT):
            flatten(ctx, '硬止损')
            ctx.stopped = True
        elif (ctx.holding == 'A' and z_now >= 0) or (ctx.holding == 'B' and z_now <= 0):
            flatten(ctx, 'z回归平仓')
        elif (ctx.holding == 'A' and z_now <= -Z_STOP) or (ctx.holding == 'B' and z_now >= Z_STOP):
            flatten(ctx, 'z扩大止损')


def get_closes(ctx, code, count):
    try:
        d = ctx.get_market_data_ex(['close'], [code], period='1m', count=count)
        p = d['close'][code]
        if hasattr(p, 'tolist'):
            p = p.tolist()
        return [float(x) for x in p]
    except Exception:
        return []


def buy(ctx, code, volume, price):
    ctx.order_seq += 1
    ctx.passorder(23, 1101, ctx.accID, code, 5, -1, volume, '配对', 0, str(ctx.order_seq), ctx)
    ctx.holding = 'A' if code == STOCK_A else 'B'
    ctx.entry_price = price


def flatten(ctx, reason):
    if ctx.holding not in ('A', 'B'):
        return
    leg = STOCK_A if ctx.holding == 'A' else STOCK_B
    vol = VOLUME_A if ctx.holding == 'A' else VOLUME_B
    ctx.order_seq += 1
    ctx.passorder(24, 1101, ctx.accID, leg, 5, -1, vol, '配对', 0, str(ctx.order_seq), ctx)
    print('[配对] %s，平仓' % reason)
    ctx.holding = None
    ctx.entry_price = None


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