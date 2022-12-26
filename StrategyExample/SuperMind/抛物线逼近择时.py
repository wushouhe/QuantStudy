"""
抛物线逼近择时
作者:一箩筐
"""


import numpy as np
import pandas as pd
import statsmodels.api as sm


# 初始化函数 ##################################################################
def init(context):
    set_params(context)  # 设置策略参数
    set_variables(context)  # 设置中间变量
    set_backtest()  # 设置回测条件


# 1.设置策略参数
def set_params(context):
    context.stock = "600519.SH"  # 交易标的
    context.N = 1  # 信号确认日期


# 2.设置中间变量
def set_variables(context):
    context.X_length = 1  # 抛物线累加日期
    context.direct = 0  # 择时方向
    context.is_change = False  # 今日交易
    context.Countdown = {}  # 信号确认时钟


# 3.设置回测条件
def set_backtest():
    set_benchmark("000300.SH")  # 设置基准
    set_slippage(PriceSlippage(0.002))  # 设置可变滑点


# 每日开盘执行 ##################################################################
def handle_bar(context, bar_dict):
    if context.X_length > 2:
        # 计算指标
        Slope = get_signal(context, bar_dict)
        # 获得交易信号
        trade_signal(context, Slope)
        # 执行交易
        tarde_operate(context)


# 4.计算指标
def get_signal(context, bar_dict):
    value = history(context.stock, ["close", "open"], context.X_length, "1d", True)
    # 计算x,y
    X = np.array(range(context.X_length))
    X2 = X**2
    c = np.ones(len(X))
    Y = (value.close.values + value.open.values) / 2
    dic1 = {"X2": X2, "X": X, "c": c, "y": Y}
    df = pd.DataFrame(dic1)
    # 输入输出
    x_train = df[["X", "X2", "c"]]
    y_train = df[["y"]]
    # 最小二乘法回归
    model = sm.OLS(y_train, x_train)
    results = model.fit()
    # 一阶斜率计算
    Slope = results.params[0] + 2 * results.params[1] * df.X.values[-1]
    log.info(Slope)
    return Slope


# 5.获得交易信号
def trade_signal(context, Slope):
    # 信号确认时钟计算
    for i in context.Countdown.keys():
        context.Countdown[i] -= 1
        if context.Countdown[i] == 0 and context.direct * Slope < 0:
            log.info("方向更改", context.direct, Slope)
            context.direct = Slope
            context.is_change = True
            return
    # 赋予初始值，初始向上，则买入
    if context.direct == 0:
        context.direct = Slope
        if Slope > 0:
            order_target_percent(context.stock, 1)
    # 方向相反，则添加一个N天后的信号确认时钟
    else:
        if context.direct * Slope < 0:
            context.Countdown[context.X_length] = context.N


# 6.执行交易
def tarde_operate(context):
    if context.is_change == True:
        # 执行交易
        if context.direct > 0:
            order_target_percent(context.stock, 1)
        if context.direct < 0:
            order_target_percent(context.stock, 0)
        # 重置中间变量
        context.X_length = 1  # 抛物线累加日期
        context.is_change = False  # 今日交易
        context.Countdown = {}  # 信号确认时钟


# 每日收盘执行 ##################################################################
def after_trading(context):
    context.X_length += 1
