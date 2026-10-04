#encoding:gbk
"""
ETF 网格交易 —— 国金证券 完整QMT 内置 Python 策略

思路：把价格区间切成 N 格，每跌一格买一份、每涨一格卖一份。
风控：跌破持仓平均成本 STOP_LOSS_PCT 清仓并当日暂停；FLAT_MINUTES 收盘前自动平仓。

适合：黄金ETF 518880 等 T+0。先回测 → 模拟 → 实盘。
注意：ETF 最小交易单位 100 份，BASE_UNIT 必须是 100 的整数倍。周期选「1分钟」。
"""

STOCK = '518880.SH'
ACC_ID = '你的资金账号'
GRID_UPPER = 6.0
GRID_LOWER = 5.0
GRID_NUM   = 20
BASE_UNIT  = 1000           # 每格份额（100 的整数倍）

# ===== 日内风控（通用参数） =====
FLAT_MINUTES = 890      # 收盘前平仓时间（890=14:50）。设 99999 关闭
STOP_LOSS_PCT = 0.02    # 硬止损：跌破持仓平均成本 2% 清仓并当日暂停。设 0 关闭
# ================================

STEP = (GRID_UPPER - GRID_LOWER) / float(GRID_NUM)


def init(ContextInfo):
    ContextInfo.set_universe([STOCK])
    ContextInfo.accID = ACC_ID
    ContextInfo.last_level = None     # 上一次价格所在网格层级
    ContextInfo.pos = 0               # 持仓份额
    ContextInfo.avg_cost = None       # 持仓平均成本
    ContextInfo.day = ''              # 用于按天重置
    ContextInfo.stopped = False       # 硬止损后当日暂停
    ContextInfo.order_seq = 0
    print('网格策略初始化完成，标的=%s，每格间距=%.4f' % (STOCK, STEP))


def handlebar(ContextInfo):
    ctx = ContextInfo
    # —— 日内风控：按天重置 / 收盘平仓 / 止损后暂停 ——
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

    price = latest_price(ctx, STOCK)
    if price is None or price <= 0:
        return

    # —— 硬止损 ——
    if (STOP_LOSS_PCT > 0 and ctx.pos > 0 and ctx.avg_cost is not None
            and price <= ctx.avg_cost * (1 - STOP_LOSS_PCT)):
        flatten(ctx, '硬止损')
        ctx.stopped = True
        return

    level = grid_level(price)
    if ctx.last_level is None:
        ctx.last_level = level
        return
    if level == ctx.last_level:
        return

    if level < ctx.last_level:                      # 向下穿越：每降一格买一份
        for _ in range(ctx.last_level - level):
            do_buy(ctx, price, BASE_UNIT)
    else:                                           # 向上穿越：每升一格卖一份
        for _ in range(level - ctx.last_level):
            if ctx.pos >= BASE_UNIT:
                do_sell(ctx, price, BASE_UNIT)
    ctx.last_level = level


def grid_level(price):
    if price <= GRID_LOWER:
        return 0
    if price >= GRID_UPPER:
        return GRID_NUM
    return int((price - GRID_LOWER) / STEP)


def latest_price(ctx, code):
    try:
        tick = ctx.get_full_tick([code])
        if code in tick and tick[code].get('lastPrice') is not None:
            return float(tick[code]['lastPrice'])
    except Exception:
        pass
    try:
        d = ctx.get_market_data_ex(['close'], [code], period='1m', count=2)
        p = d['close'][code]
        if hasattr(p, 'tolist'):
            p = p.tolist()
        return float(p[-1])
    except Exception:
        return None


def do_buy(ctx, price, volume):
    ctx.order_seq += 1
    ctx.passorder(23, 1101, ctx.accID, STOCK, 5, -1, volume, '网格', 0, str(ctx.order_seq), ctx)
    ctx.avg_cost = price if ctx.avg_cost is None else \
        (ctx.avg_cost * ctx.pos + price * volume) / float(ctx.pos + volume)
    ctx.pos += volume
    print('[网格] 买入 %d 份 @ %.3f（持仓 %d）' % (volume, price, ctx.pos))


def do_sell(ctx, price, volume):
    ctx.order_seq += 1
    ctx.passorder(24, 1101, ctx.accID, STOCK, 5, -1, volume, '网格', 0, str(ctx.order_seq), ctx)
    ctx.pos = max(0, ctx.pos - volume)
    if ctx.pos == 0:
        ctx.avg_cost = None
    print('[网格] 卖出 %d 份 @ %.3f（持仓 %d）' % (volume, price, ctx.pos))


def flatten(ctx, reason):
    if ctx.pos <= 0:
        return
    ctx.order_seq += 1
    ctx.passorder(24, 1101, ctx.accID, STOCK, 5, -1, ctx.pos, '网格', 0, str(ctx.order_seq), ctx)
    print('[网格] %s，清仓 %d 份' % (reason, ctx.pos))
    ctx.pos = 0
    ctx.avg_cost = None


# —— 以下为通用工具（与其它策略文件重复，为保证单文件可独立运行） ——
def bar_time(ctx, code):
    """当前最后一根1分钟K线的时间，取不到返回 None"""
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
    """K线时间转当日分钟数（14:50 -> 890）"""
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
    """K线时间转 'YYYY-MM-DD' 字符串"""
    try:
        import pandas as pd
        if isinstance(t, pd.Timestamp):
            return t.strftime('%Y-%m-%d')
    except Exception:
        pass
    return str(t)[:10]