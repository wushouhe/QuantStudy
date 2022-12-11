# 通过更好的大盘止损方法，以及更加合理的基本面过滤逻辑实现性能提升

from jqdata import jy
import talib
import numpy as np 
import pandas as pd
import datetime
import time

# 初始化方法，在整个回测、模拟实盘中最开始执行一次，用于初始一些全局变量
def initialize(context):
   
    # 当前价格的百分比设置滑点
    set_slippage(PriceRelatedSlippage(0.002))   
    # 设置佣金
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, \
    close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    # 设置对比基准
    set_benchmark('000300.XSHG')
    # 使用真实价格
    set_option('use_real_price', True)
    # 过滤log日志
    log.set_level('order', 'error')
    # 按月回测，每月第一个交易日
    run_monthly(fundamentals_filter, 1)
    # 设置回测，每天open价格执行
    run_daily(tralling_stop_day, 'open')   
    # 设置持股数量
    g.stocknum = 15
    # 股息率
    g.div = 0.2
    # 指数动量判断周期
    g.lag = 20
    # 止损位置
    g.tralling_stop_X_ATR = 3


'''
=================================================
每日交易时
=================================================
'''

# 双重逻辑（追踪止损+二八止损）模块
def tralling_stop_day(context):
    for stock in context.portfolio.positions.keys():
        if tralling_stop(context, stock) == 1 and mem_300_500_stop(context) == 1:   
            log.info("追踪止损: selling %s %s股" % (stock, context.portfolio.positions[stock].closeable_amount))
            order_target(stock, 0)
         
           
# 计算是否需要追踪止损   
def tralling_stop(context, stock_code):   

    Data_ATR = attribute_history('000300.XSHG', 30, '1d',['close','high','low'] , df=False)
    close_ATR = Data_ATR['close']
    high_ATR = Data_ATR['high']
    low_ATR = Data_ATR['low']

    atr = talib.ATR(high_ATR, low_ATR, close_ATR)
    highest20 = max(close_ATR[-20:])
    if ((highest20 - close_ATR[-1]) > (g.tralling_stop_X_ATR*atr[-1])):
        return 1
    else:
        return 0
   
       
# 计算300和500指数动量是否需要追踪止损   
def mem_300_500_stop(context):
    # 计算300和500指数的增长率，用于快速清仓
    interval300,Yesterday300 = getStockPrice('000300.XSHG', g.lag) 
    interval500,Yesterday500 = getStockPrice('000905.XSHG', g.lag) 
       
    hs300increase = (Yesterday300 - interval300) / interval300
    zz500increase = (Yesterday500 - interval500) / interval500
   
    if (hs300increase <= 0 and zz500increase <= 0):
        return 1
    else:
        return 0
   
   
# 定义函数 getStockPrice
# 取得股票某个区间内的所有收盘价（用于取前20日和当前 收盘价）
# 输入：stock, interval
# 输出：h['close'].values[0] , h['close'].values[-1]
def getStockPrice(stock, interval): # 输入stock证券名，interval期
    h = attribute_history(stock, interval, unit='1d', fields=('close'), skip_paused=True)
    return (h['close'].values[0] , h['close'].values[-1])
    # 0是第一个（interval周期的值,-1是最近的一个值(昨天收盘价)）       


# 取基本面数据
def fundamentals_filter(context):
   
    sample = get_index_stocks('000985.XSHG', date = None)
   
    # 获取基本面数据
    q = query(valuation.code,
                valuation.pe_ratio / indicator.inc_net_profit_year_on_year,# PEG
                indicator.roe / valuation.pb_ratio, # PB-ROE
                indicator.roe ,
                ).filter(
                    valuation.pe_ratio / indicator.inc_net_profit_year_on_year>0,
                    valuation.pe_ratio / indicator.inc_net_profit_year_on_year<1,
                    # indicator.roe / valuation.pb_ratio > 1,
                    valuation.code.in_(sample))
    df_fundamentals = get_fundamentals(q, date = None)   

    g.stocks = list(df_fundamentals.code)
   
    get_signal(context,g.stocks)


# 获得交易信号，股票池是g.stocks
def get_signal(context,stocks):
   
    # 定义year为去年
    year = context.current_dt.year-1
    print(year)
    # 得到运行该函数的日期数字（后文没有使用该变量currenttime）
    # datetime.datetime格式
    currenttime = int(str(context.current_dt)[0:4]+\
    str(context.current_dt)[5:7]+str(context.current_dt)[8:10])
    
    #获取【聚源数据】对应的股票内部代码
    stocks_symbol=[]
    #将股票代码变为6位数字
    for s in stocks:
        stocks_symbol.append(s[0:6]) #append 添加
    stocklis_company_code=jy.run_query(query(
        jy.SecuMain.InnerCode,
        jy.SecuMain.SecuCode
    ).filter( jy.SecuMain.SecuCode.in_(stocks_symbol),jy.SecuMain.SecuCategory==1
    ))
    #stocklist_company_code_name即为股票对应的聚源数据Innercode
    #print(stocklis_company_code)
    stocklist_company_code_name=list(stocklis_company_code['InnerCode'])
    #获取股票分红数据
    dataframe=pd.DataFrame(columns=['InnerCode','CashDiviRMB','AdvanceDate'])
    for stock in stocklist_company_code_name:
        df = jy.run_query(query(
            jy.LC_Dividend.InnerCode,
            jy.LC_Dividend.CashDiviRMB,
            jy.LC_Dividend.AdvanceDate
        ).filter( jy.LC_Dividend.InnerCode == (stock),
                  jy.LC_Dividend.IfDividend == 1
        )).dropna(axis = 0)
        if (df.empty) == False:#df是否为空
            AdvanceDate_list=list(df['AdvanceDate'])
            #print(AdvanceDate_list)
            for i in range (0,len(AdvanceDate_list)):
                #print(AdvanceDate_list[i])
                if int(((str(AdvanceDate_list[i])[0:4]+str(AdvanceDate_list[i])[5:7]+str(AdvanceDate_list[i])[8:10]))[0:4]) == year:
                    #print(df)
                    df=df.iloc[[i],:]#获得去年的股息
                    dataframe=pd.concat([dataframe,df],axis=0)
                    break
            
            
    dataframe.index=range(0,len(dataframe.index))
    #dataframe.columns=['InnerCode','CashDiviRMB ','AdvanceDate']
    #print((dataframe))
    #下一步，进行数据时间的获取
    df=dataframe
    #print(df)
    #将聚源数据内部股票代码变化为证券代码
    df_innercode_list=list(df['InnerCode'])
    
    stocklis_inner_code_to_sec=jy.run_query(query(
        
        jy.SecuMain.InnerCode,
        jy.SecuMain.SecuCode
    ).filter( jy.SecuMain.InnerCode.in_(df_innercode_list),jy.SecuMain.SecuCategory==1
        
    ))
    #print(stocklis_inner_code_to_sec) 
    df['sec_code']= stocklis_inner_code_to_sec['SecuCode']   
    del df['InnerCode']
    #print(df)
    #将索引变为股票代码
    df['sec_code'] = map(normalize_code,list(df['sec_code']))
    df.index = list(df['sec_code'])
    
    df = df.drop(['AdvanceDate','sec_code'],axis=1)
    
    # 并且将DIVIDENTBT列转换为float
    df['CashDiviRMB'] = map(float, df['CashDiviRMB'])
    
    # 按照股票代码分堆聚合（某些股票不仅一次分红）
    df = df.groupby(df.index).sum()

    # 得到20日股价均值，并向df内添加一列avg_close
    Price = history(20, unit='1d', field='close', security_list=list(df.index),  skip_paused=False, fq='pre')
    Price = Price.mean()
    Price = Price.T
    df['avg_close'] = Price
    
    #计算股息率divpercent = 股息/股票价格
    df['divpercent'] = df['CashDiviRMB']/df['avg_close']
    #divpercent_list = df['divpercent'].tolist()
    # 取股息率大于g.div的个股，如果不设置股息率阈值过滤，在股灾时刻回撤偏大
    df = df[(df.divpercent > g.div)] 
    # 按股息率降序排序
    df = df.sort(columns = ['divpercent'], axis=0, ascending=False) 
    
    # 取股票代码
    Buylist = list(df.index)
   
    # 过滤停牌退市ST股票，次新股
    Buylist = filter_stock_ST(Buylist)
    Buylist = remove_new_stocks(Buylist,context)
    Buylist = filter_stock_limit(Buylist)
    Buylist = Buylist[:g.stocknum]

   
    # 卖出买入股票（在追踪止损未生效时建仓，但不要考虑二八指数）
    if len(Buylist) > 0 and tralling_stop(context, '000300.XSHG') == 0:
    # if len(Buylist) > 0 :
        order_stock_sell(context,Buylist)
        order_stock_buy(context,Buylist)


# 执行卖出       
def order_stock_sell(context,order_list):
    # 对于不需要持仓的股票，全仓卖出
    for stock in context.portfolio.positions:
        # 除去buy_list内的股票，其他都卖出
        if stock not in order_list:
            order_target_value(stock, 0)
           
           
# 执行买入           
def order_stock_buy(context,order_list):
    print len(context.portfolio.positions)
    # 先求出可用资金，如果持仓个数小于g.stocknum
    if len(context.portfolio.positions) < g.stocknum:
        # 求出要买的数量num
        num = g.stocknum - len(context.portfolio.positions)
        # 求出每只股票要买的金额cash
        g.each_stock_cash = context.portfolio.cash/num
    else:
        # 如果持仓个数满足要求，不再计算g.each_stock_cash
        cash = 0
        num = 0
    # 执行买入
    for stock in order_list:
        if stock not in context.portfolio.positions:
            order_target_value(stock, g.each_stock_cash)     


# 过滤停牌退市ST股票，选股时使用
def filter_stock_ST(stock_list):
    curr_data = get_current_data()
    for stock in stock_list:
        if (curr_data[stock].paused) or (curr_data[stock].is_st) or ('ST' in curr_data[stock].name)\
            or ('*' in curr_data[stock].name)\
            or ('退' in curr_data[stock].name):
            stock_list.remove(stock)
    return stock_list
   
   
# 过滤每日开盘时的涨跌停股filter low_limit/high_limit   
def filter_stock_limit(stock_list): 
    curr_data = get_current_data()
    for stock in stock_list:
        price = curr_data[stock].day_open
        if (curr_data[stock].high_limit <= price) or (price <= curr_data[stock].low_limit):
            stock_list.remove(stock)
    return stock_list


# 过滤上市180日以内次新股
def remove_new_stocks(security_list,context):
    for stock in security_list:
        days_public = (context.current_dt.date() - get_security_info(stock).start_date).days
        if days_public < 180:
            security_list.remove(stock)
    return security_list