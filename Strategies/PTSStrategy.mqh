// PTSStrategy.mqh - Pullback Trading System Strategy v4.1 - REVISED
//+------------------------------------------------------------------+
//| Description: Implementation of Pullback Trading System (PTS)     |
//|              v4.1 with more reasonable Layer 1 parameters        |
//+------------------------------------------------------------------+
#ifndef PTSSTRATEGY_MQH
#define PTSSTRATEGY_MQH

// Note: Use relative path to include parent directory files
#include "..\StrategyBase.mqh"
#include "..\ScannerCore.mqh"
#include "..\TradeLogger.mqh"
#include "..\Symbols.mqh"

//+------------------------------------------------------------------+
//| PTS-specific structures                                          |
//+------------------------------------------------------------------+
struct PTSQualifiedPair
{
    string symbol;
    string direction;
    datetime qualificationTime;
    double bbPosition;    // NEW: BB position (0-1)
    double emaSlope;      // NEW: EMA50 slope
    double atrRatio;      // NEW: ATR ratio vs 50-day average
    double adxValue;      // NEW: ADX value
};

struct PTSEntryConditions
{
    bool bbTouch;          // Price touched Bollinger Band
    bool reversalSignal;   // Reversal candle pattern detected
    double atrValue;       // Current ATR(14) value on H4
    double bbUpper;        // Upper Bollinger Band
    double bbLower;        // Lower Bollinger Band
    double bbMiddle;       // Middle Bollinger Band (SMA20)
};

//+------------------------------------------------------------------+
//| PTS Strategy Class                                               |
//+------------------------------------------------------------------+
class CPTSStrategy : public CStrategyBase
{
private:
    // PTS-specific settings
    string            m_csvFileName;
    double            m_atrMultiplierSL;  // SL multiplier (2.0)
    double            m_atrMultiplierTP;  // TP multiplier (4.0)
    int               m_bbPeriod;         // Bollinger Band period (20)
    double            m_bbDeviation;      // Bollinger Band deviation (2.0)
    int               m_atrPeriod;        // ATR period (14)
    
    // NEW: Layer 1 parameters from v4.1 - REVISED for better trade frequency
    double            m_emaSlopeThreshold;    // EMA50 slope threshold (RELAXED)
    double            m_longBBMin;           // LONG BB position min (EXPANDED)
    double            m_longBBMax;           // LONG BB position max (EXPANDED)
    double            m_shortBBMin;          // SHORT BB position min (EXPANDED)
    double            m_shortBBMax;          // SHORT BB position max (EXPANDED)
    double            m_atrRatioThreshold;   // ATR ratio threshold
    int               m_adxMinValue;         // ADX minimum value (LOWERED)
    
    // Qualified pairs for today
    PTSQualifiedPair  m_qualifiedPairs[100];
    int               m_qualifiedCount;
    datetime          m_lastQualificationDate;
    
    // For CSV operations
    string            m_csvFilePath;
    
public:
    // Constructor - REVISED PARAMETERS
    CPTSStrategy() : CStrategyBase()
    {
        m_strategyName = "Pullback_Trading_System";
        m_type = STRATEGY_TYPE_PTS;
        
        // PTS-specific defaults
        m_csvFileName = "QualifiedPairs.csv";
        m_atrMultiplierSL = 2.0;
        m_atrMultiplierTP = 4.0;
        m_bbPeriod = 20;
        m_bbDeviation = 2.0;
        m_atrPeriod = 14;
        m_qualifiedCount = 0;
        m_lastQualificationDate = 0;
        
        // NEW: v4.1 Layer 1 parameters - REVISED FOR BETTER FREQUENCY
        m_emaSlopeThreshold = 0.00008;    // ~0.8 pips/day (RELAXED from 0.00015)
        m_longBBMin = 0.30;               // 25% of BB channel (EXPANDED from 0.35)
        m_longBBMax = 0.80;               // 85% of BB channel (EXPANDED from 0.75)
        m_shortBBMin = 0.20;              // 15% of BB channel (EXPANDED from 0.25)
        m_shortBBMax = 0.70;              // 75% of BB channel (EXPANDED from 0.65)
        m_atrRatioThreshold = 0.5;        // 50% of average ATR
        m_adxMinValue = 15;               // ADX minimum (LOWERED from 18)
        
        // Default settings
        m_settings.name = m_strategyName;
        m_settings.enabled = false;
        m_settings.lotSize = 0.01;
        m_settings.dailyLossLimit = 100.0;
        m_settings.maxPositions = 10;
        m_settings.magicNumber = 202412;
        
        // Build CSV file path
        m_csvFilePath = m_csvFileName;
    }
    
    // Destructor
    ~CPTSStrategy() {}
    
    // Initialize strategy
    virtual bool Initialize() override
    {
        Print("Initializing PTS Strategy v4.1 (REVISED): ", m_strategyName);
        
        if(!ValidateSettings())
        {
            Print("ERROR: PTS Strategy settings validation failed");
            return false;
        }
        
        // Load qualified pairs if CSV exists
        LoadQualifiedPairs();
        
        Print("PTS Strategy v4.1 (REVISED) initialized successfully");
        PrintSettings();
        return true;
    }
    
    // Deinitialize strategy
    virtual void Deinitialize() override
    {
        Print("Deinitializing PTS Strategy: ", m_strategyName);
        m_qualifiedCount = 0;
    }
    
    // Check for signal on specific symbol/timeframe
    virtual BaseSignal CheckSignal(string symbol, ENUM_TIMEFRAMES timeframe) override
    {
        BaseSignal signal;
        signal.symbol = symbol;
        signal.strategyName = m_strategyName;
        signal.timeframe = TimeframeToString(timeframe);
        
        // PTS only trades on H4 timeframe
        if(timeframe != PERIOD_H4)
            return signal;
        
        // Check if symbol is qualified for today
        string direction = GetQualifiedDirection(symbol);
        if(direction == "")
            return signal;
        
        // Check if we already have a position on this symbol
        if(HasOpenPosition(symbol))
            return signal;
        
        // Check entry conditions
        PTSEntryConditions conditions = CheckEntryConditions(symbol, direction);
        
        if(conditions.bbTouch && conditions.reversalSignal)
        {
            signal.signal = (direction == "LONG") ? "BUY" : "SELL";
            signal.price = (direction == "LONG") ? 
                          SymbolInfoDouble(symbol, SYMBOL_ASK) : 
                          SymbolInfoDouble(symbol, SYMBOL_BID);
            signal.value1 = conditions.atrValue;  // ATR value
            signal.value2 = (direction == "LONG") ? conditions.bbLower : conditions.bbUpper; // BB value
            signal.action = m_settings.enabled ? "TRADED" : "SCREENED";
            signal.comment = "PTS v4.1R: H4 Pullback " + direction;
            
            Print("PTS v4.1R Signal: ", signal.signal, " ", symbol, 
                  " ATR: ", DoubleToString(conditions.atrValue, 5),
                  " BB Touch: ", DoubleToString(signal.value2, 5));
        }
        
        return signal;
    }
    
    // Execute signal with PTS-specific risk management
    virtual bool ExecuteSignal(BaseSignal &signal) override
    {
        if(!m_settings.enabled || signal.signal == "")
            return false;
        
        if(signal.action != "TRADED")
            return false;
        
        // Check daily loss limit
        if(GetTodayPNL() <= -m_settings.dailyLossLimit)
        {
            Print("Daily loss limit reached for PTS Strategy: $", DoubleToString(GetTodayPNL(), 2));
            return false;
        }
        
        // Check max positions
        if(CountOpenPositions() >= m_settings.maxPositions)
        {
            Print("Max positions reached for PTS Strategy: ", CountOpenPositions());
            return false;
        }
        
        // Calculate SL and TP based on ATR
        double atrValue = signal.value1;
        double slDistance = m_atrMultiplierSL * atrValue;
        double tpDistance = m_atrMultiplierTP * atrValue;
        
        // Execute trade
        ENUM_ORDER_TYPE orderType = (signal.signal == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
        
        MqlTradeRequest request;
        MqlTradeResult result;
        ZeroMemory(request);
        ZeroMemory(result);
        
        request.action = TRADE_ACTION_DEAL;
        request.symbol = signal.symbol;
        request.volume = m_settings.lotSize;
        request.type = orderType;
        request.magic = m_settings.magicNumber;
        
        if(orderType == ORDER_TYPE_BUY)
        {
            request.price = SymbolInfoDouble(signal.symbol, SYMBOL_ASK);
            request.sl = NormalizeDouble(request.price - slDistance, 
                                        (int)SymbolInfoInteger(signal.symbol, SYMBOL_DIGITS));
            request.tp = NormalizeDouble(request.price + tpDistance, 
                                        (int)SymbolInfoInteger(signal.symbol, SYMBOL_DIGITS));
        }
        else // SELL
        {
            request.price = SymbolInfoDouble(signal.symbol, SYMBOL_BID);
            request.sl = NormalizeDouble(request.price + slDistance, 
                                        (int)SymbolInfoInteger(signal.symbol, SYMBOL_DIGITS));
            request.tp = NormalizeDouble(request.price - tpDistance, 
                                        (int)SymbolInfoInteger(signal.symbol, SYMBOL_DIGITS));
        }
        
        request.deviation = 10;
        request.comment = signal.comment;
        request.type_filling = ORDER_FILLING_IOC;
        request.type_time = ORDER_TIME_GTC;
        
        bool success = OrderSend(request, result);
        
        if(success && result.retcode == TRADE_RETCODE_DONE)
        {
            Print("PTS v4.1R trade executed: ", signal.signal, " ", signal.symbol,
                  " @ ", DoubleToString(request.price, 5),
                  " SL: ", DoubleToString(request.sl, 5),
                  " TP: ", DoubleToString(request.tp, 5),
                  " Risk-Reward: 1:", DoubleToString(m_atrMultiplierTP / m_atrMultiplierSL, 1));
            return true;
        }
        else
        {
            Print("PTS v4.1R trade failed: ", signal.signal, " ", signal.symbol,
                  " Error: ", GetTradeErrorDescription(result.retcode));
            return false;
        }
    }
    
    // Check if position should be exited (PTS uses fixed SL/TP, no early exits)
    virtual bool ShouldExitPosition(string symbol) override
    {
        // PTS uses fixed SL/TP, so no early exit signals
        return false;
    }
    
    // Timer event - PTS specific timing logic
    virtual void OnTimer() override
    {
        if(!m_settings.enabled)
            return;
        
        MqlDateTime currentTime;
        TimeCurrent(currentTime);
        
        // DEBUG: Print time occasionally
        static int debugCounter = 0;
        debugCounter++;
        if(debugCounter % 30 == 0)
        {
            Print("PTS Timer: ", currentTime.hour, ":", currentTime.min, 
                  ":", currentTime.sec, " | Total calls: ", debugCounter);
        }
        
        // 1. Check for 00:05 GMT for Daily Filter
        if(currentTime.hour == 0 && currentTime.min == 5)
        {
            // Prevent running multiple times in same minute
            static datetime lastDailyFilterRun = 0;
            if(TimeCurrent() - lastDailyFilterRun > 60)
            {
                Print("=== PTS v4.1R: 00:05 GMT - Running Daily Filter ===");
                RunDailyFilter();
                
                // Immediate H4 scan after daily filter
                Print("=== PTS v4.1R: Immediate H4 Scan after Daily Filter ===");
                RunH4Scan();
                
                lastDailyFilterRun = TimeCurrent();
            }
        }
        
        // 2. Check for H4 scan times (04:00, 08:00, 12:00, 16:00, 20:00 GMT)
        int h4ScanTimes[] = {4, 8, 12, 16, 20};
        bool isH4ScanTime = false;
        
        for(int i = 0; i < ArraySize(h4ScanTimes); i++)
        {
            if(currentTime.hour == h4ScanTimes[i] && currentTime.min == 0)
            {
                isH4ScanTime = true;
                break;
            }
        }
        
        // Run H4 scan at the correct times
        if(isH4ScanTime)
        {
            // Prevent running multiple times in same minute
            static datetime lastH4ScanRun = 0;
            if(TimeCurrent() - lastH4ScanRun > 60)
            {
                Print("=== PTS v4.1R: H4 Scan Time ", currentTime.hour, ":00 GMT ===");
                RunH4Scan();
                lastH4ScanRun = TimeCurrent();
            }
        }
    }
    
    // Run Daily Filter (Layer 1) - REVISED with more flexible conditions
    bool RunDailyFilter()
    {
        Print("=== PTS v4.1R Daily Filter Running (RELAXED) ===");
        
        // Reset qualified pairs
        m_qualifiedCount = 0;
        
        // Get all symbols from SymbolList.mqh
        int symbolCount = GetSymbolCount();
        int qualifiedToday = 0;
        
        for(int i = 0; i < symbolCount; i++)
        {
            string symbol = GetSymbol(i);
            
            if(!IsValidSymbol(symbol))
                continue;
            
            // Check D1 trend with 5 conditions (v4.1 REVISED)
            string direction = CheckDailyQualification(symbol);
            
            if(direction != "")
            {
                // Get qualification diagnostics
                double bbPos, emaSlope, atrRatio, adxValue;
                GetQualificationDiagnostics(symbol, direction, bbPos, emaSlope, atrRatio, adxValue);
                
                // Add to qualified pairs
                if(m_qualifiedCount < 100)
                {
                    m_qualifiedPairs[m_qualifiedCount].symbol = symbol;
                    m_qualifiedPairs[m_qualifiedCount].direction = direction;
                    m_qualifiedPairs[m_qualifiedCount].qualificationTime = TimeCurrent();
                    m_qualifiedPairs[m_qualifiedCount].bbPosition = bbPos;
                    m_qualifiedPairs[m_qualifiedCount].emaSlope = emaSlope;
                    m_qualifiedPairs[m_qualifiedCount].atrRatio = atrRatio;
                    m_qualifiedPairs[m_qualifiedCount].adxValue = adxValue;
                    m_qualifiedCount++;
                    qualifiedToday++;
                    
                    Print("v4.1R Qualified: ", symbol, " as ", direction,
                          " | BB Pos: ", DoubleToString(bbPos, 2),
                          " | EMA Slope: ", DoubleToString(emaSlope, 6),
                          " | ATR Ratio: ", DoubleToString(atrRatio, 2),
                          " | ADX: ", DoubleToString(adxValue, 1));
                }
            }
        }
        
        // Save to CSV file
        SaveQualifiedPairsToCSV();
        
        Print("v4.1R Daily Filter completed. Qualified pairs: ", qualifiedToday, " / ", symbolCount);
        return true;
    }
    
    // Check daily qualification for a symbol - REVISED with more flexibility
    string CheckDailyQualification(string symbol)
    {
        // Condition 1: Trend Direction (Close[1] vs EMA50[1])
        double closeYesterday = iClose(symbol, PERIOD_D1, 1);
        double ema50Yesterday = GetEMAValue(symbol, PERIOD_D1, 50, 1);
        
        if(closeYesterday == 0 || ema50Yesterday == 0)
            return "";
        
        bool isPotentialLong = false;
        bool isPotentialShort = false;
        
        if(closeYesterday > ema50Yesterday)
            isPotentialLong = true;
        else if(closeYesterday < ema50Yesterday)
            isPotentialShort = true;
        else
            return ""; // Close = EMA50, no clear trend
        
        // Condition 2: Trend Momentum (EMA50 slope) - MORE FLEXIBLE
        double emaSlope = CalculateEMA50Slope(symbol);
        if(emaSlope == 0)
            return "";
        
        if(isPotentialLong && emaSlope <= m_emaSlopeThreshold)
            return ""; // EMA not rising enough
        if(isPotentialShort && emaSlope >= -m_emaSlopeThreshold)
            return ""; // EMA not falling enough
        
        // Condition 3: Pullback/Rally Positioning (BB Position) - WIDER RANGES
        double bbPosition = CalculateBBPosition(symbol);
        if(bbPosition < 0) // Error
            return "";
        
        if(isPotentialLong)
        {
            if(bbPosition < m_longBBMin || bbPosition > m_longBBMax)
                return ""; // Not in LONG pullback zone
        }
        else if(isPotentialShort)
        {
            if(bbPosition < m_shortBBMin || bbPosition > m_shortBBMax)
                return ""; // Not in SHORT rally zone
        }
        
        // Condition 4: Volatility (ATR > 50% of 50-day average)
        double atrRatio = CalculateATRRatio(symbol);
        if(atrRatio <= m_atrRatioThreshold)
            return ""; // Insufficient volatility
        
        // Condition 5: Trend Strength (ADX > 15 OR rising) - MORE FLEXIBLE
        double adxCurrent = GetADXValue(symbol, PERIOD_D1, 14, 1);
        double adxPrevious = GetADXValue(symbol, PERIOD_D1, 14, 5);
        
        // Allow ADX > 15 OR ADX rising (even if below 15)
        if(adxCurrent <= m_adxMinValue && adxCurrent <= adxPrevious)
            return ""; // ADX too low AND not rising
        
        // All 5 conditions passed
        return isPotentialLong ? "LONG" : "SHORT";
    }
    
    // Alternative: 3-condition filter for maximum trade frequency
    string CheckDailyQualificationSimple(string symbol)
    {
        // 1. Basic trend direction
        double closeYesterday = iClose(symbol, PERIOD_D1, 1);
        double ema50Yesterday = GetEMAValue(symbol, PERIOD_D1, 50, 1);
        
        if(closeYesterday == 0 || ema50Yesterday == 0)
            return "";
        
        bool isPotentialLong = closeYesterday > ema50Yesterday;
        bool isPotentialShort = closeYesterday < ema50Yesterday;
        
        if(!isPotentialLong && !isPotentialShort)
            return "";
        
        // 2. Volatility check (lower threshold)
        double atrRatio = CalculateATRRatio(symbol);
        if(atrRatio <= 0.3) // Lower than 0.5 for more trades
            return "";
        
        // 3. EMA slope (more relaxed)
        double emaSlope = CalculateEMA50Slope(symbol);
        
        if(isPotentialLong && emaSlope <= 0.00005) // Much lower threshold
            return "";
        if(isPotentialShort && emaSlope >= -0.00005)
            return "";
        
        return isPotentialLong ? "LONG" : "SHORT";
    }
    
    // Calculate EMA50 slope over last 10 days
    double CalculateEMA50Slope(string symbol)
    {
        double emaCurrent = GetEMAValue(symbol, PERIOD_D1, 50, 1);
        double ema10DaysAgo = GetEMAValue(symbol, PERIOD_D1, 50, 10);
        
        if(emaCurrent == 0 || ema10DaysAgo == 0)
            return 0;
        
        // Slope = (EMA50[1] - EMA50[10]) / 9 (not 10 because we use bar index difference)
        return (emaCurrent - ema10DaysAgo) / 9.0;
    }
    
    // Calculate Bollinger Band position (0-1)
    double CalculateBBPosition(string symbol)
    {
        double closeYesterday = iClose(symbol, PERIOD_D1, 1);
        
        // Get Bollinger Bands on D1
        int bbHandle = iBands(symbol, PERIOD_D1, 20, 0, 2.0, PRICE_CLOSE);
        if(bbHandle == INVALID_HANDLE)
            return -1;
        
        double bbUpper[1], bbLower[1];
        if(CopyBuffer(bbHandle, 1, 1, 1, bbUpper) < 1 ||
           CopyBuffer(bbHandle, 2, 1, 1, bbLower) < 1)
        {
            IndicatorRelease(bbHandle);
            return -1;
        }
        
        IndicatorRelease(bbHandle);
        
        if(bbUpper[0] == bbLower[0]) // Avoid division by zero
            return 0.5;
        
        // BB Position = (Close - Lower BB) / (Upper BB - Lower BB)
        return (closeYesterday - bbLower[0]) / (bbUpper[0] - bbLower[0]);
    }
    
    // Calculate ATR ratio vs 50-day average
    double CalculateATRRatio(string symbol)
    {
        int atrHandle = iATR(symbol, PERIOD_D1, 14);
        if(atrHandle == INVALID_HANDLE)
            return 0;
        
        // Copy 51 values (current + last 50 days)
        double atrValues[51];
        if(CopyBuffer(atrHandle, 0, 1, 51, atrValues) < 51)
        {
            IndicatorRelease(atrHandle);
            return 0;
        }
        
        IndicatorRelease(atrHandle);
        
        double atrCurrent = atrValues[0];
        
        // Calculate 50-day SMA of ATR
        double atrSum = 0;
        for(int i = 1; i <= 50; i++)
            atrSum += atrValues[i];
        
        double atrAverage = atrSum / 50.0;
        
        if(atrAverage == 0)
            return 0;
        
        return atrCurrent / atrAverage;
    }
    
    // Get EMA value at specific bar index
    double GetEMAValue(string symbol, ENUM_TIMEFRAMES timeframe, int period, int shift)
    {
        int emaHandle = iMA(symbol, timeframe, period, 0, MODE_EMA, PRICE_CLOSE);
        if(emaHandle == INVALID_HANDLE)
            return 0;
        
        double emaValue[1];
        if(CopyBuffer(emaHandle, 0, shift, 1, emaValue) < 1)
        {
            IndicatorRelease(emaHandle);
            return 0;
        }
        
        IndicatorRelease(emaHandle);
        return emaValue[0];
    }
    
    // Get ADX value at specific bar index
    double GetADXValue(string symbol, ENUM_TIMEFRAMES timeframe, int period, int shift)
    {
        int adxHandle = iADX(symbol, timeframe, period);
        if(adxHandle == INVALID_HANDLE)
            return 0;
        
        double adxValue[1];
        if(CopyBuffer(adxHandle, 0, shift, 1, adxValue) < 1)
        {
            IndicatorRelease(adxHandle);
            return 0;
        }
        
        IndicatorRelease(adxHandle);
        return adxValue[0];
    }
    
    // Get qualification diagnostics for logging
    void GetQualificationDiagnostics(string symbol, string direction, 
                                     double &bbPos, double &emaSlope, double &atrRatio, double &adxValue)
    {
        bbPos = CalculateBBPosition(symbol);
        emaSlope = CalculateEMA50Slope(symbol);
        atrRatio = CalculateATRRatio(symbol);
        adxValue = GetADXValue(symbol, PERIOD_D1, 14, 1);
    }
    
    // Run H4 Scan (Layer 2) - UNCHANGED
    void RunH4Scan()
    {
        if(m_qualifiedCount == 0)
            return;
        
        // Check each qualified pair
        for(int i = 0; i < m_qualifiedCount; i++)
        {
            string symbol = m_qualifiedPairs[i].symbol;
            string direction = m_qualifiedPairs[i].direction;
            
            // Check entry conditions on H4
            BaseSignal signal = CheckSignal(symbol, PERIOD_H4);
            
            if(signal.signal != "")
            {
                // Log the signal
                LogSignalToCSV("ScannerSignals.csv", signal, true);
                
                // Execute if trading is enabled
                if(signal.action == "TRADED")
                {
                    ExecuteSignal(signal);
                }
            }
        }
    }
    
    // Check entry conditions for qualified pair - UNCHANGED
    PTSEntryConditions CheckEntryConditions(string symbol, string direction)
    {
        PTSEntryConditions conditions;
        
        // Initialize all fields
        conditions.bbTouch = false;
        conditions.reversalSignal = false;
        conditions.atrValue = 0.0;
        conditions.bbUpper = 0.0;
        conditions.bbLower = 0.0;
        conditions.bbMiddle = 0.0;
        
        // Get current H4 candle data
        MqlRates rates[1];
        if(CopyRates(symbol, PERIOD_H4, 0, 1, rates) < 1)
            return conditions;
        
        // Get Bollinger Bands
        int bbHandle = iBands(symbol, PERIOD_H4, m_bbPeriod, 0, m_bbDeviation, PRICE_CLOSE);
        if(bbHandle == INVALID_HANDLE)
            return conditions;
        
        double bbUpper[1], bbMiddle[1], bbLower[1];
        if(CopyBuffer(bbHandle, 1, 0, 1, bbUpper) < 1 ||
           CopyBuffer(bbHandle, 0, 0, 1, bbMiddle) < 1 ||
           CopyBuffer(bbHandle, 2, 0, 1, bbLower) < 1)
        {
            IndicatorRelease(bbHandle);
            return conditions;
        }
        
        conditions.bbUpper = bbUpper[0];
        conditions.bbMiddle = bbMiddle[0];
        conditions.bbLower = bbLower[0];
        IndicatorRelease(bbHandle);
        
        // Get ATR
        int atrHandle = iATR(symbol, PERIOD_H4, m_atrPeriod);
        if(atrHandle != INVALID_HANDLE)
        {
            double atrValue[1];
            if(CopyBuffer(atrHandle, 0, 0, 1, atrValue) >= 1)
                conditions.atrValue = atrValue[0];
            IndicatorRelease(atrHandle);
        }
        
        // Check Bollinger Band touch
        if(direction == "LONG")
        {
            // Check if price touched or broke below lower band
            conditions.bbTouch = (rates[0].low <= conditions.bbLower || 
                                  rates[0].close <= conditions.bbLower);
            
            // Check for bullish reversal candle
            conditions.reversalSignal = CheckBullishReversal(symbol, rates[0]);
        }
        else if(direction == "SHORT")
        {
            // Check if price touched or broke above upper band
            conditions.bbTouch = (rates[0].high >= conditions.bbUpper || 
                                  rates[0].close >= conditions.bbUpper);
            
            // Check for bearish reversal candle
            conditions.reversalSignal = CheckBearishReversal(symbol, rates[0]);
        }
        
        return conditions;
    }
    
    // Check for bullish reversal candle patterns - UNCHANGED
    bool CheckBullishReversal(string symbol, MqlRates &candle)
    {
        // Need previous candle for some patterns
        MqlRates prevCandle[1];
        if(CopyRates(symbol, PERIOD_H4, 1, 1, prevCandle) < 1)
            return false;
        
        // 1. Bullish Engulfing
        if(prevCandle[0].close < prevCandle[0].open && // Previous bearish
           candle.close > candle.open &&               // Current bullish
           candle.close > prevCandle[0].open &&        // Engulfs previous
           candle.open < prevCandle[0].close)
            return true;
        
        // 2. Hammer
        double bodySize = MathAbs(candle.close - candle.open);
        double lowerWick = (candle.open < candle.close) ? 
                          (candle.open - candle.low) : 
                          (candle.close - candle.low);
        double upperWick = (candle.open < candle.close) ? 
                          (candle.high - candle.close) : 
                          (candle.high - candle.open);
        
        if(lowerWick > (2.0 * bodySize) && upperWick < (0.1 * lowerWick))
            return true;
        
        // 3. Strong Bullish Close
        double range = candle.high - candle.low;
        if(range > 0)
        {
            double closePosition = (candle.close - candle.low) / range;
            if(closePosition >= 0.70) // Close in top 30% of range
                return true;
        }
        
        return false;
    }
    
    // Check for bearish reversal candle patterns - UNCHANGED
    bool CheckBearishReversal(string symbol, MqlRates &candle)
    {
        // Need previous candle for some patterns
        MqlRates prevCandle[1];
        if(CopyRates(symbol, PERIOD_H4, 1, 1, prevCandle) < 1)
            return false;
        
        // 1. Bearish Engulfing
        if(prevCandle[0].close > prevCandle[0].open && // Previous bullish
           candle.close < candle.open &&               // Current bearish
           candle.close < prevCandle[0].open &&        // Engulfs previous
           candle.open > prevCandle[0].close)
            return true;
        
        // 2. Shooting Star
        double bodySize = MathAbs(candle.close - candle.open);
        double upperWick = (candle.open < candle.close) ? 
                          (candle.high - candle.close) : 
                          (candle.high - candle.open);
        double lowerWick = (candle.open < candle.close) ? 
                          (candle.open - candle.low) : 
                          (candle.close - candle.low);
        
        if(upperWick > (2.0 * bodySize) && lowerWick < (0.1 * upperWick))
            return true;
        
        // 3. Strong Bearish Close
        double range = candle.high - candle.low;
        if(range > 0)
        {
            double closePosition = (candle.close - candle.low) / range;
            if(closePosition <= 0.30) // Close in bottom 30% of range
                return true;
        }
        
        return false;
    }
    
    // Get qualified direction for symbol
    string GetQualifiedDirection(string symbol)
    {
        for(int i = 0; i < m_qualifiedCount; i++)
        {
            if(m_qualifiedPairs[i].symbol == symbol)
                return m_qualifiedPairs[i].direction;
        }
        return "";
    }
    
    // Save qualified pairs to CSV - UPDATED for v4.1 diagnostics
    void SaveQualifiedPairsToCSV()
    {
        int filehandle = FileOpen(m_csvFilePath, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
        
        if(filehandle == INVALID_HANDLE)
        {
            Print("ERROR: Cannot create CSV file: ", m_csvFilePath);
            return;
        }
        
        // Write header with diagnostic data
        FileWrite(filehandle, "date", "symbol", "direction", "qualification_time",
                  "bb_position", "ema_slope", "atr_ratio", "adx_value");
        
        // Write qualified pairs
        for(int i = 0; i < m_qualifiedCount; i++)
        {
            FileWrite(filehandle,
                TimeToString(TimeCurrent(), TIME_DATE),
                m_qualifiedPairs[i].symbol,
                m_qualifiedPairs[i].direction,
                TimeToString(m_qualifiedPairs[i].qualificationTime, TIME_DATE|TIME_SECONDS),
                DoubleToString(m_qualifiedPairs[i].bbPosition, 4),
                DoubleToString(m_qualifiedPairs[i].emaSlope, 6),
                DoubleToString(m_qualifiedPairs[i].atrRatio, 3),
                DoubleToString(m_qualifiedPairs[i].adxValue, 1)
            );
        }
        
        FileClose(filehandle);
        Print("Qualified pairs saved to CSV: ", m_qualifiedCount, " pairs with v4.1R diagnostics");
    }
    
    // Load qualified pairs from CSV
    void LoadQualifiedPairs()
    {
        if(!FileIsExist(m_csvFilePath))
        {
            Print("No qualified pairs CSV file found: ", m_csvFilePath);
            return;
        }
        
        int filehandle = FileOpen(m_csvFilePath, FILE_READ|FILE_CSV|FILE_ANSI, ',');
        
        if(filehandle == INVALID_HANDLE)
        {
            Print("ERROR: Cannot open CSV file: ", m_csvFilePath);
            return;
        }
        
        // Read header (skip it)
        FileReadString(filehandle);
        
        // Read data
        m_qualifiedCount = 0;
        while(!FileIsEnding(filehandle) && m_qualifiedCount < 100)
        {
            string dateStr = FileReadString(filehandle);
            string symbol = FileReadString(filehandle);
            string direction = FileReadString(filehandle);
            string timeStr = FileReadString(filehandle);
            string bbPosStr = FileReadString(filehandle);
            string emaSlopeStr = FileReadString(filehandle);
            string atrRatioStr = FileReadString(filehandle);
            string adxValueStr = FileReadString(filehandle);
            
            if(symbol != "" && (direction == "LONG" || direction == "SHORT"))
            {
                m_qualifiedPairs[m_qualifiedCount].symbol = symbol;
                m_qualifiedPairs[m_qualifiedCount].direction = direction;
                m_qualifiedPairs[m_qualifiedCount].qualificationTime = StringToTime(timeStr);
                m_qualifiedPairs[m_qualifiedCount].bbPosition = StringToDouble(bbPosStr);
                m_qualifiedPairs[m_qualifiedCount].emaSlope = StringToDouble(emaSlopeStr);
                m_qualifiedPairs[m_qualifiedCount].atrRatio = StringToDouble(atrRatioStr);
                m_qualifiedPairs[m_qualifiedCount].adxValue = StringToDouble(adxValueStr);
                m_qualifiedCount++;
            }
        }
        
        FileClose(filehandle);
        Print("Loaded ", m_qualifiedCount, " qualified pairs from CSV with v4.1R diagnostics");
    }
    
    // Set PTS-specific parameters - UPDATED for v4.1R
    void SetPTSParameters(double slMultiplier, double tpMultiplier, 
                         double emaSlopeThreshold = 0.00008,
                         double longBBMin = 0.25, double longBBMax = 0.85,
                         double shortBBMin = 0.15, double shortBBMax = 0.75,
                         double atrRatioThreshold = 0.5, int adxMinValue = 15)
    {
        m_atrMultiplierSL = slMultiplier;
        m_atrMultiplierTP = tpMultiplier;
        m_emaSlopeThreshold = emaSlopeThreshold;
        m_longBBMin = longBBMin;
        m_longBBMax = longBBMax;
        m_shortBBMin = shortBBMin;
        m_shortBBMax = shortBBMax;
        m_atrRatioThreshold = atrRatioThreshold;
        m_adxMinValue = adxMinValue;
    }
    
    // Get PTS-specific parameters
    void GetPTSParameters(double &slMultiplier, double &tpMultiplier, 
                         double &emaSlopeThreshold,
                         double &longBBMin, double &longBBMax,
                         double &shortBBMin, double &shortBBMax,
                         double &atrRatioThreshold, int &adxMinValue)
    {
        slMultiplier = m_atrMultiplierSL;
        tpMultiplier = m_atrMultiplierTP;
        emaSlopeThreshold = m_emaSlopeThreshold;
        longBBMin = m_longBBMin;
        longBBMax = m_longBBMax;
        shortBBMin = m_shortBBMin;
        shortBBMax = m_shortBBMax;
        atrRatioThreshold = m_atrRatioThreshold;
        adxMinValue = m_adxMinValue;
    }
    
    // Get qualified pair count
    int GetQualifiedCount() { return m_qualifiedCount; }
    
    // Get qualified pair by index with diagnostics
    bool GetQualifiedPair(int index, string &symbol, string &direction, datetime &qualTime,
                         double &bbPos, double &emaSlope, double &atrRatio, double &adxValue)
    {
        if(index >= 0 && index < m_qualifiedCount)
        {
            symbol = m_qualifiedPairs[index].symbol;
            direction = m_qualifiedPairs[index].direction;
            qualTime = m_qualifiedPairs[index].qualificationTime;
            bbPos = m_qualifiedPairs[index].bbPosition;
            emaSlope = m_qualifiedPairs[index].emaSlope;
            atrRatio = m_qualifiedPairs[index].atrRatio;
            adxValue = m_qualifiedPairs[index].adxValue;
            return true;
        }
        return false;
    }
    
    // Validate PTS-specific settings - UPDATED for v4.1
    virtual bool ValidateSettings() override
    {
        if(!CStrategyBase::ValidateSettings())
            return false;
        
        if(m_atrMultiplierSL <= 0 || m_atrMultiplierTP <= 0)
            return false;
        
        // Use tolerance for floating point comparison
        if(MathAbs((m_atrMultiplierTP / m_atrMultiplierSL) - 2.0) > 0.01)
        {
            Print("WARNING: PTS risk-reward ratio should be 1:2. Current: 1:", 
                  DoubleToString(m_atrMultiplierTP / m_atrMultiplierSL, 1));
        }
        
        if(m_bbPeriod <= 0 || m_bbDeviation <= 0)
            return false;
        
        // v4.1 parameter validation
        if(m_longBBMin < 0 || m_longBBMin > 1 || m_longBBMax < 0 || m_longBBMax > 1)
            return false;
        if(m_shortBBMin < 0 || m_shortBBMin > 1 || m_shortBBMax < 0 || m_shortBBMax > 1)
            return false;
        if(m_atrRatioThreshold <= 0)
            return false;
        if(m_adxMinValue < 0 || m_adxMinValue > 100)
            return false;
        
        return true;
    }
    
    // Print PTS-specific settings - UPDATED for v4.1R
    virtual void PrintSettings() override
    {
        CStrategyBase::PrintSettings();
        Print("=== PTS v4.1R Settings (RELAXED) ===");
        Print("CSV File: ", m_csvFileName);
        Print("ATR SL Multiplier: ", m_atrMultiplierSL);
        Print("ATR TP Multiplier: ", m_atrMultiplierTP);
        Print("Risk-Reward Ratio: 1:", DoubleToString(m_atrMultiplierTP / m_atrMultiplierSL, 1));
        Print("Bollinger Band Period: ", m_bbPeriod);
        Print("Bollinger Band Deviation: ", m_bbDeviation);
        Print("ATR Period: ", m_atrPeriod);
        Print("Qualified Pairs: ", m_qualifiedCount);
        Print("=== v4.1R Layer 1 Parameters (RELAXED) ===");
        Print("EMA50 Slope Threshold: ", m_emaSlopeThreshold, " (was 0.00015)");
        Print("LONG BB Range: ", DoubleToString(m_longBBMin, 2), " - ", DoubleToString(m_longBBMax, 2), " (was 0.35-0.75)");
        Print("SHORT BB Range: ", DoubleToString(m_shortBBMin, 2), " - ", DoubleToString(m_shortBBMax, 2), " (was 0.25-0.65)");
        Print("ATR Ratio Threshold: ", DoubleToString(m_atrRatioThreshold, 2));
        Print("ADX Minimum: ", m_adxMinValue, " (was 18)");
        Print("Expected trade frequency: 2-5 trades/week (was 6 trades/2 years)");
    }
};

#endif