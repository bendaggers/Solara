// EMAStrategy.mqh - Simplified EMA Crossover Strategy for Multi-Symbol Scanner
//+------------------------------------------------------------------+
//| Description: Simple EMA 20/50 crossover strategy                 |
//+------------------------------------------------------------------+
#ifndef EMASTRATEGY_MQH
#define EMASTRATEGY_MQH

#include "TradeLogger.mqh"
#include "ScannerCore.mqh"

//+------------------------------------------------------------------+
//| Strategy settings structure                                      |
//+------------------------------------------------------------------+
struct EMAStrategySettings {
    int      fastPeriod;      // EMA fast period (default: 20)
    int      slowPeriod;      // EMA slow period (default: 50)
    double   lotSize;         // Fixed lot size for this strategy
    double   dailyLossLimit;  // Max daily loss in USD
    bool     enableTrading;   // Enable auto-trading
    
    EMAStrategySettings() {
        fastPeriod = 20;
        slowPeriod = 50;
        lotSize = 0.01;
        dailyLossLimit = 100.0;
        enableTrading = false;
    }
};

//+------------------------------------------------------------------+
//| EMA values for current and previous bars                         |
//+------------------------------------------------------------------+
struct EMAValues {
    double currentFast;      // EMA fast on current bar (bar 0)
    double currentSlow;      // EMA slow on current bar (bar 0)
    double prevFast;         // EMA fast on previous bar (bar 1)
    double prevSlow;         // EMA slow on previous bar (bar 1)
    double currentClose;     // Close price on current bar
    double currentOpen;      // Open price on current bar
    
    EMAValues() {
        currentFast = 0.0;
        currentSlow = 0.0;
        prevFast = 0.0;
        prevSlow = 0.0;
        currentClose = 0.0;
        currentOpen = 0.0;
    }
};

//+------------------------------------------------------------------+
//| Check EMA crossover strategy for given symbol/timeframe          |
//+------------------------------------------------------------------+
TradingSignal CheckEMAStrategy(string symbol, ENUM_TIMEFRAMES timeframe, 
                              EMAStrategySettings &settings, bool hasOpenPosition = false)
{
    TradingSignal signal;
    signal.symbol = symbol;
    signal.strategy = "EMA_Crossover";
    signal.timeframe = TimeframeToString(timeframe);
    
    // Get EMA values for current and previous bars
    EMAValues ema = CalculateEMAValues(symbol, timeframe, settings.fastPeriod, settings.slowPeriod);
    
    if(ema.currentFast == 0.0 || ema.currentSlow == 0.0)
    {
        // Error in calculation
        return signal;
    }
    
    // Debug information
    Print("=== Checking ", symbol, " ", TimeframeToString(timeframe), " ===");
    Print("Has open position: ", hasOpenPosition ? "YES" : "NO");
    Print("Enable trading: ", settings.enableTrading ? "YES" : "NO");
    
    // If we DON'T have an open position, check for BUY signal
    if(!hasOpenPosition)
    {
        if(CheckBuySignal(ema))
        {
            signal.signal = "BUY";
            signal.price = SymbolInfoDouble(symbol, SYMBOL_ASK);
            signal.ema20 = ema.currentFast;
            signal.ema50 = ema.currentSlow;
            signal.action = settings.enableTrading ? "TRADED" : "SCREENED";
            
            // Log the signal
            Print("BUY SIGNAL: ", symbol, " ", signal.timeframe,
                  " Price: ", DoubleToString(signal.price, 5),
                  " EMA20: ", DoubleToString(ema.currentFast, 5),
                  " EMA50: ", DoubleToString(ema.currentSlow, 5));
            
            // Execute trade if enabled
            if(settings.enableTrading)
            {
                SimpleExecuteTrade(signal, settings.lotSize);
            }
        }
        else
        {
            Print("No BUY signal for ", symbol, " ", TimeframeToString(timeframe));
        }
    }
    // If we DO have an open position, check for SELL signal
    else
    {
        if(CheckSellSignal(ema))
        {
            signal.signal = "SELL";
            signal.price = SymbolInfoDouble(symbol, SYMBOL_BID);
            signal.ema20 = ema.currentFast;
            signal.ema50 = ema.currentSlow;
            signal.action = "EXIT_SIGNAL";
            
            // Log exit signal
            Print("EXIT SIGNAL: ", symbol, " ", signal.timeframe,
                  " Price below EMA20: ", DoubleToString(signal.price, 5),
                  " EMA20: ", DoubleToString(ema.currentFast, 5));
            
            // Execute exit trade if enabled
            if(settings.enableTrading)
            {
                SimpleExecuteTrade(signal, settings.lotSize);
            }
        }
        else
        {
            Print("No exit signal for existing position on ", symbol);
        }
    }
    
    return signal;
}

//+------------------------------------------------------------------+
//| Calculate EMA values for current and previous bars               |
//+------------------------------------------------------------------+
EMAValues CalculateEMAValues(string symbol, ENUM_TIMEFRAMES timeframe, 
                            int fastPeriod, int slowPeriod)
{
    EMAValues ema;
    
    // Get handle for EMA indicators
    int handleFast = iMA(symbol, timeframe, fastPeriod, 0, MODE_EMA, PRICE_CLOSE);
    int handleSlow = iMA(symbol, timeframe, slowPeriod, 0, MODE_EMA, PRICE_CLOSE);
    
    if(handleFast == INVALID_HANDLE || handleSlow == INVALID_HANDLE)
    {
        Print("ERROR: Cannot create EMA indicator for ", symbol);
        return ema;
    }
    
    // Copy EMA values for bars 0 and 1
    double fastValues[2];
    double slowValues[2];
    
    // Copy fast EMA values (current bar = 0, previous = 1)
    if(CopyBuffer(handleFast, 0, 0, 2, fastValues) < 2)
    {
        Print("ERROR: Cannot copy fast EMA values for ", symbol);
        IndicatorRelease(handleFast);
        IndicatorRelease(handleSlow);
        return ema;
    }
    
    // Copy slow EMA values
    if(CopyBuffer(handleSlow, 0, 0, 2, slowValues) < 2)
    {
        Print("ERROR: Cannot copy slow EMA values for ", symbol);
        IndicatorRelease(handleFast);
        IndicatorRelease(handleSlow);
        return ema;
    }
    
    // Get price data for current bar
    MqlRates rates[1];
    if(CopyRates(symbol, timeframe, 0, 1, rates) < 1)
    {
        Print("ERROR: Cannot copy price data for ", symbol);
        IndicatorRelease(handleFast);
        IndicatorRelease(handleSlow);
        return ema;
    }
    
    // Assign values
    ema.currentFast = fastValues[0];   // Bar 0 (current)
    ema.prevFast = fastValues[1];      // Bar 1 (previous)
    
    ema.currentSlow = slowValues[0];   // Bar 0 (current)
    ema.prevSlow = slowValues[1];      // Bar 1 (previous)
    
    ema.currentClose = rates[0].close;
    ema.currentOpen = rates[0].open;
    
    // Release indicator handles
    IndicatorRelease(handleFast);
    IndicatorRelease(handleSlow);
    
    return ema;
}

//+------------------------------------------------------------------+
//| Check for BUY signal (entry conditions)                          |
//+------------------------------------------------------------------+
bool CheckBuySignal(EMAValues &ema)
{
    // Condition 1: Previous candle has crossover of EMA20 above EMA50
    // Previous bar: EMA20 > EMA50 (crossover happened)
    if(!(ema.prevFast > ema.prevSlow))
    {
        Print("FAIL: No crossover on previous bar. Prev EMA20=", ema.prevFast, 
              " Prev EMA50=", ema.prevSlow);
        return false;
    }
    
    // Condition 2: Current candle close price OR body is above EMA20
    // Check if close price is above EMA20
    bool closeAboveEMA20 = (ema.currentClose > ema.currentFast);
    
    // Check if candle body (midpoint between open and close) is above EMA20
    double bodyMidpoint = (ema.currentOpen + ema.currentClose) / 2.0;
    bool bodyAboveEMA20 = (bodyMidpoint > ema.currentFast);
    
    if(!(closeAboveEMA20 || bodyAboveEMA20))
    {
        Print("FAIL: Neither close nor body above EMA20. Close=", ema.currentClose,
              " BodyMid=", bodyMidpoint, " EMA20=", ema.currentFast);
        return false;
    }
    
    // SUCCESS - All conditions met
    Print("SUCCESS: BUY SIGNAL!");
    Print("  Previous: EMA20=", ema.prevFast, " > EMA50=", ema.prevSlow, " (CROSSOVER)");
    Print("  Current: Close=", ema.currentClose, 
          " EMA20=", ema.currentFast, " EMA50=", ema.currentSlow);
    Print("  Body Midpoint: ", bodyMidpoint);
    
    return true;
}

//+------------------------------------------------------------------+
//| Check for SELL signal (exit conditions)                          |
//+------------------------------------------------------------------+
bool CheckSellSignal(EMAValues &ema)
{
    // Simple exit condition: Price closes below EMA20
    if(ema.currentClose < ema.currentFast)
    {
        Print("SELL SIGNAL: Close price ", ema.currentClose, 
              " below EMA20 ", ema.currentFast);
        return true;
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Check if position should be exited                               |
//+------------------------------------------------------------------+
bool ShouldExitPosition(string symbol, ENUM_TIMEFRAMES timeframe, 
                       EMAStrategySettings &settings)
{
    // Get current EMA values
    EMAValues ema = CalculateEMAValues(symbol, timeframe, settings.fastPeriod, settings.slowPeriod);
    
    if(ema.currentFast == 0.0)
        return false;
    
    // Check exit conditions
    return CheckSellSignal(ema);
}

//+------------------------------------------------------------------+
//| Get strategy name                                                |
//+------------------------------------------------------------------+
string GetStrategyName()
{
    return "EMA_Crossover_20_50";
}

//+------------------------------------------------------------------+
//| Get strategy description                                         |
//+------------------------------------------------------------------+
string GetStrategyDescription()
{
    return "Simple EMA 20/50 Crossover Strategy";
}

//+------------------------------------------------------------------+
//| Validate strategy settings                                       |
//+------------------------------------------------------------------+
bool ValidateSettings(EMAStrategySettings &settings)
{
    if(settings.fastPeriod <= 0 || settings.slowPeriod <= 0)
    {
        Print("ERROR: EMA periods must be positive");
        return false;
    }
    
    if(settings.fastPeriod >= settings.slowPeriod)
    {
        Print("ERROR: Fast EMA period must be less than slow EMA period");
        return false;
    }
    
    if(settings.lotSize <= 0)
    {
        Print("ERROR: Lot size must be positive");
        return false;
    }
    
    if(settings.dailyLossLimit < 0)
    {
        Print("ERROR: Daily loss limit cannot be negative");
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Print strategy settings                                          |
//+------------------------------------------------------------------+
void PrintStrategySettings(EMAStrategySettings &settings)
{
    Print("=== EMA Strategy Settings ===");
    Print("Fast EMA Period: ", settings.fastPeriod);
    Print("Slow EMA Period: ", settings.slowPeriod);
    Print("Lot Size: ", settings.lotSize);
    Print("Daily Loss Limit: $", settings.dailyLossLimit);
    Print("Trading Enabled: ", settings.enableTrading ? "Yes" : "No");
    Print("=============================");
}

//+------------------------------------------------------------------+
//| Simple signal check (for quick testing)                          |
//+------------------------------------------------------------------+
bool QuickEMACheck(string symbol, ENUM_TIMEFRAMES timeframe)
{
    EMAStrategySettings settings;
    EMAValues ema = CalculateEMAValues(symbol, timeframe, settings.fastPeriod, settings.slowPeriod);
    
    if(ema.currentFast == 0.0)
        return false;
    
    return CheckBuySignal(ema);
}

#endif // EMASTRATEGY_MQH