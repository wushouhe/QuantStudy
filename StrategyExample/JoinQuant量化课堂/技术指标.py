# 标题：MACD、BOLL、KDJ、RSI、CCI、MTM、CMO、相关系数、线性回归等指标和统计方法测试模板

import talib


def initialize(context):
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
    # 设置最大持仓股票数量
    g.buyStockCount = 50
    # 记录买入后的最高价top值
    g.top = {}
    # 设置股票池
    g.stockpool = "000300.XSHG"
    # 日期计数器开始值
    g.days = 0
    # 调仓间隔周期
    g.refresh_rate = 5


# 过滤股票，过滤停牌退市ST股票，选股时使用
def filter_stock_ST(stock_list):
    curr_data = get_current_data()
    for stock in stock_list[:]:
        if (
            (curr_data[stock].paused)
            or (curr_data[stock].is_st)
            or ("ST" in curr_data[stock].name)
            or ("*" in curr_data[stock].name)
            or ("退" in curr_data[stock].name)
        ):
            stock_list.remove(stock)
    return stock_list


# 交易时使用，过滤每日开盘时的涨跌停股filter low_limit/high_limit
def filter_stock_limit(stock_list):
    curr_data = get_current_data()
    for stock in stock_list[:]:
        price = curr_data[stock].day_open
        if (curr_data[stock].high_limit <= price) or (
            price <= curr_data[stock].low_limit
        ):
            stock_list.remove(stock)
    return stock_list


# 可选项: 过滤上市180日以内次新股
def remove_new_stocks(security_list, context):
    for stock in security_list[:]:
        days_public = (
            context.current_dt.date() - get_security_info(stock).start_date
        ).days
        if days_public < 180:
            security_list.remove(stock)
    return security_list


# 进行回测
def handle_data(context, data):

    # ===================== 个股单独的买入逻辑 =====================
    # 取得当前的现金
    cash = context.portfolio.available_cash

    # 定义optional_list为买入操作名单
    if cash > 0 and g.days % g.refresh_rate == 0:
        optional_list = []
        sample = get_index_stocks(g.stockpool)
        # 过滤停牌退市ST股票，次新股，涨跌停板股
        sample = filter_stock_ST(sample)
        sample = remove_new_stocks(sample, context)
        sample = filter_stock_limit(sample)

        # 循环股票列表，计算指标值
        for stock in sample:
            # 获取第stock只股票的历史数据
            # 这里要注意语法问题，涉及到取多列数据，要加入['close','high','low']
            close_data = attribute_history(
                stock, 60, "1d", ["close", "high", "low", "volume"]
            )
            close_data.fillna(0, inplace=True)
            # 导入收盘价和参数fastperiod=12, slowperiod=26, signalperiod=9，计算出macd, macdsignal, macdhist
            # 因为默认返回pandas.DataFrame，所以表示每一列，要加入[列名].values
            macd_DIF, macd_DEA, macd_macd = talib.MACD(
                close_data["close"].values, fastperiod=12, slowperiod=26, signalperiod=9
            )
            # DIF = EMA(close，12）-EMA（close，26）等于快线慢线离差，等同于双均线交易规则
            # EDA = 前一日DEA×8/10+今日DIF×2/10
            # MACD指标值 = （DIF-DEA）×2

            upperband, middleband, lowerband = talib.BBANDS(
                close_data["close"].values,
                timeperiod=30,
                nbdevup=2,
                nbdevdn=2,
                matype=0,
            )
            # 布林带指标，先求中轨是timeperiod周期移动平均线
            # 然后求timeperiod周期内价格标准差
            # 上轨upperband = middleband + nbdevup*标准差
            # 下轨lowerband = middleband - nbdevdn*标准差

            RSI_line = talib.RSI(close_data["close"].values, timeperiod=20)
            # 相对强弱指标RSI = N日内收盘涨幅的平均值/(N日内收盘涨幅均值+N日内收盘跌幅均值) ×100%

            CCI_line = talib.CCI(
                close_data["high"].values,
                close_data["low"].values,
                close_data["close"].values,
                timeperiod=20,
            )
            # CCI(n) 公式= (TP－MA) ÷MD ÷0.015
            # 变量TP = (最高价 + 最低价 + 收盘价) ÷ 3
            # 变量MA = 最近n日收盘价的累计和÷n
            # 变量MD = 最近n日(MA - 收盘价)的绝对值的累计和 ÷ n

            MOM_line = talib.MOM(close_data["close"].values, timeperiod=20)
            # 动量线也被简写为MTM = close - close[timeperiod] 昨日收盘价与N日前收盘价的差

            slowk, slowd = talib.STOCH(
                close_data["high"].values,
                close_data["low"].values,
                close_data["close"].values,
                fastk_period=9,
                slowk_period=3,
                slowk_matype=0,
                slowd_period=3,
                slowd_matype=0,
            )
            # KDJ指标首先计算n日RSV=（收盘－最低）/（最高－最低）×100
            # 当日K值=2/3×前一日K值+1/3×当日RSV
            # 当日D值=2/3×前一日D值+1/3×当日K值
            # 若无前一日K 值与D值，则可分别用50来代替。
            # J值=3*当日K值-2*当日D值

            CMO_line = talib.CMO(close_data["close"].values, timeperiod=20)
            # 钱德动量摆荡指标
            # SU:=IF(C>REF(C,1),SUM(C-REF(C,1),0),0);
            # SD:=IF(C<REF(C,1),SUM(C-REF(C,1),0),0);
            # CMO:=(SU-SD)/(SU+SD);

            OBV_line = talib.OBV(
                close_data["close"].values, close_data["volume"].values
            )
            # On Balance Volume能量潮指标
            # SUM(IF(CLOSE>REF(CLOSE,1),VOL,IF(CLOSE<REF(CLOSE,1),-VOL,0)),0);
            # 如果本日收盘价或指数高于前一日收盘价或指数，本日值则为正；
            # 如果本日的收盘价或指数低于前一日的收盘价，本日值则为负值；
            # 如果本日值与前一日的收盘价或指数持平，本日值不计算，然后计算累积成交量。

            CORR = talib.CORREL(
                close_data["close"].values, close_data["volume"].values, timeperiod=20
            )
            # 相关系数函数：皮尔逊相关系数，是用来度量两个变量 X 和 Y 之间的相互关系（线性相关）
            # 取值范围在 [-1,+1] 之间

            price_SLOPE = talib.LINEARREG_SLOPE(
                close_data["close"].values, timeperiod=20
            )
            # 线性回归斜率：用最小二乘法拟合，得到一条近似的直线函数y=ax+b，
            # a是拟合直线的斜率，b是截距

            # ===================== 指标买入逻辑 =====================
            # MACD买入逻辑
            # if (macd_macd[-2] > 0 and macd_macd[-1] < 0): # 动量
            # if (macd_macd[-2] > 0 and macd_macd[-1] < 0): # 反转

            # 布林带买入逻辑
            # if (close_data['close'][-2] < upperband and close_data['close'][-1] > upperband): # 动量
            # if (close_data['close'][-2] > lowerband and close_data['close'][-1] < lowerband): # 反转

            # RSI买入逻辑
            # if (RSI_line[-2] < 70 and RSI_line[-1] > 70): # 动量
            # if (RSI_line[-2] > 50 and RSI_line[-1] < 50): # 反转

            # CCI买入逻辑
            # if (CCI_line[-2] < 100 and CCI_line[-1] > 100): # 动量
            # if (CCI_line[-2] > -100 and CCI_line[-1] < -100): # 反转

            # MOM买入逻辑
            # if (MOM_line[-2] < 0 and MOM_line[-1] > 0): # 动量
            # if (MOM_line[-2] > 0 and MOM_line[-1] < 0): # 反转

            # KDJ买入逻辑
            # if (slowk[-2] > 90 or slowd[-1] > 90): # 动量
            # if (slowk[-2] < 10 or slowd[-1] < 10): # 反转

            # CMO买入逻辑
            # if (CMO_line[-2] < 50 or CMO_line[-1] > 50): # 动量
            # if (CMO_line[-2] > 50 or CMO_line[-1] < 50): # 反转

            # OBV买入逻辑
            # if (OBV_line[-2] < 50 or OBV_line[-1] > 50): # 动量
            # if (OBV_line[-2] > 50 or OBV_line[-1] < 50): # 反转

            # CORR买入逻辑
            # if (CORR.mean() > 0): # 量价匹配
            # if (CORR.mean() < 0): # 量价背离

            # price_SLOPE买入逻辑
            # if (price_SLOPE[-1] > 0): # 动量
            # if (price_SLOPE[-1] < 0): # 反转

            # 如果按照金叉死叉交易，要启用if条件，注意代码缩进
            # optional_list.append(stock)

            # 如果启用指标值排序交易，不需要启用上述if条件
            optional_list.append((stock, RSI_line[-1]))

        # 以指标值强度做【升序排名】，指标值小排名靠前，优先买入（反转模式）
        # optional_list.sort(key = lambda l: l[1], reverse = False )

        # 以指标值强度做【降序排名】，指标值大排名靠前，优先买入（动量模式）
        optional_list.sort(key=lambda l: l[1], reverse=True)

        # 转化成np.array结构，方便取出第一列数据（股票代码），然后再转回list数据类型
        optional_list = np.array(optional_list)
        optional_list = optional_list[:, 0].tolist()

        # 限定买入名单数量
        optional_list = optional_list[: g.buyStockCount]
        # 执行买入函数
        buy_Stocks(optional_list, context)

        # 买入结束后，计数器递增
        g.days += 1
    else:
        g.days += 1


# 买入股票函数
def buy_Stocks(optional_list, context):
    # 初始化应买入股票数量valid_count
    # 如果某只个股在仓位中，且持仓>0，valid_count递增1
    valid_count = 0
    # for stock, close in optional_list:
    for stock in optional_list:
        if (
            stock in context.portfolio.positions.keys()
        ):  # context.portfolio.positions[stock].total_amount > 0:
            valid_count = valid_count + 1
    # optional_list完全卖光，或valid_count == 买入股票个数（完全满仓），停止计算
    if len(optional_list) == 0 or valid_count == g.buyStockCount:
        return

    # 每只个股持有价值 = 总价值 / 目前应买入股票数量
    value = context.portfolio.available_cash / (g.buyStockCount - valid_count)
    for stock in optional_list:
        if stock in context.portfolio.positions.keys():
            pass
        else:
            order_target_value(stock, value)
