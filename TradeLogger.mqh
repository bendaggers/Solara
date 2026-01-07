// TradeLogger.mqh - Enhanced for multi-strategy support
//+------------------------------------------------------------------+
//| Description: Handles CSV logging and trade execution with        |
//|              enhanced multi-strategy support                     |
//+------------------------------------------------------------------+
#ifndef TRADELOGGER_MQH
#define TRADELOGGER_MQH

// Include StrategyBase to get BaseSignal definition
#include "StrategyBase.mqh"

//+------------------------------------------------------------------+
//| Forward declarations                                             |
//+------------------------------------------------------------------+
struct TradingSignal;  // Forward declaration

//+------------------------------------------------------------------+
//| TradingSignal structure (must be defined BEFORE functions that use it)
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
//| Get trade error description (complete implementation)            |
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
//| Enhanced signal structure with more fields                       |
//+------------------------------------------------------------------+
struct EnhancedSignal
{
    datetime timestamp;
    string   symbol;
    string   strategyName;
    string   signal;        // "BUY", "SELL", "EXIT"
    double   price;
    double   value1;        // Strategy-specific value 1
    double   value2;        // Strategy-specific value 2
    string   timeframe;
    string   action;        // "SCREENED", "TRADED", "EXIT_SIGNAL"
    string   comment;       // Additional info
    double   slPrice;       // Stop loss price
    double   tpPrice;       // Take profit price
    double   lotSize;       // Trade lot size
    int      magicNumber;   // Strategy magic number
    
    EnhancedSignal()
    {
        timestamp = TimeCurrent();
        symbol = "";
        strategyName = "";
        signal = "";
        price = 0.0;
        value1 = 0.0;
        value2 = 0.0;
        timeframe = "";
        action = "SCREENED";
        comment = "";
        slPrice = 0.0;
        tpPrice = 0.0;
        lotSize = 0.0;
        magicNumber = 0;
    }
};

//+------------------------------------------------------------------+
//| Log enhanced signal to CSV file                                  |
//+------------------------------------------------------------------+
void LogEnhancedSignalToCSV(string csvFile, EnhancedSignal &signal, bool append = true)
{
    string filepath = "Files\\" + csvFile;
    bool fileExists = FileIsExist(filepath);
    int filehandle = INVALID_HANDLE;
    
    if(append && fileExists)
    {
        filehandle = FileOpen(filepath, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
        if(filehandle != INVALID_HANDLE)
            FileSeek(filehandle, 0, SEEK_END);
    }
    else
    {
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
            "Timestamp", "Symbol", "Strategy", "Signal", "Price",
            "Value1", "Value2", "Timeframe", "Action", "Comment",
            "SL_Price", "TP_Price", "LotSize", "MagicNumber"
        );
    }
    
    // Write signal data
    FileWrite(filehandle,
        TimeToString(signal.timestamp, TIME_DATE|TIME_SECONDS),
        signal.symbol,
        signal.strategyName,
        signal.signal,
        DoubleToString(signal.price, 5),
        DoubleToString(signal.value1, 5),
        DoubleToString(signal.value2, 5),
        signal.timeframe,
        signal.action,
        signal.comment,
        DoubleToString(signal.slPrice, 5),
        DoubleToString(signal.tpPrice, 5),
        DoubleToString(signal.lotSize, 2),
        IntegerToString(signal.magicNumber)
    );
    
    FileClose(filehandle);
    
    Print("Signal logged to CSV: ", signal.symbol, " ", signal.strategyName, " ", 
          signal.signal, " @ ", DoubleToString(signal.price, 5), 
          " (", signal.timeframe, ")");
}

//+------------------------------------------------------------------+
//| Log signal (backward compatibility)                              |
//+------------------------------------------------------------------+
void LogSignalToCSV(string csvFile, BaseSignal &signal, bool append = true)
{
    EnhancedSignal enhancedSignal;
    enhancedSignal.timestamp = signal.timestamp;
    enhancedSignal.symbol = signal.symbol;
    enhancedSignal.strategyName = signal.strategyName;
    enhancedSignal.signal = signal.signal;
    enhancedSignal.price = signal.price;
    enhancedSignal.value1 = signal.value1;
    enhancedSignal.value2 = signal.value2;
    enhancedSignal.timeframe = signal.timeframe;
    enhancedSignal.action = signal.action;
    enhancedSignal.comment = signal.comment;
    
    LogEnhancedSignalToCSV(csvFile, enhancedSignal, append);
}

//+------------------------------------------------------------------+
//| SIMPLE Execute trade - No checks, just place order!              |
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
        // Create BaseSignal from TradingSignal
        BaseSignal baseSignal;
        baseSignal.timestamp = signal.timestamp;
        baseSignal.symbol = signal.symbol;
        baseSignal.strategyName = signal.strategy;
        baseSignal.signal = signal.signal;
        baseSignal.price = signal.price;
        baseSignal.value1 = signal.ema20;
        baseSignal.value2 = signal.ema50;
        baseSignal.timeframe = signal.timeframe;
        baseSignal.action = signal.action;
        baseSignal.comment = "";
        
        LogSignalToCSV("ScannerSignals.csv", baseSignal, true);
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