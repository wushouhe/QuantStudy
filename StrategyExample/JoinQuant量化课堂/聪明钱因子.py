# 标题：聪明钱因子改进+ATR仓位控制+市值中性化
 
# 导入函数库
import jqdata
impor ttalib
import pandas as pd
import numpy as np
import datetime
from datetime import timedelta
import math
from numpy import nan
from statsmodels import regression
import statsmodels.apias sm
 
# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    g.num_stock = 20        # 持有股票数量
    g.index = '000905.XSHG' # 选股范围
    g.risk_ratio = 0.1     # 每次每只股票总资金允许的损失比率（该值建议设置0.05~0.1）
    g.ATR_timeperiod = 14   # set ATR 周期
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税,每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001,open_commission=0.0003, close_commission=0.0003, min_commission=5),type='stock')
    # 按月运行rebalence函数
    run_monthly(rebalence, 1)
 
       
# 重平衡函数（定期调仓买卖）
def rebalence(context):
    # stocklist是select_stock函数传入的名单
    stocklist = select_stock(context)
    # 清仓卖出
    order_stock_sell(context,stocklist)
    # 传统等量下单模式
    # order_stock_buy(context,stocklist)
    # ATR风险平价下单模式
    order_ATR_stock_buy(context,stocklist)
 
 
# 买入逻辑（通过ATR计算风险，调整仓位）
def order_ATR_stock_buy(context,order_list):
    # 首先计算stock_values是能够承受的亏损幅度，函数返回【个股持仓价值】
    stock_values =ATR_Position(context,order_list)
    for stock in stock_values:
        # 预计买入价值 = stock_values
        target_value = stock_values[stock]
        # 调整个股仓位到target_value
        order_target_value(stock,target_value)
 
 
# 执行卖出       
def order_stock_sell(context,order_list):
    # 对于不需要持仓的股票，全仓卖出
    for stock in context.portfolio.positions:
        # 除去buy_list内的股票，其他都卖出
        if stock not in order_list:
            order_target_value(stock, 0)
 
           
# 执行等仓位买入          
def order_stock_buy(context,order_list):
    # 先求出可用资金，如果持仓个数小于g.stocknum
    if len(context.portfolio.positions) <g.num_stock:
        # 求出要买的数量num
        num = g.num_stock -len(context.portfolio.positions)
        # 求出每只股票要买的金额cash
        g.each_stock_cash =context.portfolio.available_cash/num
    else:
        # 如果持仓个数满足要求，不再计算g.each_stock_cash
        cash = 0
        num = 0
    # 执行买入
    for stock in order_list:
        if stock not incontext.portfolio.positions:
            order_target_value(stock,g.each_stock_cash)           
           
           
# 过滤个股，并添加因子值，再排序后，去除因子值，返回个股名单
def select_stock(context):
    stocklist = get_index_stocks(g.index)
    # 停牌、退市、st、开盘涨跌停
    stock_list =filter_specials(stocklist) 
    # 新股和次新股
    stock_list =filter_new_and_sub_new(stock_list)
    factor_dict = {}
   
    # 从stock_list逐一取元素到factor_dict的过程中
    # factor_dict的index索引列等于stock_list，所以factor_dict只填充值
    for i in stock_list:
        temp = []
        # 调用get_smart_money函数，添加因子值到list：temp
        temp.append(get_smart_money(i))
        factor_dict[i] = temp
    df_factor = pd.DataFrame(factor_dict).T
    df_factor = df_factor.dropna()
   
   
    #获取股票的市值因子
    market_cap = get_fundamentals(
            query(valuation.market_cap)
           .filter(valuation.code.in_(df_factor.index.values))
        )
       
    # 市值中性化（输入原因子dataframe，市值因子dataframe）
    factor_neutra = mkt_cap_neutralization(df_factor,market_cap)
    # 重新构成新的DataFrame，构成索引列（股票代码）和值列（factor_neutra）
    df_new_factor = pd.DataFrame(index =df_factor.index.values) 
    df_new_factor['new_smart_money'] =factor_neutra
 
    # 获得排序后股票池
    df = df_new_factor.sort('new_smart_money')
    # 选出前g.num_stock只股票,.index.values取出了股票代码一列，另一列是因子值
    stock_list =list(df.index.values)[:g.num_stock]
    return stock_list
 
 
# 过滤新股和次新股——60日
def filter_new_and_sub_new(stocklist,days = 60):
    stock_list = []
    for stock in stocklist:
        start_date =get_security_info(stock).start_date
        if(datetime.date.today()-start_date)>timedelta(days):
            stock_list.append(stock)
    return stock_list
 
 
# 核心模块，计算10日内聪明钱因子值
def get_smart_money(stock):
    # df获取股票分钟数据[开盘、收盘、成交量]
    df =attribute_history(stock,2400,'1m',['open','close','high','low','volume'])
 
    # Bar_Return列是bar内回报绝对值（改为振幅）
    # df['Bar_Return'] =abs(df['close']/df['open']-1)
    df['Bar_Return'] =abs(df['high']/df['low']-1)
    # SS列是bar内回报绝对值，除以成交量开平方
    df['SS'] =df['Bar_Return']/(df['volume'].apply(math.sqrt))*10000
   
    # 在DataFrame内，以SS列为基准降序排序
    df = df.sort('SS',ascending = False)
   
    # 计算轴向元素累加和，计算【成交量】或【价格】
    # df['cum_vol'] = df['volume'].cumsum()
    df['cum_vol'] = df['close'].cumsum()
    # 计算1分钟内K线【成交量】或【价格】变动率
    df['cum_vol'] =df['cum_vol']/df.ix[-1,'cum_vol']
    # all_vol是所有成交量求和
    all_vol = df['volume'].sum()
   
    # df_smartQ = cum_vol列【1钟内K线【成交量】或【价格】变动率】小于0.2的部分
    df_smartQ = df[df['cum_vol'] <= 0.2]
    # all_smartvol聪明钱因子求和
    all_smartvol = df_smartQ['volume'].sum()
    # 计算两个VWAP求和
    VWAP_smart =(df_smartQ['volume']*df_smartQ['close']/all_smartvol).sum()
    VWAP_all =(df['volume']*df['close']/all_vol).sum()
    try:
        # 因子值 = 成交量加权平均价 / 所有交易的成交量加权平均价
        factor = VWAP_smart / VWAP_all
    except:
        factor = nan
    return factor
       
          
# 过滤停牌、退市、st、开盘涨跌停   
def filter_specials(stock_list):
    curr_data = get_current_data()
    stocklist = []
    for stock in stock_list:
        price = attribute_history(stock, 1,'1m', 'close')
        price = price.values[0][0]
        if (not curr_data[stock].paused)\
            and (not curr_data[stock].is_st)\
            and ('ST' not incurr_data[stock].name)\
            and ('*' not in curr_data[stock].name)\
            and ('退' not in curr_data[stock].name)\
            and (curr_data[stock].low_limit< price < curr_data[stock].high_limit):
            stocklist.append(stock)  
    return stock_list
 
 
# 这是典型的资金管理模块，让个股头寸和ATR建立负相关，在波动较高时，给个股更小的头寸
def ATR_Position(context, buylist):
    # 每次调仓，用 positionAdjustFactor(总资产*损失比率) 来控制承受的风险
    # positionAdjustValue：最大损失的资金量
    positionAdjustValue =context.portfolio.available_cash * g.risk_ratio
    # Ajustvalue_per_stock是个股能承受的最大损失资金量（等分）
    Adjustvalue_per_stock =float(positionAdjustValue)/len(buylist)
   
    # 取到buylist个股名单上一个1分钟收盘价，df=False不返回df数据类型
    hStocks = history(1, '1m', 'close',buylist, df=False)
    # 建立一个dataframe：risk_value
    # 第一列是buylist股票代码，第二列是risk_value
    risk_value = {}
    # 计算个股动态头寸risk_value
    for stock in buylist:
        # curATR是2倍日线ATR值，输出转化成浮点数
        curATR = 2*float(fun_getATR(stock))
        if curATR != 0 :
            # 拆解分析：当前价 * 个股能承受的最大损失资金量是【个股持仓价值】
            # 如果不除以curATR，说明不进行个股头寸波动性变化
            # ATR越大，个股risk_value越小；ATR越小，个股risk_value越大
            # 说明波动性和个股持仓价值应该负相关（进行个股持仓量动态分配），这符合资金管理或者资产配置原则
            risk_value[stock] =hStocks[stock]*Adjustvalue_per_stock/curATR
            # risk_value[stock] =Adjustvalue_per_stock
        else:
            risk_value[stock] = 0
    # 到此为止计算出个股应该持有的风险价值
    return risk_value
 
 
# 计算日线级别ATRlag周期ATR
def fun_getATR(stock):
    try:
        hStock = attribute_history(stock,g.ATR_timeperiod+10, '1d', ('close','high','low') , df=False)
    except:
        log.info('%s 获取历史数据失败' %stock)
        return 0
    # 去极值，然后送入ATR函数，细致处理
    close_ATR =hStock['close']
    high_ATR =hStock['high']
    low_ATR = hStock['low']
    try:
        ATR = talib.ATR(high_ATR, low_ATR,close_ATR, timeperiod = g.ATR_timeperiod)
    except:
        return 0
    # 返回前一个ATR值
    return ATR[-1]
   
 
# 市值中性化函数   
# 需要传入单个因子值和总市值(DataFrame数据类型)
# 输出因子值和市值回归后的残差
def mkt_cap_neutralization(factor,mkt_cap):
    # factor为待中性化的因子值序列
    # 对mkt_cap取对数
    y = factor.values
    x = np.log(mkt_cap.values)
    resid = linreg(y,x)
    # resid残差即为纯净的中性化后因子值
    return resid
    # 返回factor为原因子值，也就是不做市值中性
    # return factor
   
   
# 求线性回归残差
# 支持list,array,DataFrame等三种数据类型
def linreg(y,x):
    y = array(y)
    x = sm.add_constant(array(x))
    if len(y)>1:
        model =regression.linear_model.OLS(y,x).fit()
    return model.resid