// TradeLogger.mqh - CSV logging and trade execution for Multi-Symbol Scanner
//+------------------------------------------------------------------+
//| Description: Handles CSV logging of trading signals and optional |
//|              trade execution with risk management                |
//+------------------------------------------------------------------+
#ifndef TRADELOGGER_MQH
#define TRADELOGGER_MQH

#include <Arrays\ArrayObj.mqh>

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
//| Daily loss tracker per strategy                                  |
//+------------------------------------------------------------------+
struct DailyLossTracker {
    string   strategy;
    double   dailyLoss;
    datetime lastResetDate;
    
    DailyLossTracker(string strat) {
        strategy = strat;
        dailyLoss = 0.0;
        lastResetDate = 0;
    }
};

CArrayObj DailyTrackers;  // Array of DailyLossTracker objects

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
bool ExecuteTrade(string symbol, string strategy, ENUM_ORDER_TYPE type, 
                 double lotSize, double slPoints, double tpPoints)
{
    // Check if symbol is valid
    if(!SymbolInfoInteger(symbol, SYMBOL_SELECT))
    {
        Print("ERROR: Symbol not selected: ", symbol);
        return false;
    }
    
    // Check daily loss limit
    if(!CheckDailyLossLimit(strategy, 100.0)) // Default limit
    {
        Print("WARNING: Daily loss limit reached for strategy: ", strategy);
        return false;
    }
    
    // Check if position already exists for this symbol/strategy
    if(HasOpenPosition(symbol, strategy))
    {
        Print("WARNING: Position already exists for ", symbol, " (", strategy, ")");
        return false;
    }
    
    // Prepare trade request
    MqlTradeRequest request;
    MqlTradeResult result;
    ZeroMemory(request);
    ZeroMemory(result);
    
    request.action = TRADE_ACTION_DEAL;
    request.symbol = symbol;
    request.volume = lotSize;
    request.type = type;
    request.magic = StringToInteger(StringSubstr(strategy, 0, 4)) + 1000; // Simple magic number
    
    // Set prices based on order type
    if(type == ORDER_TYPE_BUY)
    {
        request.price = SymbolInfoDouble(symbol, SYMBOL_ASK);
        request.sl = request.price - (slPoints * SymbolInfoDouble(symbol, SYMBOL_POINT));
        request.tp = request.price + (tpPoints * SymbolInfoDouble(symbol, SYMBOL_POINT));
    }
    else // SELL
    {
        request.price = SymbolInfoDouble(symbol, SYMBOL_BID);
        request.sl = request.price + (slPoints * SymbolInfoDouble(symbol, SYMBOL_POINT));
        request.tp = request.price - (tpPoints * SymbolInfoDouble(symbol, SYMBOL_POINT));
    }
    
    request.deviation = 10;
    request.comment = strategy;
    request.type_filling = ORDER_FILLING_FOK;
    request.type_time = ORDER_TIME_GTC;
    
    // Send order
    bool success = OrderSend(request, result);
    
    if(success)
    {
        Print("TRADE EXECUTED: ", symbol, " ", EnumToString(type), 
              " Lot: ", lotSize, " Price: ", request.price,
              " Ticket: ", result.order);
        
        // Update daily loss tracker
        UpdateDailyLossTracker(strategy, 0); // Will be updated when position closes
        
        return true;
    }
    else
    {
        Print("ERROR: Trade execution failed: ", symbol, 
              " Error: ", result.retcode, " ", GetTradeErrorDescription(result.retcode));
        return false;
    }
}

//+------------------------------------------------------------------+
//| Check daily loss limit for strategy                              |
//+------------------------------------------------------------------+
bool CheckDailyLossLimit(string strategy, double dailyLossLimit)
{
    // Reset daily loss at midnight
    ResetDailyLossIfNeeded(strategy);
    
    // Find or create tracker for this strategy
    DailyLossTracker* tracker = FindOrCreateTracker(strategy);
    
    if(tracker == NULL)
        return true; // Allow trading if tracker creation failed
    
    // Check if daily loss exceeds limit
    if(tracker.dailyLoss <= -dailyLossLimit)
    {
        Print("DAILY LOSS LIMIT REACHED: Strategy ", strategy, 
              " Loss: $", DoubleToString(MathAbs(tracker.dailyLoss), 2),
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
    DailyLossTracker* tracker = FindOrCreateTracker(strategy);
    
    if(tracker != NULL)
    {
        tracker.dailyLoss += pnl;
        
        // Log significant updates
        if(MathAbs(pnl) > 10.0) // Log trades with > $10 P/L
        {
            Print("Daily loss updated: Strategy ", strategy, 
                  " P/L: $", DoubleToString(pnl, 2),
                  " Total: $", DoubleToString(tracker.dailyLoss, 2));
        }
    }
}

//+------------------------------------------------------------------+
//| Find or create daily loss tracker                                |
//+------------------------------------------------------------------+
DailyLossTracker* FindOrCreateTracker(string strategy)
{
    // Check if tracker already exists
    for(int i = 0; i < DailyTrackers.Total(); i++)
    {
        DailyLossTracker* tracker = DailyTrackers.At(i);
        if(tracker.strategy == strategy)
            return tracker;
    }
    
    // Create new tracker
    DailyLossTracker* newTracker = new DailyLossTracker(strategy);
    DailyTrackers.Add(newTracker);
    
    return newTracker;
}

//+------------------------------------------------------------------+
//| Reset daily loss if new day                                      |
//+------------------------------------------------------------------+
void ResetDailyLossIfNeeded(string strategy)
{
    DailyLossTracker* tracker = FindOrCreateTracker(strategy);
    
    if(tracker != NULL)
    {
        MqlDateTime currentTime;
        TimeCurrent(currentTime);
        
        MqlDateTime lastResetTime;
        TimeToStruct(tracker.lastResetDate, lastResetTime);
        
        // Reset if it's a new day
        if(currentTime.day != lastResetTime.day || 
           currentTime.mon != lastResetTime.mon || 
           currentTime.year != lastResetTime.year)
        {
            tracker.dailyLoss = 0.0;
            tracker.lastResetDate = TimeCurrent();
            Print("Daily loss reset for strategy: ", strategy);
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
        if(PositionGetSymbol(i) == symbol)
        {
            // Check if position belongs to this strategy (by magic number or comment)
            string comment = PositionGetString(POSITION_COMMENT);
            if(comment == strategy)
                return true;
        }
    }
    
    return false;
}

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
        default:    return "Unknown error";
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
    
    // Simple fixed stop loss and take profit (50 points each)
    double slPoints = 50.0;
    double tpPoints = 100.0;
    
    return ExecuteTrade(signal.symbol, signal.strategy, orderType, lotSize, slPoints, tpPoints);
}

#endif // TRADELOGGER_MQH