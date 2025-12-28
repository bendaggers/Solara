// ScannerCore.mqh - Core scanning functions for Multi-Symbol Scanner
//+------------------------------------------------------------------+
//| Description: Provides essential functions for symbol management  |
//|              and timeframe checking                              |
//+------------------------------------------------------------------+
#ifndef SCANNERCORE_MQH
#define SCANNERCORE_MQH

//+------------------------------------------------------------------+
//| Check if symbol is valid and tradeable                           |
//+------------------------------------------------------------------+
bool IsValidSymbol(string symbol)
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
//| Check if new bar has formed                                      |
//+------------------------------------------------------------------+
bool IsNewBar(string symbol, ENUM_TIMEFRAMES timeframe, datetime &lastBarTime)
{
    // Get current bar open time
    datetime currentBarTime = iTime(symbol, timeframe, 0);
    
    if(currentBarTime == 0)
    {
        Print("ERROR: Cannot get bar time for ", symbol, " ", TimeframeToString(timeframe));
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
//| Get strategy timeframes                                          |
//+------------------------------------------------------------------+
void GetStrategyTimeframes(ENUM_TIMEFRAMES &timeframes[])
{
    // Hardcoded for now - can be made configurable later
    ArrayResize(timeframes, 3);
    timeframes[0] = PERIOD_H1;   // 1-hour
    timeframes[1] = PERIOD_H4;   // 4-hour
    timeframes[2] = PERIOD_D1;   // Daily
}

//+------------------------------------------------------------------+
//| Convert timeframe to string                                      |
//+------------------------------------------------------------------+
string TimeframeToString(ENUM_TIMEFRAMES tf)
{
    switch(tf)
    {
        case PERIOD_M1:   return "M1";
        case PERIOD_M5:   return "M5";
        case PERIOD_M15:  return "M15";
        case PERIOD_M30:  return "M30";
        case PERIOD_H1:   return "H1";
        case PERIOD_H4:   return "H4";
        case PERIOD_D1:   return "D1";
        case PERIOD_W1:   return "W1";
        case PERIOD_MN1:  return "MN1";
        default:          return "Unknown";
    }
}

//+------------------------------------------------------------------+
//| Trim leading whitespace from string                              |
//+------------------------------------------------------------------+
string TrimLeft(string text)
{
    int start = 0;
    int len = StringLen(text);
    
    while(start < len && StringGetCharacter(text, start) == ' ')
        start++;
    
    if(start >= len)
        return "";
    
    return StringSubstr(text, start);
}

//+------------------------------------------------------------------+
//| Trim trailing whitespace from string                             |
//+------------------------------------------------------------------+
string TrimRight(string text)
{
    int end = StringLen(text) - 1;
    
    while(end >= 0 && StringGetCharacter(text, end) == ' ')
        end--;
    
    if(end < 0)
        return "";
    
    return StringSubstr(text, 0, end + 1);
}

#endif // SCANNERCORE_MQH