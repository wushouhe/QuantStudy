# 标题：动量、反转测试模板

import pandas as pd
import numpy as np


def initialize(context):  # 初始化
    set_params()  # 设置参数
    set_backtest()  # 设置回测条件


def set_params():  # 设置参数
    g.stockCount = 2000  # 返回前多少只股票（市值最小，或动量最强）
    g.stocksnum = 100  # 持有最小市值股票数（市值最小，或动量最强）
    g.period = 10  # 调仓轮动日频率
    g.lag = 60  # 动量反转形成的窗口期
    g.days = 0  # 记录策略进行到第几天，初始为1


def set_backtest():  # 设置回测
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


# 自定义函数 getStockPrice
# 取得股票某个区间内的所有收盘价（用于取前interval日和当前日 收盘价）
# 输入：stock, interval
# 输出：h['close'].values[0] , h['close'].values[-1]
def getStockPrice(stock, interval):  # 输入stock证券名，interval期
    h = attribute_history(
        stock, interval, unit="1d", fields=("close"), skip_paused=True
    )
    return (h["close"].values[0], h["close"].values[-1])
    # 0是第一个（interval周期的值,-1是最近的一个值(昨天收盘价)）


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


# 回测函数运行
def handle_data(context, data):
    # 获得当前时间
    hour = context.current_dt.hour
    minute = context.current_dt.minute

    # 额定天数的14:53调仓
    if hour == 14 and minute == 53 and g.days % g.period == 1:
        # 获取当前时间
        date = context.current_dt.strftime("%Y-%m-%d")
        list_stock = get_index_stocks("000002.XSHG") + get_index_stocks("399107.XSHE")
        # 000002.XSHG  A股指数 和 399107.XSHE 深证A指

        # 过滤停牌、退市、st牌股、次新股、涨停板股
        filter1 = filter_paused_stock(list_stock)
        filter2 = delisted_filter(filter1)
        filter3 = st_filter(filter2)
        filter4 = remove_new_stocks(context, filter3)

        # 选出在过滤停牌、退市和st后的股票代码，并按照当前时间市值从小到大排序
        df = get_fundamentals(
            query(valuation.code, valuation.market_cap)
            .filter(valuation.code.in_(filter4))
            .order_by(valuation.market_cap.asc())
            .limit(
                # 最多取前stockCount只
                g.stockCount
            ),
            date=date,
        )

        # 取出股票代码，并转成list类型
        stocks_to_buy = list(df["code"])

        # 通过循环，逐一求出个股的动量，形成一个momentum
        stock_momentum = []
        momentum = []
        for security in stocks_to_buy:
            interval, Yesterday = getStockPrice(security, g.lag)
            stock_momentum = Yesterday / interval
            momentum.append((security, stock_momentum))

        # 按照动量进行排序（升序）
        # 升序模式是反转模式，买入低动量股票
        # 降序模式是动量模式，买入高动量股票
        # 我们测试默认用1000万元，买入100只股票，每只10万元，保证较细致的资金分割

        # momentum.sort(key = lambda l: l[1])                 # 升序（反转模式）
        momentum.sort(key=lambda l: l[1], reverse=True)  # 降序（动量模式）

        # 转化成np.array结构，方便取出第一列数据（股票代码）
        np_momentuma = np.array(momentum)
        stocks_to_buy = np_momentuma[:, 0]

        # 取出前stocksnum个股票买入，2000只股票的前100名，是前5%
        stocks_to_buy = stocks_to_buy[: g.stocksnum]
        # print stocks_to_buy

        # 对于每个当下持有的股票进行判断：现在是否已经不在stocks_to_buy里，如果是则卖出
        # already_have_cnt表示已经被买入了
        already_have_cnt = 0
        for stock in context.portfolio.positions:
            if stock not in stocks_to_buy:  # 如果stock不在stocks_to_buy买入名单
                order_target(stock, 0)  # 调整stock的持仓为0，即卖出
            else:
                already_have_cnt += 1

        # 将资金分成（g.stocksnum-already_have_cnt）份
        if g.stocksnum > already_have_cnt:
            position_per_stk = context.portfolio.cash / (g.stocksnum - already_have_cnt)
        else:  # 如果要买的股票都已经买入了
            position_per_stk = 0

        # 用position_per_stk份资金去买stocks_to_buy中的股票
        # 如果要买的股票已经买入，position_per_stk = 0，则不会再产生买入
        for stock in stocks_to_buy:
            if stock not in context.portfolio.positions:
                order_value(stock, position_per_stk)

    # 每日，让g.days计数器递增1
    if hour == 14 and minute == 53:
        g.days = g.days + 1  # 策略经过天数增加1
