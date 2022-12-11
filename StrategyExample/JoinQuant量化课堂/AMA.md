将改进版 AMA 系统运用于股票指数，映射到 3 只 ETF 基金交易（只做多）

//------------------------------------------------------------------------
// 简称: AMA_ETF
// 名称:
// 类别: 公式应用
// 类型: 用户应用
// 输出:
//------------------------------------------------------------------------

Params

    Numeric money(100000);  			// 单品种资金配置
    Numeric NATRstop(4);				// N倍ATR硬止损和追踪止损
    Numeric FilterSet2(0.26);		    // 常规走势过滤器，阈值系数，各品种不同
    Numeric EffRatioLength(12);			// ER系数周期，各品种不同

    // 30分钟线上，建议默认50-3-50。1小时和日线上，建议模型30-2-20
    Numeric FilterLength(50);
    Numeric FastAvgLength(3);
    Numeric SlowAvgLength(50);

Vars

Numeric ATRlength(14);
Numeric Lots;
Numeric MinPoint;
NumericSeries AMAValue; // 主要 AMA 线
Numeric filter2; // 【多头】抖动过滤器：n 周期以来的 AMA 值样本标准差\*过滤器系数

    Bool    LongEntryCon(false);       // 开多仓
    Bool    ShortEntryCon(false);      // 开空仓

    NumericSeries HighestAfterEntry;   // 开仓后出现的最高价
    NumericSeries LowestAfterEntry;    // 开仓后出现的最低价
    Numeric MyExitPrice;	           // 硬止损出场均价，平仓价格

    BoolSeries TS_Reentry_long ;	   // 多头TS追踪止损后，防止重入模块

    BoolSeries stoploss_hard_long(False);
    BoolSeries BIAS_R_long(False);
    BoolSeries Normal_Trailing_long(False);

    BoolSeries gap_long;

    BoolSeries No_buy_sellshort;

    NumericSeries ATR;            		// 本周期ATR
    BoolSeries reconSF(false);          // 过年和长假平仓条件
    NumericSeries posbefSF;             // 过年和长假平仓前，信号值（年后重新恢复）

    NumericSeries Highest_high_1_30;	// 30周期高点1
    NumericSeries Lowest_low_1_30;		// 30周期低点1

    NumericSeries Highest_high_2_30;	// 20周期高点1
    NumericSeries Lowest_low_2_30;		// 20周期低点1

    BoolSeries downto30bars ;

    NumericSeries lowD1;

    NumericSeries all_PositionProfit;
    NumericSeries PositionRange;
    NumericSeries Portfolio_CurrentEquity_;
    NumericSeries TotalEquity;

Begin

    If( !CallAuctionFilter() ) Return;                      // 过滤集合竞价
    If( date!=date[1] and high==low ) Return;               // 本bar价格异常

    all_PositionProfit = PositionProfit/ money;
    Commentary("单笔盈利幅度 ="+ Text(all_PositionProfit)) ;

    PositionRange = (close - AvgEntryPrice) / AvgEntryPrice ;
    Commentary("价格运行幅度 ="+ Text(PositionRange)) ;

    Portfolio_CurrentEquity_ = Portfolio_CurrentEquity;
    Commentary("动态权益 ="+ Text(Portfolio_CurrentEquity_)) ;

    lowD1 = lowD(1);

    lots = money / (open*ContractUnit()*BigPointValue());


    // 农历新年，国庆节长假，平仓
    reconSF =
     ( Date == 20170126 && Time == 0.140000 )
    || ( Date == 20160205 && Time == 0.140000 )
    || ( Date == 20150217 && Time == 0.140000 )
    || ( Date == 20140130 && Time == 0.140000 )
    || ( Date == 20130208 && Time == 0.140000 )
    || ( Date == 20120120 && Time == 0.140000 )
    || ( Date == 20110201 && Time == 0.140000 )
    || ( Date == 20100212 && Time == 0.140000 )
    || ( Date == 20090123 && Time == 0.140000 )

    || ( Date == 20170929 && Time == 0.140000 )
    || ( Date == 20160930 && Time == 0.140000 )
    || ( Date == 20150930 && Time == 0.140000 )
    || ( Date == 20140930 && Time == 0.140000 )
    || ( Date == 20130930 && Time == 0.140000 )
    || ( Date == 20120928 && Time == 0.140000 )
    || ( Date == 20110930 && Time == 0.140000 )
    || ( Date == 20100930 && Time == 0.140000 )
    || ( Date == 20090930 && Time == 0.140000 ) ;

    Highest_high_1_30 = Highest(high[1],30);
    Lowest_low_1_30 = Lowest(low[1],30);

    Highest_high_2_30 = Highest(high[2],30);
    Lowest_low_2_30 = Lowest(low[2],30);


    // ========================= 以下是AMA值和过滤器计算 =============================

    AMAValue = AdaptiveMovAvg(close[1],EffRatioLength,FastAvgLength,SlowAvgLength);

    PlotNumeric("AMAValue",AMAValue,0,yellow);

    filter2 = StandardDev(AMAValue, FilterLength ,1)*FilterSet2;  // 连续过滤器

    ATR = XAverage(TrueRange,ATRlength);


    // 以下是开仓条件


    if((AMAValue - AMAValue[1]) >= filter2 )
    LongEntryCon = true;

    if((AMAValue[1] - AMAValue) >= filter2 )
    ShortEntryCon = true;


    // TS止损后，止损平仓30个bar之内，不允许入场条件，之外条件失效（多）
    TS_Reentry_long =
    ( BIAS_R_long == True || Normal_Trailing_long == True ) // 止损平仓
    && close[1] < Highest_high_2_30  // 价格没有创30周期新高，没有有效突破
    && BarsSinceExit < 30 ;			// 止损平仓30个bar之内


    // 特殊时段标准差增加过滤
    No_buy_sellshort = ( Weekday == 1 || date - date[1] >= 2 ) && time == 0.0900 ;

    // 正常开仓
    if( MarketPosition != 1 && LongEntryCon
    && !No_buy_sellshort
    && !TS_Reentry_long
    && !reconSF && !reconSF[1] && !reconSF[2] )
    {
    	buy(lots,Open);
    	Normal_Trailing_long = False;
    	BIAS_R_long = False;
    	stoploss_hard_long = False;
    }

    if( MarketPosition == 1 && ShortEntryCon
    && !No_buy_sellshort
    && !reconSF && !reconSF[1] && !reconSF[2] )
    {
    	Sell(0,Open);
    }


    // 以下是跟踪止损计算

    if ( BarsSinceEntry == 1 )     // 开仓后第一个bar，直接等于开仓价
    {
    HighestAfterEntry = AvgEntryPrice;
    }

    Else If( BarsSinceEntry > 1 )   // 之后的bar，不断用最高和最低价做比对，赋值给开仓后最高最低价
    {
    HighestAfterEntry = Max(HighestAfterEntry[1],high[1]); // 初步测试，在high[1]和low[1]情况下，下bar常规回落止损最好！
    }

    Else                          // 没有仓位时，保持上次价格信息，没有其他用途
    {
    HighestAfterEntry = HighestAfterEntry[1];
    }

    // 向下跳空(或大幅度加空)，多头止损不启动
    gap_long = open - close[1] < -1*atr[1]
    && ( time == 0.090000 || time == 0.210000 );


    	If( MarketPosition == 1 && BarsSinceEntry > 1  && !gap_long
    	&& HighestAfterEntry - AvgEntryPrice > 2*NATRstop*atr[1] ) // 有多仓
    		{
    			If(low <= HighestAfterEntry - 2*NATRstop*atr[1] )
    			{
    			Sell(0,Min(Open, HighestAfterEntry - 2*NATRstop*atr[1]  ) );
    			Normal_Trailing_long = True ;
    			PlotString ("TrailingStop","TrailingStop",high*1.01,White);
    			}
    		}
    	}


    	// 硬止损平仓

    	downto30bars = low < lowD1 ;
    	// 确认非常需要止损的时候，再止损
    	//但是实测部分品种有性能提升，1bar

    	If( MarketPosition == 1 && BarsSinceEntry > 0  && !gap_long    && downto30bars
    	&& Low <= AvgEntryPrice - NATRstop*atr[1] )   // 多仓情况
    	{
    		MyExitPrice = Min (Open, Min(AvgEntryPrice - NATRstop*atr[1] , lowD1) );
    		Sell(0,MyExitPrice); 	    //多头止损平仓
    		PlotString ("HardStop","HardStop",high*1.01,White);
    		stoploss_hard_long = True ;
    	}

    // =======================新年前，春节前，国庆前，14点平仓=======================

    If( reconSF )
    {
    	posbefSF = marketposition;     // 先记录下当时的信号，以便节后重新开仓，然后平仓
    	Sell(0,Open);
    	PlotString ("IMP Festival","IMP Festival",close*0.99,White);
    }


    // 节后，第一个交易日11:00重新开仓
    if (marketposition == 0 && reconSF[3] && posbefSF != 0 )
    {
    	PlotString ("IMP Festival","AftF",close*0.99,White);

    	if (posbefSF == 1 )
    	{
    		Buy(lots,open);
    	}

    }

End
