import talib
import pandas as pd
import numpy as np


def initialize(context):
    set_params()  # 设置参数
    set_backtest()  # 设置回测条件


def set_params():  # 设置参数
    g.stocknum = 20  # 买入的股票数量
    g.period = 5  # 调仓周期
    g.days = 0  # 计时器
    g.lag = 20


def set_backtest():  # 设置回测条件
    # 对比标的
    set_benchmark("000300.XSHG")
    # 当前价格的百分比设置滑点
    set_slippage(PriceRelatedSlippage(0.002))
    # 设置佣金
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5,
        ),
        type="stock",
    )
    # 用真实价格交易
    set_option("use_real_price", True)
    # 设置报错等级，过滤比error低的报错，只保留error
    log.set_level("order", "error")
    # 设置tralling_stop_day，每天open价格执行
    run_daily(tralling_stop_day, "open")


# 定义函数 getStockPrice
# 取得股票某个区间内的所有收盘价（用于取前20日和当前 收盘价）
# 输入：stock, interval
# 输出：h['close'].values[0] , h['close'].values[-1]
def getStockPrice(stock, interval):  # 输入stock证券名，interval期
    h = attribute_history(
        stock, interval, unit="1d", fields=("close"), skip_paused=True
    )
    return (h["close"].values[0], h["close"].values[-1])
    # 0是第一个（interval周期的值,-1是最近的一个值(昨天收盘价)）


# 追踪止损模块
def tralling_stop_day(context):
    for stock in context.portfolio.positions.keys():
        if tralling_stop(context, stock) == 1 and mem_300_500_stop(context) == 1:
            log.info(
                "追踪止损: selling %s %s股"
                % (stock, context.portfolio.positions[stock].closeable_amount)
            )
            order_target(stock, 0)


# 计算是否需要追踪止损
def tralling_stop(context, stock_code):

    Data_ATR = attribute_history(
        "000001.XSHG", 30, "1d", ["close", "high", "low"], df=False
    )
    close_ATR = Data_ATR["close"]
    high_ATR = Data_ATR["high"]
    low_ATR = Data_ATR["low"]

    atr = talib.ATR(high_ATR, low_ATR, close_ATR)
    highest20 = max(close_ATR[-20:])
    if (highest20 - close_ATR[-1]) > (3 * atr[-1]):
        return 1
    else:
        return 0


# 计算300和500指数动量是否需要追踪止损
def mem_300_500_stop(context):
    # 计算300和500指数的增长率，用于快速清仓
    interval300, Yesterday300 = getStockPrice("000300.XSHG", g.lag)
    interval500, Yesterday500 = getStockPrice("000905.XSHG", g.lag)

    hs300increase = (Yesterday300 - interval300) / interval300
    zz500increase = (Yesterday500 - interval500) / interval500

    if hs300increase <= 0 and zz500increase <= 0:
        return 1
    else:
        return 0


# 1、过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    stock_list = [stock for stock in stock_list if not current_data[stock].paused]
    return stock_list


# 2、过滤退市
def delisted_filter(security_list):
    current_data = get_current_data()
    security_list = [
        stock for stock in security_list if not "退" in current_data[stock].name
    ]
    return security_list


# 3、过滤St
def st_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].is_st]
    return security_list


# 4、过滤次新股
# 通过context.current_dt.date实现
def remove_new_stocks(context, security_list):
    for stock in security_list:
        days_public = (
            context.current_dt.date() - get_security_info(stock).start_date
        ).days
        if days_public < 365:
            security_list.remove(stock)
    return security_list


# 5、过滤涨停板股
# 通过history获取1分钟数据，再通过current_data获取涨停价格
def high_limit_filter(security_list):
    prices = history(1, unit="1m", field="close", security_list=security_list)
    current_data = get_current_data()
    security_list = [
        stock
        for stock in security_list
        if not prices[stock][-1] == current_data[stock].high_limit
    ]
    return security_list


def handle_data(context, data):
    # 获得当前时间
    hour = context.current_dt.hour
    minute = context.current_dt.minute

    # 每天14:53调仓
    if hour == 14 and minute == 53:

        # 计算300和500指数的增长率
        interval300, Yesterday300 = getStockPrice("000300.XSHG", g.lag)
        interval500, Yesterday500 = getStockPrice("000905.XSHG", g.lag)

        hs300increase = (Yesterday300 - interval300) / interval300
        zz500increase = (Yesterday500 - interval500) / interval500

        h = attribute_history(
            "000001.XSHG",
            20,
            unit="1d",
            fields=("close", "high", "low"),
            skip_paused=True,
        )
        h_now = h["close"][-1]
        # 阶段内大盘最高最低价
        low_price = h.close.min()

        # 如果非止损区间，且小盘股动量大于大盘股
        if (
            tralling_stop(context, "000001.XSHG") == 0
            and zz500increase >= 0
            and zz500increase - hs300increase >= 0.01
        ):
            buy_market_stocks(context)
            g.days += 1


# 定义函数买入股票
def buy_market_stocks(context):
    # 在每个调仓周期
    g.run_today = g.days % g.period == 0
    if g.run_today == False:
        return

    # 获取当前时间
    date = context.current_dt.strftime("%Y-%m-%d")
    list_stock = get_index_stocks("000002.XSHG") + get_index_stocks("399107.XSHE")
    # 000002.XSHG  A股指数 和 399107.XSHE 深证A指

    # 过滤停牌、退市、st牌股、次新股、涨停板股
    filter1 = filter_paused_stock(list_stock)
    filter2 = delisted_filter(filter1)
    filter3 = st_filter(filter2)
    filter4 = remove_new_stocks(context, filter3)
    filter5 = high_limit_filter(filter4)

    # 选出在过滤停牌、退市和st后的股票代码，并按照当前时间市值从小到大排序
    df = get_fundamentals(
        query(
            valuation.code,
            valuation.market_cap,  # 总市值
            valuation.pe_ratio,  # PE市盈率
            indicator.inc_net_profit_year_on_year,  # 净利润同比增长率(%)
            indicator.inc_net_profit_annual,  # 净利润环比增长率(%)
            balance.total_assets,  # 资产总计(元)
            balance.total_liability,  # 负债总计(元)
        )
        .filter(
            # 市盈率相对盈利增长比率
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year > 0,
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year < 1,
            # 资产负债率
            balance.total_liability / balance.total_assets < 0.5,
            indicator.inc_net_profit_annual > 0.10,
            valuation.code.in_(filter5),
        )
        .order_by(valuation.market_cap.asc())
        .limit(
            # 最多取前stocknum只
            g.stocknum
        ),
        date=date,
    )

    # 取出前g.buyStockCount名的股票代码，并转成list类型
    g.stocks = list(df["code"])

    order_stock_sell(context, g.stocks)
    order_stock_buy(context, g.stocks)


# 执行卖出
def order_stock_sell(context, order_list):
    # 对于不需要持仓的股票，全仓卖出
    for stock in context.portfolio.positions:
        # 除去buy_list内的股票，其他都卖出
        if stock not in order_list:
            order_target_value(stock, 0)


# 执行买入
def order_stock_buy(context, order_list):
    # 先求出可用资金，如果持仓个数小于g.stocknum
    if len(context.portfolio.positions) < g.stocknum:
        # 求出要买的数量num
        num = g.stocknum - len(context.portfolio.positions)
        # 求出每只股票要买的金额cash
        g.each_stock_cash = context.portfolio.available_cash / num
    else:
        # 如果持仓个数满足要求，不再计算g.each_stock_cash
        cash = 0
        num = 0
    # 执行买入
    for stock in order_list:
        if stock not in context.portfolio.positions:
            order_target_value(stock, g.each_stock_cash)
