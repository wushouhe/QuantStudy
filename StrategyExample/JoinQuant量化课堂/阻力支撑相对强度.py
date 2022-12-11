# RSRS（阻力支撑相对强度）择时策略映射到个股交易
# RS指数择时原链接：https://www.joinquant.com/post/10246


# 导入函数库
import statsmodels.api as sm
import numpy as np
import pandas as pd
import math


# 初始化函数，设定基准等
def initialize(context):
    # 设定上证指数作为基准
    set_benchmark('000300.XSHG')
    # 当前价格的百分比设置滑点
    set_slippage(PriceRelatedSlippage(0.002))   
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    # 每日运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')


    # 设置RSRS指标中N, M的值
    g.N = 18
    g.M = 600
    g.init = True

    # 择时依据的指数
    g.index = '000300.XSHG'

    # 买入阈值
    g.buy = 0.8
    g.sell = -0.8
    g.ans = []

    # 持有股票数量
    g.stocknum = 20

    # 计算2005年1月5日至回测开始日期的RSRS斜率指标
    prices = get_price(g.index, '2005-01-05', context.previous_date, '1d', ['high', 'low'])
    highs = prices.high
    lows = prices.low
    g.ans = []
    for i in range(len(highs))[g.N:]:
        data_high = highs.iloc[i-g.N+1:i+1]
        data_low = lows.iloc[i-g.N+1:i+1]
        X = sm.add_constant(data_low)
        model = sm.OLS(data_high,X)
        results = model.fit()
        g.ans.append(results.params[1])


## 每日运行
def market_open(context):

    if g.init:
        g.init = False
    else:
        # RSRS斜率指标定义
        prices = attribute_history(g.index, g.N, '1d', ['high', 'low'])
        highs = prices.high
        lows = prices.low
        X = sm.add_constant(lows)
        model = sm.OLS(highs, X)
        beta = model.fit().params[1]
        g.ans.append(beta)

    # 计算标准化的RSRS指标
    # 计算均值序列
    section = g.ans[-g.M:]
    # 计算均值序列
    mu = np.mean(section)
    # 计算标准化RSRS指标序列
    sigma = np.std(section)
    zscore = (section[-1]-mu)/sigma    

    # 获取该指数的成分股名单
    security_list = get_index_stocks(g.index)
    # 获取相关性最高的部分个股
    corr_security_list = corr_security(security_list,g.index,g.stocknum*2)
    # 再过滤得到动量较低的部分个股
    mom_corr_security_list = low_momentum(corr_security_list,g.stocknum)

    # 如果上一时间点的RSRS斜率大于买入阈值, 则全仓买入
    if zscore > g.buy :
        log.info("标准化RSRS斜率大于买入阈值, 买入" )
        order_stock_buy(context,mom_corr_security_list)

    # 如果上一时间点的RSRS斜率小于卖出阈值, 则空仓卖出
    elif zscore < g.sell :
        # 记录这次卖出
        log.info("标准化RSRS斜率小于卖出阈值, 卖出" )
        # 如果有股票卖出所有股票
        if (context.portfolio.positions!={}):
            order_stock_sell(context)


# 执行买入
def order_stock_buy(context,security_list):
    # 卖出已经持有的，但是不在这次security_list里的股票
    num = 0 # 重复的股票的数量
    for stock in context.portfolio.positions:
        print stock
        if stock not in security_list:
            order_target_value(stock, 0)
        else:
            num += 1

    if (num==g.stocknum): # 所有的股票都是重复的，不需要买入或卖出
        pass
    else:    
        g.each_stock_cash = context.portfolio.available_cash/(g.stocknum-num)
        # 执行买入
        for stock in security_list:
            if stock not in context.portfolio.positions:
                order_target_value(stock, g.each_stock_cash) 


# 执行卖出
def order_stock_sell(context):
    # 对于不需要持仓的股票，全仓卖出
    for stock in context.portfolio.positions:
        order_target_value(stock, 0)


# 求阶段性高相关个股
def corr_security(security_list,index,n):
    corr_list = []
    # 获取两个数据：个股序列security_price，指数序列index_price
    for i in security_list:
        security_price = attribute_history(i, 30, '1d', ['close']).close
        index_price = attribute_history(index, 30, '1d', ['close']).close
        corr_prine = pd.Series(security_price).corr(pd.Series(index_price))
        corr_list.append((i, corr_prine))

    # 降序排列
    corr_list.sort(key = lambda l: l[1], reverse = True) 
    # 转化成np.array结构，方便取出第一列数据（股票代码）
    np_corr_list = np.array(corr_list)[:,0]
    # 取出前stocksnum个股票买入，（买入名单stock_list）的前n名
    np_corr_list = list(np_corr_list[:n])
    # print np_corr_list
    return np_corr_list    


# 20周期内低动量过滤
def low_momentum(stock_list,n):
    momentum = []
    for i in stock_list:
        interval,Yesterday = getStockPrice(i, 20) 
        stock_momentum = Yesterday / interval
        momentum.append((i, stock_momentum))

    momentum.sort(key = lambda l: l[1])                 # 动量升序
    # 转化成np.array结构，方便取出第一列数据（股票代码）
    np_momentuma = np.array(momentum)[:,0]
    # 取出前stocksnum个股票买入，（买入名单stock_list）的前20名
    low_momentum_to_buy = list(np_momentuma[:n])
    return low_momentum_to_buy


# 取得股票某个区间内的所有收盘价（用于取前interval日和当前日收盘价）
def getStockPrice(stock, interval): # 输入stock证券名，interval期
    h = attribute_history(stock, interval, unit='1d', fields=('close'), skip_paused=True)
    return (h['close'].values[0] , h['close'].values[-1])
    # 0是第一个（interval周期的值,-1是最近的一个值(昨天收盘价)）