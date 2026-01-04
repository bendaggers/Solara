// PTSStrategy.mqh - Pullback Trading System Strategy
//+------------------------------------------------------------------+
//| Description: Implementation of Pullback Trading System (PTS)     |
//|              based on the functional specification              |
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
    string direction;  // "LONG" or "SHORT"
    datetime qualificationTime;
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
    
    // Qualified pairs for today
    PTSQualifiedPair  m_qualifiedPairs[100];
    int               m_qualifiedCount;
    datetime          m_lastQualificationDate;
    
    // For CSV operations
    string            m_csvFilePath;
    
public:
    // Constructor
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
        Print("Initializing PTS Strategy: ", m_strategyName);
        
        if(!ValidateSettings())
        {
            Print("ERROR: PTS Strategy settings validation failed");
            return false;
        }
        
        // Load qualified pairs if CSV exists
        LoadQualifiedPairs();
        
        Print("PTS Strategy initialized successfully");
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
            signal.comment = "PTS: H4 Pullback " + direction;
            
            Print("PTS Signal: ", signal.signal, " ", symbol, 
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
            Print("PTS Strategy trade executed: ", signal.signal, " ", signal.symbol,
                  " @ ", DoubleToString(request.price, 5),
                  " SL: ", DoubleToString(request.sl, 5),
                  " TP: ", DoubleToString(request.tp, 5),
                  " Risk-Reward: 1:", DoubleToString(m_atrMultiplierTP / m_atrMultiplierSL, 1));
            return true;
        }
        else
        {
            Print("PTS Strategy trade failed: ", signal.signal, " ", signal.symbol,
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
               Print("=== PTS: 00:05 GMT - Running Daily Filter ===");
               RunDailyFilter();
               
               // Immediate H4 scan after daily filter
               Print("=== PTS: Immediate H4 Scan after Daily Filter ===");
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
               Print("=== PTS: H4 Scan Time ", currentTime.hour, ":00 GMT ===");
               RunH4Scan();
               lastH4ScanRun = TimeCurrent();
           }
       }
   }
    
    // Run Daily Filter (Layer 1)
    bool RunDailyFilter()
    {
        Print("=== PTS Daily Filter Running ===");
        
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
            
            // Check D1 trend and volatility
            string direction = CheckDailyQualification(symbol);
            
            if(direction != "")
            {
                // Add to qualified pairs
                if(m_qualifiedCount < 100)
                {
                    m_qualifiedPairs[m_qualifiedCount].symbol = symbol;
                    m_qualifiedPairs[m_qualifiedCount].direction = direction;
                    m_qualifiedPairs[m_qualifiedCount].qualificationTime = TimeCurrent();
                    m_qualifiedCount++;
                    qualifiedToday++;
                    
                    Print("Qualified: ", symbol, " as ", direction);
                }
            }
        }
        
        // Save to CSV file
        SaveQualifiedPairsToCSV();
        
        Print("Daily Filter completed. Qualified pairs: ", qualifiedToday, " / ", symbolCount);
        return true;
    }
    
    // Run H4 Scan (Layer 2)
    void RunH4Scan()
    {
        if(m_qualifiedCount == 0)
            return;
        
        // Print("=== PTS H4 Scan Running ===");
        
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
    
    // Check daily qualification for a symbol - FIXED VERSION
    string CheckDailyQualification(string symbol)
    {
        // Use yesterday's daily data (bar index 1)
        double closeYesterday = iClose(symbol, PERIOD_D1, 1);
        
        // Get EMA50 handle
        int emaHandle = iMA(symbol, PERIOD_D1, 50, 0, MODE_EMA, PRICE_CLOSE);
        if(emaHandle == INVALID_HANDLE)
            return "";
        
        // Copy EMA value for yesterday
        double emaValues[2];
        if(CopyBuffer(emaHandle, 0, 1, 2, emaValues) < 2)
        {
            IndicatorRelease(emaHandle);
            return "";
        }
        double ema50Yesterday = emaValues[0];
        IndicatorRelease(emaHandle);
        
        if(closeYesterday == 0 || ema50Yesterday == 0)
            return "";
        
        // Check volatility (ATR > 50% of 50-day average ATR)
        int atrHandle = iATR(symbol, PERIOD_D1, 14);
        if(atrHandle == INVALID_HANDLE)
            return "";
        
        // Copy ATR values
        double atrValues[51];
        if(CopyBuffer(atrHandle, 0, 0, 51, atrValues) < 51)
        {
            IndicatorRelease(atrHandle);
            return "";
        }
        
        double atrCurrent = atrValues[0];
        
        // Calculate 50-period SMA of ATR
        double atrSum = 0;
        for(int i = 1; i <= 50; i++)
            atrSum += atrValues[i];
        double atrSMA50 = atrSum / 50.0;
        
        IndicatorRelease(atrHandle);
        
        if(atrCurrent <= (atrSMA50 * 0.5))
            return ""; // Insufficient volatility
        
        // Determine direction
        if(closeYesterday > ema50Yesterday)
            return "LONG";
        else if(closeYesterday < ema50Yesterday)
            return "SHORT";
        
        return ""; // No clear trend
    }
    
    // Check entry conditions for qualified pair - FIXED VERSION
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
    
    // Check for bullish reversal candle patterns - FIXED VERSION
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
    
    // Check for bearish reversal candle patterns - FIXED VERSION
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
    
    // Save qualified pairs to CSV
    void SaveQualifiedPairsToCSV()
    {
        int filehandle = FileOpen(m_csvFilePath, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
        
        if(filehandle == INVALID_HANDLE)
        {
            Print("ERROR: Cannot create CSV file: ", m_csvFilePath);
            return;
        }
        
        // Write header
        FileWrite(filehandle, "date", "symbol", "direction", "qualification_time");
        
        // Write qualified pairs
        for(int i = 0; i < m_qualifiedCount; i++)
        {
            FileWrite(filehandle,
                TimeToString(TimeCurrent(), TIME_DATE),
                m_qualifiedPairs[i].symbol,
                m_qualifiedPairs[i].direction,
                TimeToString(m_qualifiedPairs[i].qualificationTime, TIME_DATE|TIME_SECONDS)
            );
        }
        
        FileClose(filehandle);
        Print("Qualified pairs saved to CSV: ", m_qualifiedCount, " pairs");
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
            
            if(symbol != "" && (direction == "LONG" || direction == "SHORT"))
            {
                m_qualifiedPairs[m_qualifiedCount].symbol = symbol;
                m_qualifiedPairs[m_qualifiedCount].direction = direction;
                m_qualifiedPairs[m_qualifiedCount].qualificationTime = StringToTime(timeStr);
                m_qualifiedCount++;
            }
        }
        
        FileClose(filehandle);
        Print("Loaded ", m_qualifiedCount, " qualified pairs from CSV");
    }
    
    // Set PTS-specific parameters
    void SetPTSParameters(double slMultiplier, double tpMultiplier, int bbPeriod = 20, double bbDeviation = 2.0)
    {
        m_atrMultiplierSL = slMultiplier;
        m_atrMultiplierTP = tpMultiplier;
        m_bbPeriod = bbPeriod;
        m_bbDeviation = bbDeviation;
    }
    
    // Get PTS-specific parameters
    void GetPTSParameters(double &slMultiplier, double &tpMultiplier, int &bbPeriod, double &bbDeviation)
    {
        slMultiplier = m_atrMultiplierSL;
        tpMultiplier = m_atrMultiplierTP;
        bbPeriod = m_bbPeriod;
        bbDeviation = m_bbDeviation;
    }
    
    // Get qualified pair count
    int GetQualifiedCount() { return m_qualifiedCount; }
    
    // Get qualified pair by index
    bool GetQualifiedPair(int index, string &symbol, string &direction, datetime &qualTime)
    {
        if(index >= 0 && index < m_qualifiedCount)
        {
            symbol = m_qualifiedPairs[index].symbol;
            direction = m_qualifiedPairs[index].direction;
            qualTime = m_qualifiedPairs[index].qualificationTime;
            return true;
        }
        return false;
    }
    
    // Validate PTS-specific settings
    virtual bool ValidateSettings() override
    {
        if(!CStrategyBase::ValidateSettings())
            return false;
        
        if(m_atrMultiplierSL <= 0 || m_atrMultiplierTP <= 0)
            return false;
        
        if(m_atrMultiplierTP / m_atrMultiplierSL != 2.0) // Must be 1:2 ratio
        {
            Print("WARNING: PTS risk-reward ratio should be 1:2. Current: 1:", 
                  DoubleToString(m_atrMultiplierTP / m_atrMultiplierSL, 1));
        }
        
        if(m_bbPeriod <= 0 || m_bbDeviation <= 0)
            return false;
        
        return true;
    }
    
    // Print PTS-specific settings
    virtual void PrintSettings() override
    {
        CStrategyBase::PrintSettings();
        Print("CSV File: ", m_csvFileName);
        Print("ATR SL Multiplier: ", m_atrMultiplierSL);
        Print("ATR TP Multiplier: ", m_atrMultiplierTP);
        Print("Risk-Reward Ratio: 1:", DoubleToString(m_atrMultiplierTP / m_atrMultiplierSL, 1));
        Print("Bollinger Band Period: ", m_bbPeriod);
        Print("Bollinger Band Deviation: ", m_bbDeviation);
        Print("ATR Period: ", m_atrPeriod);
        Print("Qualified Pairs: ", m_qualifiedCount);
    }
};

#endif // PTSSTRATEGY_MQH