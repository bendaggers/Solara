// TradeLogger.mqh - CSV logging and trade execution for Multi-Symbol Scanner
//+------------------------------------------------------------------+
//| Description: Handles CSV logging of trading signals and optional |
//|              trade execution with risk management                |
//+------------------------------------------------------------------+
#ifndef TRADELOGGER_MQH
#define TRADELOGGER_MQH

//+------------------------------------------------------------------+
//| Signal structure for logging                                     |
//+------------------------------------------------------------------+
struct TradingSignal {
    datetime timestamp;
    string   symbol;
    string   strategy;
    string   signal;      // "BUY" or "SELL"
    double   price;
    double   ema20;
    double   ema50;
    string   timeframe;
    string   action;      // "SCREENED" or "TRADED"
    
    TradingSignal() {
        timestamp = TimeCurrent();
        symbol = "";
        strategy = "";
        signal = "";
        price = 0.0;
        ema20 = 0.0;
        ema50 = 0.0;
        timeframe = "";
        action = "SCREENED";
    }
};

//+------------------------------------------------------------------+
//| Simple daily loss tracker                                        |
//+------------------------------------------------------------------+
struct DailyTracker {
    string   strategy;
    double   dailyLoss;
    datetime lastResetDate;
};

DailyTracker Trackers[10];  // Simple array for up to 10 strategies
int TrackerCount = 0;

//+------------------------------------------------------------------+
//| Get trade error description                                      |
//+------------------------------------------------------------------+
string GetTradeErrorDescription(int errorCode)
{
    switch(errorCode)
    {
        case 10004: return "Requote";
        case 10006: return "Request rejected";
        case 10007: return "Request canceled by trader";
        case 10008: return "Order placed";
        case 10009: return "Request completed";
        case 10010: return "Request partially filled";
        case 10011: return "Request processing error";
        case 10012: return "Request canceled";
        case 10013: return "Invalid request";
        case 10014: return "Invalid volume";
        case 10015: return "Invalid price";
        case 10016: return "Invalid stops";
        case 10017: return "Trade is disabled";
        case 10018: return "Market is closed";
        case 10019: return "Insufficient funds";
        case 10020: return "Price changed";
        case 10021: return "Too many requests";
        case 10022: return "No changes";
        case 10023: return "Autotrading disabled";
        case 10024: return "Order locked";
        case 10025: return "Long positions only allowed";
        case 10026: return "Too many orders";
        case 10027: return "Hedging prohibited";
        case 10028: return "Prohibited by FIFO";
        case 10029: return "Invalid filling";
        case 10030: return "Invalid order type";
        case 10031: return "Invalid position";
        case 10032: return "Invalid trade volume";
        case 10033: return "Invalid trade price";
        case 10034: return "Invalid trade stops";
        case 10035: return "Invalid trade expiration";
        case 10036: return "Invalid trade request";
        case 10038: return "Trade timeout";
        case 10039: return "Invalid trade filling mode";
        case 10040: return "Invalid trade type";
        case 10041: return "No connection with trade server";
        case 10042: return "Trade context is busy";
        case 10043: return "Invalid trade parameters";
        case 10044: return "Invalid trade function";
        case 10045: return "Trade function denied";
        case 10046: return "Trade disabled";
        case 10047: return "Old version of trade server";
        case 10048: return "Invalid account";
        case 10049: return "Invalid trade position";
        case 10050: return "Invalid trade volume limit";
        default:    return "Unknown error (" + IntegerToString(errorCode) + ")";
    }
}

//+------------------------------------------------------------------+
//| Find tracker index for strategy                                  |
//+------------------------------------------------------------------+
int FindTrackerIndex(string strategy)
{
    for(int i = 0; i < TrackerCount; i++)
    {
        if(Trackers[i].strategy == strategy)
            return i;
    }
    
    // Create new tracker if we have space
    if(TrackerCount < 10)
    {
        Trackers[TrackerCount].strategy = strategy;
        Trackers[TrackerCount].dailyLoss = 0.0;
        Trackers[TrackerCount].lastResetDate = 0;
        TrackerCount++;
        return TrackerCount - 1;
    }
    
    return -1;
}

//+------------------------------------------------------------------+
//| Reset daily loss if new day                                      |
//+------------------------------------------------------------------+
void ResetDailyLossIfNeeded(string strategy)
{
    int trackerIndex = FindTrackerIndex(strategy);
    
    if(trackerIndex != -1)
    {
        MqlDateTime currentTime;
        TimeCurrent(currentTime);
        
        MqlDateTime lastResetTime;
        TimeToStruct(Trackers[trackerIndex].lastResetDate, lastResetTime);
        
        // Reset if it's a new day
        if(currentTime.day != lastResetTime.day || 
           currentTime.mon != lastResetTime.mon || 
           currentTime.year != lastResetTime.year)
        {
            Trackers[trackerIndex].dailyLoss = 0.0;
            Trackers[trackerIndex].lastResetDate = TimeCurrent();
            Print("Daily loss reset for strategy: ", strategy);
        }
    }
}

//+------------------------------------------------------------------+
//| Check daily loss limit for strategy                              |
//+------------------------------------------------------------------+
bool CheckDailyLossLimit(string strategy, double dailyLossLimit)
{
    // Reset daily loss at midnight
    ResetDailyLossIfNeeded(strategy);
    
    // Find tracker index for this strategy
    int trackerIndex = FindTrackerIndex(strategy);
    
    if(trackerIndex == -1)
        return true; // No tracker yet, allow trading
    
    // Check if daily loss exceeds limit
    if(Trackers[trackerIndex].dailyLoss <= -dailyLossLimit)
    {
        Print("DAILY LOSS LIMIT REACHED: Strategy ", strategy, 
              " Loss: $", DoubleToString(MathAbs(Trackers[trackerIndex].dailyLoss), 2),
              " Limit: $", DoubleToString(dailyLossLimit, 2));
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Update daily loss tracker                                        |
//+------------------------------------------------------------------+
void UpdateDailyLossTracker(string strategy, double pnl)
{
    int trackerIndex = FindTrackerIndex(strategy);
    
    if(trackerIndex != -1)
    {
        Trackers[trackerIndex].dailyLoss += pnl;
        
        // Log significant updates
        if(MathAbs(pnl) > 10.0) // Log trades with > $10 P/L
        {
            Print("Daily loss updated: Strategy ", strategy, 
                  " P/L: $", DoubleToString(pnl, 2),
                  " Total: $", DoubleToString(Trackers[trackerIndex].dailyLoss, 2));
        }
    }
}

//+------------------------------------------------------------------+
//| Check if position already exists                                 |
//+------------------------------------------------------------------+
bool HasOpenPosition(string symbol, string strategy)
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(PositionGetString(POSITION_SYMBOL) == symbol)
        {
            // Check if position belongs to this strategy (by comment)
            string comment = PositionGetString(POSITION_COMMENT);
            if(comment == strategy)
                return true;
        }
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Log signal to CSV file                                           |
//+------------------------------------------------------------------+
void LogSignalToCSV(string csvFile, TradingSignal &signal, bool append = true)
{
    // Build full file path
    string filepath = "Files\\" + csvFile;
    
    // Check if file exists to write header
    bool fileExists = FileIsExist(filepath);
    int filehandle = INVALID_HANDLE;
    
    if(append && fileExists)
    {
        // Open existing file for appending
        filehandle = FileOpen(filepath, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
        if(filehandle != INVALID_HANDLE)
        {
            FileSeek(filehandle, 0, SEEK_END);
        }
    }
    else
    {
        // Create new file or overwrite
        filehandle = FileOpen(filepath, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
    }
    
    if(filehandle == INVALID_HANDLE)
    {
        Print("ERROR: Cannot open CSV file: ", filepath);
        return;
    }
    
    // Write header if new file
    if(!fileExists || !append)
    {
        FileWrite(filehandle, 
            "Timestamp",
            "Symbol", 
            "Strategy", 
            "Signal", 
            "Price", 
            "EMA20", 
            "EMA50", 
            "Timeframe",
            "Action"
        );
    }
    
    // Format timestamp
    string timestampStr = TimeToString(signal.timestamp, TIME_DATE|TIME_SECONDS);
    
    // Write signal data
    FileWrite(filehandle,
        timestampStr,
        signal.symbol,
        signal.strategy,
        signal.signal,
        DoubleToString(signal.price, 5),
        DoubleToString(signal.ema20, 5),
        DoubleToString(signal.ema50, 5),
        signal.timeframe,
        signal.action
    );
    
    FileClose(filehandle);
    
    Print("Signal logged: ", signal.symbol, " ", signal.strategy, " ", 
          signal.signal, " @ ", DoubleToString(signal.price, 5), 
          " (", signal.timeframe, ")");
}

//+------------------------------------------------------------------+
//| Format CSV row (alternative method)                              |
//+------------------------------------------------------------------+
string FormatCSVRow(TradingSignal &signal)
{
    string timestampStr = TimeToString(signal.timestamp, TIME_DATE|TIME_SECONDS);
    
    return StringFormat("%s,%s,%s,%s,%.5f,%.5f,%.5f,%s,%s",
        timestampStr,
        signal.symbol,
        signal.strategy,
        signal.signal,
        signal.price,
        signal.ema20,
        signal.ema50,
        signal.timeframe,
        signal.action
    );
}

//+------------------------------------------------------------------+
//| Execute trade if conditions met                                  |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| SIMPLE Execute trade - No checks, just place order!             |
//+------------------------------------------------------------------+
bool ExecuteTrade(string symbol, string strategy, ENUM_ORDER_TYPE type, 
                 double lotSize, double slPoints, double tpPoints)
{
    Print("SIMPLE ORDER: Placing ", EnumToString(type), " for ", symbol, 
          " Lot: ", lotSize, " Strategy: ", strategy);
    
    // Prepare trade request
    MqlTradeRequest request;
    MqlTradeResult result;
    ZeroMemory(request);
    ZeroMemory(result);
    
    request.action = TRADE_ACTION_DEAL;
    request.symbol = symbol;
    request.volume = lotSize;
    request.type = type;
    request.magic = 12345;
    
    // Get current prices
    double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
    double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
    double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
    int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
    
    // Set prices based on order type
    if(type == ORDER_TYPE_BUY)
    {
        request.price = ask;
        if(slPoints > 0) request.sl = NormalizeDouble(ask - (slPoints * point), digits);
        if(tpPoints > 0) request.tp = NormalizeDouble(ask + (tpPoints * point), digits);
    }
    else // SELL
    {
        request.price = bid;
        if(slPoints > 0) request.sl = NormalizeDouble(bid + (slPoints * point), digits);
        if(tpPoints > 0) request.tp = NormalizeDouble(bid - (tpPoints * point), digits);
    }
    
    request.deviation = 10;
    request.comment = strategy;
    request.type_filling = ORDER_FILLING_IOC;
    request.type_time = ORDER_TIME_GTC;
    
    // Send order
    bool success = OrderSend(request, result);
    
    if(success && result.retcode == TRADE_RETCODE_DONE)
    {
        Print("ORDER PLACED: ", symbol, " ", EnumToString(type), 
              " Lot: ", lotSize, " Price: ", request.price,
              " Ticket: ", result.order);
        return true;
    }
    else
    {
        Print("ORDER FAILED: ", symbol, " Error: ", GetTradeErrorDescription(result.retcode));
        return false;
    }
}

//+------------------------------------------------------------------+
//| Simple trade execution (without complex risk management)         |
//+------------------------------------------------------------------+
bool SimpleExecuteTrade(TradingSignal &signal, double lotSize)
{
    // For screening mode, just log
    if(signal.action == "SCREENED")
    {
        LogSignalToCSV("ScannerSignals.csv", signal, true);
        return true;
    }
    
    // For trading mode
    ENUM_ORDER_TYPE orderType = (signal.signal == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
    
    // Use reasonable stop loss and take profit
    double slPoints = 50.0;   // 50 points stop loss
    double tpPoints = 100.0;  // 100 points take profit
    
    return ExecuteTrade(signal.symbol, signal.strategy, orderType, lotSize, slPoints, tpPoints);
}

#endif // TRADELOGGER_MQH