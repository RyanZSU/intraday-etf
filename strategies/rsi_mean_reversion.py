#encoding:gbk
"""
RSI 均值回归 —— 国金证券 完整QMT 内置 Python 策略

思路：RSI 超卖回升买入、回升到退出线止盈、跌破成本止损。
      * 均值回归在震荡市有效，单边趋势市会反复接飞刀，请配合行情判断。
风控：跌破持仓成本 STOP_LOSS_PCT 硬止损并当日暂停；FLAT_MINUTES 收盘前自动平仓。

适合：黄金 518880 等日内震荡的 T+0 ETF。先回测 → 模拟 → 实盘。周期选「1分钟」。
"""

STOCK = '518880.SH'
ACC_ID = '你的资金账号'
RSI_PERIOD = 14
OVERSOLD = 30          # 超卖线（跌破后回升时买入）
EXIT_LEVEL = 55        # 回升退出线（止盈）
VOLUME = 1000          # 每次买卖份额（100 的整数倍）

# ===== 日内风控（通用参数） =====
FLAT_MINUTES = 890
STOP_LOSS_PCT = 0.02   # 硬止损：跌破持仓成本 2% 清仓并当日暂停。设 0 关闭
# ================================


def init(ContextInfo):
    ContextInfo.set_universe([STOCK])
    ContextInfo.accID = ACC_ID
    ContextInfo.holding = False
    ContextInfo.entry_price = None
    ContextInfo.day = ''
    ContextInfo.stopped = False
    ContextInfo.order_seq = 0
    print('RSI 均值回归策略初始化完成，标的=%s RSI=%d 超卖线=%d' % (STOCK, RSI_PERIOD, OVERSOLD))


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

    closes = get_closes(ctx, STOCK, RSI_PERIOD + 5)
    if len(closes) < RSI_PERIOD + 2:
        return

    rsi_prev = compute_rsi(closes[:-1], RSI_PERIOD)
    rsi_now = compute_rsi(closes, RSI_PERIOD)
    if rsi_prev is None or rsi_now is None:
        return
    price = closes[-1]

    if not ctx.holding:
        # 确认式买入：RSI 从超卖区下方回升、上穿超卖线
        if rsi_prev < OVERSOLD <= rsi_now:
            buy(ctx, price)
            print('[RSI] 超卖回升买入 @ %.3f rsi=%.1f' % (price, rsi_now))
    else:
        # 硬止损优先
        if STOP_LOSS_PCT > 0 and ctx.entry_price is not None \
                and price <= ctx.entry_price * (1 - STOP_LOSS_PCT):
            flatten(ctx, '硬止损')
            ctx.stopped = True
        elif rsi_now >= EXIT_LEVEL:
            flatten(ctx, 'RSI回升止盈')


def compute_rsi(closes, period):
    """简化版 RSI（对最近 period 根涨跌幅取平均，Wilder 平滑版可自行替换）"""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[-period:]) / float(period)
    avg_loss = sum(losses[-period:]) / float(period)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def get_closes(ctx, code, count):
    try:
        d = ctx.get_market_data_ex(['close'], [code], period='1m', count=count)
        p = d['close'][code]
        if hasattr(p, 'tolist'):
            p = p.tolist()
        return [float(x) for x in p]
    except Exception:
        return []


def buy(ctx, price):
    ctx.order_seq += 1
    ctx.passorder(23, 1101, ctx.accID, STOCK, 5, -1, VOLUME, 'RSI', 0, str(ctx.order_seq), ctx)
    ctx.holding = True
    ctx.entry_price = price


def flatten(ctx, reason):
    if not ctx.holding:
        return
    ctx.order_seq += 1
    ctx.passorder(24, 1101, ctx.accID, STOCK, 5, -1, VOLUME, 'RSI', 0, str(ctx.order_seq), ctx)
    ctx.holding = False
    ctx.entry_price = None
    print('[RSI] %s，平仓' % reason)


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