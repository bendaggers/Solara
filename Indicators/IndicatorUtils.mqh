// Indicators/IndicatorUtils.mqh
//+------------------------------------------------------------------+
//| Description: Utility functions for Indicator System              |
//+------------------------------------------------------------------+
#ifndef INDICATORUTILS_MQH
#define INDICATORUTILS_MQH

#include "IndicatorTypes.mqh"
#include "IndicatorKey.mqh"

//+------------------------------------------------------------------+
//| Indicator Utilities Class                                        |
//+------------------------------------------------------------------+
class CIndicatorUtils
{
public:
    //+------------------------------------------------------------------+
    //| Check if new bar has formed                                      |
    //+------------------------------------------------------------------+
    static bool IsNewBar(string symbol, ENUM_TIMEFRAMES timeframe, datetime &lastBarTime)
    {
        // Get current bar open time
        datetime currentBarTime = iTime(symbol, timeframe, 0);
        
        if(currentBarTime == 0)
        {
            Print("ERROR: Cannot get bar time for ", symbol, " ", 
                  CIndicatorKey::TimeframeToString(timeframe));
            return false;
        }
        
        // Check if this is a new bar
        if(currentBarTime != lastBarTime)
        {
            lastBarTime = currentBarTime;
            return true;
        }
        
        return false;
    }
    
    //+------------------------------------------------------------------+
    //| Check if bar is complete (closed)                                |
    //+------------------------------------------------------------------+
    static bool IsBarComplete(string symbol, ENUM_TIMEFRAMES timeframe)
    {
        datetime currentOpen = iTime(symbol, timeframe, 0);
        datetime currentTime = TimeCurrent();
        
        // Calculate when current bar will close
        datetime nextBarTime = currentOpen + GetTimeframeSeconds(timeframe);
        
        // If current time is within last 10% of bar, consider it complete
        double percentComplete = (double)(currentTime - currentOpen) / 
                                 (double)GetTimeframeSeconds(timeframe);
        
        return (percentComplete >= 0.9); // 90% complete
    }
    
    //+------------------------------------------------------------------+
    //| Get timeframe in seconds                                         |
    //+------------------------------------------------------------------+
    static int GetTimeframeSeconds(ENUM_TIMEFRAMES timeframe)
    {
        switch(timeframe)
        {
            case PERIOD_M1:   return 60;
            case PERIOD_M5:   return 300;
            case PERIOD_M15:  return 900;
            case PERIOD_M30:  return 1800;
            case PERIOD_H1:   return 3600;
            case PERIOD_H4:   return 14400;
            case PERIOD_D1:   return 86400;
            case PERIOD_W1:   return 604800;
            case PERIOD_MN1:  return 2592000; // Approximately
            default:          return 3600;
        }
    }
    
    //+------------------------------------------------------------------+
    //| Calculate pip value for a symbol                                 |
    //+------------------------------------------------------------------+
    static double CalculatePipValue(string symbol, double volume = 1.0)
    {
        double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
        double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        
        if(point == 0 || tickSize == 0) 
            return 0.0;
            
        // For most forex pairs: 1 pip = 10 points (0.0001)
        // For JPY pairs: 1 pip = 100 points (0.01)
        double pipSize = 0.0001;
        
        // Check if it's a JPY pair
        if(StringFind(symbol, "JPY") != -1)
            pipSize = 0.01;
            
        // Calculate pip value
        double pipValue = (pipSize / point) * tickValue * volume;
        
        return NormalizeDouble(pipValue, 2);
    }
    
    //+------------------------------------------------------------------+
    //| Calculate position size based on risk percentage                 |
    //+------------------------------------------------------------------+
    static double CalculatePositionSize(string symbol, double accountBalance, 
                                       double riskPercent, double stopLossPips)
    {
        double pipValue = CalculatePipValue(symbol, 1.0);
        if(pipValue == 0.0) return 0.01;
        
        double riskAmount = accountBalance * (riskPercent / 100.0);
        double positionSize = riskAmount / (stopLossPips * pipValue);
        
        // Apply minimum and maximum lot size constraints
        double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
        double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
        double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
        
        positionSize = MathMax(positionSize, minLot);
        positionSize = MathMin(positionSize, maxLot);
        
        // Round to nearest lot step
        if(lotStep > 0)
            positionSize = MathRound(positionSize / lotStep) * lotStep;
        
        return NormalizeDouble(positionSize, 2);
    }
    
    //+------------------------------------------------------------------+
    //| Validate symbol for trading                                      |
    //+------------------------------------------------------------------+
    static bool IsValidSymbol(string symbol)
    {
        // Check if symbol exists in Market Watch
        long selectResult = 0;
        if(!SymbolInfoInteger(symbol, SYMBOL_SELECT, selectResult) || selectResult == 0)
        {
            // Try to select it
            if(!SymbolSelect(symbol, true))
            {
                Print("WARNING: Symbol not available: ", symbol);
                return false;
            }
        }
        
        // Check if trading is allowed for this symbol
        long tradeMode = 0;
        if(!SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE, tradeMode))
        {
            Print("WARNING: Cannot get trade mode for: ", symbol);
            return false;
        }
        
        if(tradeMode == SYMBOL_TRADE_MODE_DISABLED || 
           tradeMode == SYMBOL_TRADE_MODE_CLOSEONLY)
        {
            Print("WARNING: Symbol trading disabled: ", symbol);
            return false;
        }
        
        // Check if market is open (simplified check)
        // Just check if we can get the spread - if not, symbol might not be tradeable
        long spread = 0;
        if(!SymbolInfoInteger(symbol, SYMBOL_SPREAD, spread))
        {
            Print("WARNING: Cannot get spread for: ", symbol);
            return false;
        }
        
        // Check if spread is reasonable (less than 100 points)
        if(spread > 1000) // 100 points = 1000 for 5-digit brokers
        {
            Print("WARNING: Symbol has very high spread: ", symbol, " (", spread, " points)");
            return false;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Get current spread in pips                                       |
    //+------------------------------------------------------------------+
    static double GetSpreadInPips(string symbol)
    {
        long spread = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        
        if(point == 0) return 0.0;
        
        // Convert spread to pips
        double spreadPips = spread * point;
        
        // For most pairs: 1 pip = 0.0001
        // For JPY pairs: 1 pip = 0.01
        double pipSize = 0.0001;
        if(StringFind(symbol, "JPY") != -1)
            pipSize = 0.01;
            
        return NormalizeDouble(spreadPips / pipSize, 1);
    }
    
    //+------------------------------------------------------------------+
    //| Get ATR value in pips                                            |
    //+------------------------------------------------------------------+
    static double GetATRInPips(string symbol, ENUM_TIMEFRAMES timeframe, int period, int shift = 0)
    {
        double atrValue = iATR(symbol, timeframe, period, shift);
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        
        if(point == 0 || atrValue == 0) return 0.0;
        
        // Convert ATR to pips
        double pipSize = 0.0001;
        if(StringFind(symbol, "JPY") != -1)
            pipSize = 0.01;
            
        return NormalizeDouble(atrValue / pipSize, 1);
    }
    
    //+------------------------------------------------------------------+
    //| Calculate stop loss distance in pips                             |
    //+------------------------------------------------------------------+
    static double CalculateStopLossPips(string symbol, double entryPrice, double stopLossPrice)
    {
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        double priceDiff = MathAbs(entryPrice - stopLossPrice);
        
        if(point == 0) return 0.0;
        
        // Convert to pips
        double pipSize = 0.0001;
        if(StringFind(symbol, "JPY") != -1)
            pipSize = 0.01;
            
        return NormalizeDouble(priceDiff / pipSize, 1);
    }
    
    //+------------------------------------------------------------------+
    //| Calculate take profit distance in pips                           |
    //+------------------------------------------------------------------+
    static double CalculateTakeProfitPips(string symbol, double entryPrice, double takeProfitPrice)
    {
        return CalculateStopLossPips(symbol, entryPrice, takeProfitPrice);
    }
    
    //+------------------------------------------------------------------+
    //| Check if time is within trading session                          |
    //+------------------------------------------------------------------+
    static bool IsTradingSession(string symbol, int sessionStartHour = 0, int sessionEndHour = 24)
    {
        MqlDateTime dt;
        TimeCurrent(dt);
        
        int currentHour = dt.hour;
        
        // Handle sessions that cross midnight
        if(sessionStartHour <= sessionEndHour)
            return (currentHour >= sessionStartHour && currentHour < sessionEndHour);
        else
            return (currentHour >= sessionStartHour || currentHour < sessionEndHour);
    }
    
    //+------------------------------------------------------------------+
    //| Check if it's weekend (Saturday or Sunday)                       |
    //+------------------------------------------------------------------+
    static bool IsWeekend()
    {
        MqlDateTime dt;
        TimeCurrent(dt);
        
        return (dt.day_of_week == 0 || dt.day_of_week == 6); // 0=Sunday, 6=Saturday
    }
    
    //+------------------------------------------------------------------+
    //| Check if high-impact news is scheduled                           |
    //+------------------------------------------------------------------+
    static bool IsHighImpactNewsScheduled(string symbol, int hoursAhead = 2)
    {
        // This is a placeholder - in real implementation, you would
        // connect to an economic calendar API or database
        
        // For now, just return false
        // TODO: Implement news checking logic
        
        return false;
    }
    
    //+------------------------------------------------------------------+
    //| Get market volatility state                                      |
    //+------------------------------------------------------------------+
    static string GetMarketVolatilityState(string symbol, ENUM_TIMEFRAMES timeframe)
    {
        double currentATR = GetATRInPips(symbol, timeframe, 14, 0);
        double avgATR = GetATRInPips(symbol, timeframe, 14, 50); // 50-period average
        
        if(avgATR == 0) return "UNKNOWN";
        
        double ratio = currentATR / avgATR;
        
        if(ratio < 0.5) return "VERY_LOW";
        if(ratio < 0.75) return "LOW";
        if(ratio < 1.25) return "NORMAL";
        if(ratio < 1.5) return "HIGH";
        return "VERY_HIGH";
    }
    
    //+------------------------------------------------------------------+
    //| Get trend strength using ADX                                     |
    //+------------------------------------------------------------------+
    static string GetTrendStrength(string symbol, ENUM_TIMEFRAMES timeframe)
    {
        // Placeholder - would use iADX in real implementation
        // TODO: Implement ADX-based trend strength
        
        return "NEUTRAL";
    }
    
    //+------------------------------------------------------------------+
    //| Format price with correct digits                                 |
    //+------------------------------------------------------------------+
    static string FormatPrice(string symbol, double price)
    {
        int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
        return DoubleToString(price, digits);
    }
    
    //+------------------------------------------------------------------+
    //| Format percentage                                                |
    //+------------------------------------------------------------------+
    static string FormatPercent(double value)
    {
        return DoubleToString(value * 100.0, 2) + "%";
    }
    
    //+------------------------------------------------------------------+
    //| Calculate profit/loss in currency                                |
    //+------------------------------------------------------------------+
    static double CalculateProfitLoss(double entryPrice, double exitPrice, 
                                     string symbol, double volume)
    {
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
        double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
        
        if(point == 0 || tickSize == 0) return 0.0;
        
        double priceDiff = exitPrice - entryPrice;
        double profit = (priceDiff / point) * (tickValue / tickSize) * volume;
        
        return NormalizeDouble(profit, 2);
    }
    
    //+------------------------------------------------------------------+
    //| Get current account information                                  |
    //+------------------------------------------------------------------+
    static void GetAccountInfo(double &balance, double &equity, double &margin, 
                              double &freeMargin, double &marginLevel)
    {
        balance = AccountInfoDouble(ACCOUNT_BALANCE);
        equity = AccountInfoDouble(ACCOUNT_EQUITY);
        margin = AccountInfoDouble(ACCOUNT_MARGIN);
        freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
        
        if(margin > 0)
            marginLevel = (equity / margin) * 100.0;
        else
            marginLevel = 0.0;
    }
    
    //+------------------------------------------------------------------+
    //| Check if account has sufficient margin                           |
    //+------------------------------------------------------------------+
    static bool HasSufficientMargin(string symbol, double volume)
    {
        double marginRequired = 0.0;
        
        if(!OrderCalcMargin(ORDER_TYPE_BUY, symbol, volume, 
                           SymbolInfoDouble(symbol, SYMBOL_ASK), marginRequired))
        {
            Print("ERROR: Cannot calculate margin for ", symbol);
            return false;
        }
        
        double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
        
        return (freeMargin >= marginRequired * 1.1); // 10% buffer
    }
    
    //+------------------------------------------------------------------+
    //| Get optimal lot size based on risk management                    |
    //+------------------------------------------------------------------+
    static double GetOptimalLotSize(string symbol, double stopLossPips, 
                                   double riskPercent = 1.0)
    {
        double balance = AccountInfoDouble(ACCOUNT_BALANCE);
        return CalculatePositionSize(symbol, balance, riskPercent, stopLossPips);
    }
    
    //+------------------------------------------------------------------+
    //| Log indicator calculation for debugging                          |
    //+------------------------------------------------------------------+
    static void LogIndicatorCalculation(string key, double value, string source, 
                                       double calculationTimeMs = 0.0)
    {
        string logEntry = StringFormat("%s,%s,%.6f,%s,%.2f", 
                                      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
                                      key, value, source, calculationTimeMs);
        
        // Write to file
        string filename = "Data/Logs/indicator_calculations.csv";
        int handle = FileOpen(filename, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
        
        if(handle != INVALID_HANDLE)
        {
            FileSeek(handle, 0, SEEK_END);
            
            // Write header if file is empty
            if(FileSize(handle) == 0)
            {
                FileWrite(handle, "Timestamp", "Key", "Value", "Source", "TimeMs");
            }
            
            FileWrite(handle, 
                     TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
                     key, 
                     DoubleToString(value, 6), 
                     source, 
                     DoubleToString(calculationTimeMs, 2));
            
            FileClose(handle);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Generate random test data for indicators                         |
    //+------------------------------------------------------------------+
    static void GenerateTestData(int numEntries = 100)
    {
        Print("=== Generating Test Data ===");
        
        string symbols[] = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"};
        ENUM_TIMEFRAMES timeframes[] = {PERIOD_H1, PERIOD_H4, PERIOD_D1};
        ENUM_INDICATOR_TYPE types[] = {INDICATOR_EMA, INDICATOR_ATR, INDICATOR_BB};
        
        for(int i = 0; i < numEntries; i++)
        {
            string symbol = symbols[i % ArraySize(symbols)];
            ENUM_TIMEFRAMES tf = timeframes[i % ArraySize(timeframes)];
            ENUM_INDICATOR_TYPE type = types[i % ArraySize(types)];
            
            IndicatorParams params;
            params.period = 20 + (i % 30); // Random period 20-50
            
            string key = CIndicatorKey::CreateKey(symbol, tf, type, params);
            double value = 1.0 + (MathRand() % 1000) / 1000.0; // Random value 1.0-2.0
            
            LogIndicatorCalculation(key, value, "TEST_DATA");
        }
        
        Print("Generated ", numEntries, " test entries");
    }
    
    //+------------------------------------------------------------------+
    //| Test utility functions                                           |
    //+------------------------------------------------------------------+
    static void TestUtilities()
    {
        Print("=== Testing Indicator Utilities ===");
        
        // Test symbol validation
        bool isValid = IsValidSymbol("EURUSD");
        Print("EURUSD is valid: ", isValid ? "YES" : "NO");
        
        // Test pip value calculation
        double pipValue = CalculatePipValue("EURUSD");
        Print("EURUSD pip value (1 lot): $", pipValue);
        
        // Test position size calculation
        double positionSize = CalculatePositionSize("EURUSD", 10000.0, 1.0, 50.0);
        Print("Position size for 1% risk, 50 pip SL: ", positionSize, " lots");
        
        // Test spread
        double spread = GetSpreadInPips("EURUSD");
        Print("Current spread: ", spread, " pips");
        
        // Test ATR in pips
        double atrPips = GetATRInPips("EURUSD", PERIOD_H4, 14);
        Print("ATR(14) on H4: ", atrPips, " pips");
        
        // Test market volatility
        string volatility = GetMarketVolatilityState("EURUSD", PERIOD_H4);
        Print("Market volatility: ", volatility);
        
        // Test weekend check
        bool isWeekend = IsWeekend();
        Print("Is weekend: ", isWeekend ? "YES" : "NO");
        
        // Test account info
        double balance, equity, margin, freeMargin, marginLevel;
        GetAccountInfo(balance, equity, margin, freeMargin, marginLevel);
        Print("Account Balance: $", balance, " Equity: $", equity);
        
        Print("=== Utility Test Complete ===");
    }
};

#endif // INDICATORUTILS_MQH