#encoding:gbk
"""
开盘区间突破（ORB）—— 国金证券 完整QMT 内置 Python 策略

思路：取开盘前 OPEN_MINUTES 分钟的最高/最低价，突破上轨买入；中轨止损、1倍区间高度止盈。
风控：跌破入场价 STOP_LOSS_PCT 硬止损（兜底）；FLAT_MINUTES 收盘前自动平仓。

适合：恒生科技 513130、纳指 513100 等开盘方向明确的 T+0 跨境ETF。
风险：假突破多、胜率低，靠盈亏比取胜。先回测 → 模拟 → 实盘。周期选「1分钟」。
依赖：需能取到带时间戳的分钟K线（判断当天）；若取不到时间请告诉我改成按 bar 计数。
"""

STOCK = '513130.SH'
ACC_ID = '你的资金账号'
OPEN_MINUTES = 30
VOLUME = 1000           # 每次下单份额（100 的整数倍）
PROFIT_RATIO = 1.0      # 止盈 = 入场价 + 区间高度 * PROFIT_RATIO

# ===== 日内风控（通用参数） =====
FLAT_MINUTES = 890
STOP_LOSS_PCT = 0.02    # 硬止损兜底（中轨止损通常先触发；设 0 关闭）
# ================================


def init(ContextInfo):
    ContextInfo.set_universe([STOCK])
    ContextInfo.accID = ACC_ID
    ContextInfo.orb_state = None      # None / 'long'
    ContextInfo.orb_day = ''
    ContextInfo.entry = None
    ContextInfo.mid = None
    ContextInfo.target = None
    ContextInfo.stopped = False
    ContextInfo.order_seq = 0
    print('ORB 策略初始化完成，标的=%s，开盘区间=%d分钟' % (STOCK, OPEN_MINUTES))


def handlebar(ContextInfo):
    ctx = ContextInfo
    times, closes = get_1m_bars(ctx, STOCK, 60)
    if not closes:
        return
    t = times[-1] if times else None
    mm = bar_minutes(t) if t is not None else None
    day = today_of(t) if t is not None else None

    # 新的一天 → 重置
    if day is not None and ctx.orb_day != day:
        ctx.orb_day = day
        ctx.orb_state = None
        ctx.stopped = False
        ctx.entry = ctx.mid = ctx.target = None

    # 收盘前平仓
    if mm is not None and mm >= FLAT_MINUTES:
        flatten(ctx, '收盘前平仓')
        return
    if ctx.stopped:
        return

    # 当天K线（取不到时间则退化为最近60根，无法按天重置）
    if day is not None:
        today_closes = [c for tt, c in zip(times, closes) if today_of(tt) == day]
    else:
        today_closes = closes

    if len(today_closes) <= OPEN_MINUTES:
        return

    opening = today_closes[:OPEN_MINUTES]
    H = max(opening)
    L = min(opening)
    mid = (H + L) / 2.0
    height = H - L
    price = today_closes[-1]

    if ctx.orb_state is None:
        if price > H:
            buy(ctx)
            ctx.entry = price
            ctx.mid = mid
            ctx.target = price + height * PROFIT_RATIO
            print('[ORB] 突破上轨 %.3f，买入 @ %.3f，目标 %.3f' % (H, price, ctx.target))
    else:
        if STOP_LOSS_PCT > 0 and ctx.entry is not None and price <= ctx.entry * (1 - STOP_LOSS_PCT):
            flatten(ctx, '硬止损')
            ctx.stopped = True
        elif price >= ctx.target:
            flatten(ctx, '止盈')
        elif price < ctx.mid:
            flatten(ctx, '止损(破中轨)')


def get_1m_bars(ctx, code, count):
    try:
        d = ctx.get_market_data_ex(['close'], [code], period='1m', count=count)
        s = d['close'][code]
        import pandas as pd
        if isinstance(s, pd.DataFrame):
            return list(s.index), [float(s.iloc[i, 0]) for i in range(len(s))]
        if isinstance(s, pd.Series):
            return list(s.index), [float(x) for x in s.tolist()]
        return None, [float(x) for x in list(s)]
    except Exception:
        return None, []


def buy(ctx):
    ctx.order_seq += 1
    ctx.passorder(23, 1101, ctx.accID, STOCK, 5, -1, VOLUME, 'ORB', 0, str(ctx.order_seq), ctx)
    ctx.orb_state = 'long'


def flatten(ctx, reason):
    if ctx.orb_state != 'long':
        return
    ctx.order_seq += 1
    ctx.passorder(24, 1101, ctx.accID, STOCK, 5, -1, VOLUME, 'ORB', 0, str(ctx.order_seq), ctx)
    ctx.orb_state = None
    print('[ORB] %s，平仓' % reason)


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