"""
RSRS指标择时及大小盘轮动
作者:一箩筐

简介:
RSRS指标的构建
1）取前N日的最高价序列与最低价序列。
2）将两列数据,以最高价为因变量，最低价为自变量进行OLS线性回归。
3）取前M日的斜率时间序列，计算当日斜率的标准分z。
4）将z与拟合方程的决定系数相乘，作为当日RSRS指标值。

择沪深300和中证500的ETF作为交易标的，作大小盘风格轮动择时。

交易信号判断
1）以RSRS指标值大的作为交易标的;
2）若RSRS指标上穿阈值S，则开仓买入；（S为开平仓阈值）
3）若RSRS指标下穿阈值-S，则平仓;
4）若RSRS指标在-S和S中间时，两标的的RSRS相对大小变化，则表示风格轮动，换仓，否则不交易。
"""


import numpy as np
import statsmodels.api as sm

# 初始化函数 ##################################################################
def init(context):
    set_params(context)  # 设置策略参数
    set_variables()  # 设置中间变量
    set_backtest()  # 设置回测条件


# 1.设置策略参数
def set_params(context):
    context.N = 20  # 取前N日的数据
    context.M = 400  # RSRS指标M变量
    context.stk1 = "510300.OF"  # 沪深300(大盘)
    context.stk2 = "510500.OF"  # 中证500(小盘)
    context.S = 0.8


# 2.设置中间变量
def set_variables():
    pass


# 3.设置回测条件
def set_backtest():
    set_benchmark("000300.SH")  # 设置基准
    set_slippage(PriceSlippage(0.002))  # 设置可变滑点


# 每日执行函数 ##################################################################
def handle_bar(context, bar_dict):

    # 计算交易信号
    signals = trade_signal(context, bar_dict)
    log.info(signals)
    # 交易操作
    trade_operation(context, signals)


# 4.计算交易信号
def trade_signal(context, bar_dict):
    N = context.N
    M = context.M
    # 计算单个标的昨日的RSRS
    hz300_RSRS = get_RSRS(bar_dict, "000300.SH", N, M)
    zz500_RSRS = get_RSRS(bar_dict, "000905.SH", N, M)
    return [hz300_RSRS, zz500_RSRS]


# 5.计算RSRS
def get_RSRS(bar_dict, stock, n, m):
    values = history(stock, ["high", "low"], n + m - 1, "1d", skip_paused=True)

    high_array = values.high.values[-(n + m - 1) :]
    low_array = values.low.values[-(n + m - 1) :]
    scores = np.zeros(m)  # 各期斜率
    for i in range(m):
        high = high_array[i : i + 30]
        low = low_array[i : i + 30]

        # 计算单期斜率
        x = low  # low作为自变量
        X = sm.add_constant(x)  # 添加常数变量
        y = high  # high作为因变量
        model = sm.OLS(y, X)  # 最小二乘法
        results = model.fit()
        score = results.params[1]
        scores[i] = score

        # 记录最后一期的Rsquared(可决系数)
        if i == m - 1:
            R_squared = results.rsquared

    # 最近期的标准分
    z_score = (scores[-1] - scores.mean()) / scores.std()

    # RSRS得分
    RSRS_socre = z_score * R_squared

    return RSRS_socre


# 6.交易操作
def trade_operation(context, signals):
    # RSRS大的标的 和值
    signal = max(signals)
    if signals[0] > signals[1]:
        stock = context.stk1
    else:
        stock = context.stk2

    if signal > context.S:
        order_value(stock, context.portfolio.stock_account.available_cash * 0.9)
    if signal < -context.S:
        order_target_percent(stock, 0)
    # 处于中间,仓位不变，但是若风格替换且持仓则要换仓
    else:
        if len(list(context.portfolio.stock_account.positions.keys())) != 0:
            order_value(stock, context.portfolio.stock_account.available_cash * 0.9)
