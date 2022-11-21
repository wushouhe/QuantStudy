# 原作者：JoinQuant量化课堂
# 原地址：https://www.joinquant.com/post/1957

import talib
import pandas as pd
import numpy as np

'''
=====================
总体回测前
=====================
'''
# 总体回测前要做的事情
def initialize(context):
    set_params()                             # 设置策略常量
    set_variables()                          # 设置中间变量
    set_backtest()                           # 设置回测条件

#1 设置策略参数
def set_params():
    g.tc = 10                                # 调仓天数，让模型每g.tc天，调仓一次
    g.num_stocks = 20                        # 每次调仓选取的最大股票数量
    g.ATR_timeperiod = 14                    # set ATR period

    
#2 设置中间变量
def set_variables():
    g.testdays = 0                           # 记录回测运行的天数
    g.if_trade = False                       # 当天是否交易

#3 设置回测条件
def set_backtest():
    set_option('use_real_price',True)        # 用真实价格交易
    log.set_level('order','error')           # 设置报错等级，过滤比error低的报错，只保留error
    set_benchmark('000300.XSHG')             # 设置基准收益

'''
=====================
每天开盘前
=====================
'''
# 每天开盘前要做的事情
def before_trading_start(context):
    if g.testdays%g.tc == 0:                     # 如果取余数=0，意味可以整除，是一个调仓窗口期
        g.if_trade = True                        # 每g.testdays天，允许调仓一次
        set_slip_fee(context)                    # 设置手续费, 因为每天的手续费不用，所以放到每天开盘前要做的事情。实际上有更好的实现方式
        g.stocks=get_index_stocks('000300.XSHG') # 设置沪深300为初始股票池
        # 不输入日期，回测模块下，默认日期值会随着回测日期变化而变化, 等于context.current_dt
        # 得到可行股票池g.feasible_stocks
        g.feasible_stocks = set_feasible_stocks(g.stocks,context)
        # print context.current_dt;
    g.testdays+=1 # g.t每天before_trading_start时刻定增1，表示新的一天


# 4 设置可行股票池：过滤掉当日停牌的股票
# 输入：initial_stocks为list类型,表示初始股票池
# 输出：unsuspened_stocks为list类型，表示当日未停牌的股票池，即：可行股票池
def set_feasible_stocks(initial_stocks,context):
    # 判断初始股票池的股票是否停牌，返回list（unsuspened_stocks没有停牌的股票）
    paused_info = []                               # paused_info（停牌状态）是一个空list数据类型
    current_data = get_current_data()              # current_data，是dict数据，含1个key和8个value
    for i in initial_stocks:                       # 依次识别股票池里的所有股票
        paused_info.append(current_data[i].paused) # paused属性标志着是否停牌
        # 提取第i个股票的current_data.paused值，添加到paused_info里面

    df_paused_info = pd.DataFrame(data = {'paused_info':paused_info},index = initial_stocks)# first para is data, second is index
    # pd.DataFrame创建一个DataFrame
    # index = initial_stocks，索引列是initial_stocks股票池代码
    # 值列，是paused_info，是True or false
    
    unsuspened_stocks = list(df_paused_info.index[df_paused_info.paused_info == False])
    # 将所有paused_info == False的数据位置提出来
    # df_paused_info.index是该位置的index，也就是股票代码，通过list函数转化为list数据类型
    return unsuspened_stocks # 该函数返回没有停牌的股票为list类型


# 5 根据不同的时间段设置滑点与手续费
# 输入：context（见API）
# 输出：none
def set_slip_fee(context):
    # 将滑点设置为千分之2
    set_slippage(PriceRelatedSlippage(0.002))   # 当前价格的百分比, default value is 0.00246
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    if dt>datetime.datetime(2013,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, \
        close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
        # 买入时印花税=0，卖出时印花税=千分之1，买入佣金=万3，卖出佣金=万3，最低佣金5元
    elif dt>datetime.datetime(2011,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.001, \
        close_commission=0.001, close_today_commission=0, min_commission=5), type='stock')
    elif dt>datetime.datetime(2009,1, 1):
        set_order_cost(OrderCost(open_tax=0.001, close_tax=0.002, open_commission=0.001, \
        close_commission=0.001, close_today_commission=0, min_commission=5), type='stock')
    else:
        set_order_cost(OrderCost(open_tax=0.002, close_tax=0.003, open_commission=0.001, \
        close_commission=0.001, close_today_commission=0, min_commission=5), type='stock')

'''
=====================
每天交易时，启动回测引擎
=====================
'''
# 4 每天回测时做的事情
def handle_data(context,data):
    if g.if_trade == True: # 每g.tc天，允许调仓一次，
        # check if need to sell all
        # sell_all = market_not_safe(g.index2,g.index8)
        sell_all = tralling_stop(context, '000300.XSHG')
        # 如果确认要进行TS操作，令两个名单为空，然后逐一把股票i循环清空
        if (sell_all):
            list_to_buy = []
            list_to_sell = []
            for i in context.portfolio.positions:
                list_to_sell.append(i)
                
        # 如果不需要追踪止损
        else:
            # 待买入的股票list_to_buy，list类型
            list_to_buy = stocks_to_buy(context)
            # 待卖出的股票，list类型
            list_to_sell = stocks_to_sell(context, list_to_buy)

        # 卖出操作 每次调仓时，先卖后买，腾出资金。
        sell_operation(list_to_sell)
        # 买入操作
        buy_operation(context, list_to_buy)
    g.if_trade = False
    # 交易完成后，不允许再交易

    
# 6 计算股票的PEG值
# 输入：context(见API)；stock_list为list类型，表示股票池，输入g.feasible_stocks（停牌处理后的）
# 输出：df_PEG为dataframe类型: index为股票代码，data为相应的PEG值
def get_PEG(context, stock_list):
    # 查询stock_list股票池里股票的代码、市盈率，收益增长率（通过.filter实现筛选）
    q_PE_G = query(valuation.code,
                valuation.pe_ratio,
                indicator.inc_net_profit_year_on_year
                 ).filter(valuation.code.in_(stock_list))
    # 得到一个dataframe：包含股票代码、市盈率PE、盈利增长率G
    df_PE_G = get_fundamentals(q_PE_G)    

    # 筛选出成长股：删除市盈率或收益增长率为负值的股票
    df_Growth_PE_G = df_PE_G[(df_PE_G.pe_ratio >0)&(df_PE_G.inc_net_profit_year_on_year >0)]
#    df_Growth_PE_G = df_PE_G[(df_PE_G >0)]
    # .dropna()去除PE或G值为“非数字”或者为空的股票所在行
    df_Growth_PE_G = df_Growth_PE_G.dropna()

    # 得到一个Series（Series_PE）：存放股票的市盈率TTM（以最近四个季度每股收益计算的市盈率），即PE值
    # .ix函数求该数据结构的行索引，:每一行，列名称是pe_ratio
    Series_PE = df_Growth_PE_G.ix[:,'pe_ratio']
    Series_PE = df_Growth_PE_G.pe_ratio
    
    # 得到一个Series（Series_G）：存放股票的收益增长率，即G值
    # .ix函数求该数据结构的行索引，:每一行，列名称是inc_net_profit_year_on_year
    Series_G = df_Growth_PE_G.ix[:,'inc_net_profit_year_on_year']
    Series_G = df_Growth_PE_G.inc_net_profit_year_on_year
    # 计算得到Series_PEG：存放股票的PEG值
    Series_PEG = Series_PE/Series_G

    # 将股票与其PEG值对应，取df_Growth_PE_G最左侧那一列（股票代码，如000001.XSHE）
    Series_PEG.index = df_Growth_PE_G.ix[:,0]
    # 将Series类型转换成dataframe数据类型，用pd.DataFrame(原变量名)函数实现转化
    df_PEG = pd.DataFrame(Series_PEG)
    return df_PEG


# 7 获得买入信号
# 输入：context(见API)
# 输出：list_to_buy为list类型,表示待买入的g.num_stocks支股票
def stocks_to_buy(context):
    list_to_buy = []
    # 通过刚才定义的函数get_PEG，输入g.feasible_stocks
    # 运行得到一个dataframe：index为股票代码，data为相应的PEG值
    df_PEG = get_PEG(context, g.feasible_stocks)
    # 将股票按PEG升序排列，返回dataframe类型，
    # 参数 columns表示对第0列排序，参数 ascending表示升序
    # dataframe类型最左侧列不是数据，而是index，所以从第1列开始，才是程序认为的第0列columns=[0]
    df_sort_PEG = df_PEG.sort(columns=[0], ascending=[1])

    # 将存储有序股票代码index转换成list，并取前g.num_stocks个为待买入的股票，返回list
    for i in range(g.num_stocks):
        if df_sort_PEG.ix[i,0] < 0.5:
            # .index是提取索引列的值，.ix是查询指定行数据。取出PEG小于0.5的前n只支股票
            # df_sort_PEG是dataframe类型，所以第0列，是索引右侧的列，也就是PEG值
            list_to_buy.append(df_sort_PEG.index[i])
            # 通过.append，逐一添加个股到list_to_buy，这个list要先创建
    return list_to_buy


# 8 获得卖出信号
# 输入：context（见API文档）, list_to_buy为list类型，代表待买入的股票
# 输出：list_to_sell为list类型，表示待卖出的股票
def stocks_to_sell(context, list_to_buy):
    list_to_sell=[]
    # 对于不需要持仓的股票，全仓卖出
    for stock_sell in context.portfolio.positions:
        stock_sell_tralling_stop = tralling_stop(context, stock_sell)
        if stock_sell not in list_to_buy:
        # 不在本期买入名单中的股票，全部要放入stock_sell名单
            list_to_sell.append(stock_sell)
        elif stock_sell_tralling_stop == 1:
            print 'time to run'
            list_to_sell.append(stock_sell)

    return list_to_sell

# 9 执行卖出操作
# 输入：list_to_sell为list类型，表示待卖出的股票
# 输出：none
def sell_operation(list_to_sell):
    for i in list_to_sell:
        order_target_value(i, 0)

# 10 执行买入操作
# 输入：context(见API)；list_to_buy为list类型，表示待买入的股票
# 输出：none
def buy_operation(context, list_to_buy):
    for i in list_to_buy:
        # 为每个持仓股票分配资金
        g.capital_unit=context.portfolio.portfolio_value/len(list_to_buy)
        # 买入在“待买股票列表”的股票
        order_target_value(i, g.capital_unit)

# 11 根据大盘走势，做针对个股追踪止损操作
def tralling_stop(context, stock_code):    
    # 获取stock_code股票的历史数据
    Data_ATR = attribute_history(stock_code, g.ATR_timeperiod+10, '1d',['close','high','low'] , df=False)
    close_ATR = Data_ATR['close']
    high_ATR = Data_ATR['high']
    low_ATR = Data_ATR['low']

    # 计算stock_code股票的AT
    atr = talib.ATR(high_ATR, low_ATR, close_ATR)
    highest20 = max(close_ATR[-20:])

    if ((highest20 - close_ATR[-1]) > (2*atr[-1])):
        return 1
    else:
        return 0