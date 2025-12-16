// EMAStrategy.mqh - EMA Crossover Strategy for Multi-Symbol Scanner
//+------------------------------------------------------------------+
//| Description: Implements EMA 20/50 crossover strategy with       |
//|              precise entry/exit conditions                       |
//+------------------------------------------------------------------+
#ifndef EMASTRATEGY_MQH
#define EMASTRATEGY_MQH

#include "TradeLogger.mqh"

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
    double prev2Fast;        // EMA fast on bar before previous (bar 2)
    double prev2Slow;        // EMA slow on bar before previous (bar 2)
    double currentClose;     // Close price on current bar
    double currentOpen;      // Open price on current bar
    double currentHigh;      // High price on current bar
    double currentLow;       // Low price on current bar
    
    EMAValues() {
        currentFast = 0.0;
        currentSlow = 0.0;
        prevFast = 0.0;
        prevSlow = 0.0;
        prev2Fast = 0.0;
        prev2Slow = 0.0;
        currentClose = 0.0;
        currentOpen = 0.0;
        currentHigh = 0.0;
        currentLow = 0.0;
    }
};

//+------------------------------------------------------------------+
//| Check EMA crossover strategy for given symbol/timeframe          |
//+------------------------------------------------------------------+
TradingSignal CheckEMAStrategy(string symbol, ENUM_TIMEFRAMES timeframe, 
                              EMAStrategySettings &settings)
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
    
    // Check for BUY signal (EMA crossover)
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
    // Check for SELL signal (exit condition)
    else if(CheckSellSignal(ema))
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
    
    // Copy EMA values for bars 0, 1, 2
    double fastValues[3];
    double slowValues[3];
    
    // Copy fast EMA values (current bar = 0, previous = 1, previous-1 = 2)
    if(CopyBuffer(handleFast, 0, 0, 3, fastValues) < 3)
    {
        Print("ERROR: Cannot copy fast EMA values for ", symbol);
        IndicatorRelease(handleFast);
        IndicatorRelease(handleSlow);
        return ema;
    }
    
    // Copy slow EMA values
    if(CopyBuffer(handleSlow, 0, 0, 3, slowValues) < 3)
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
    ema.prev2Fast = fastValues[2];     // Bar 2 (previous-1)
    
    ema.currentSlow = slowValues[0];   // Bar 0 (current)
    ema.prevSlow = slowValues[1];      // Bar 1 (previous)
    ema.prev2Slow = slowValues[2];     // Bar 2 (previous-1)
    
    ema.currentClose = rates[0].close;
    ema.currentOpen = rates[0].open;
    ema.currentHigh = rates[0].high;
    ema.currentLow = rates[0].low;
    
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
    // Condition 1: Current price above both EMAs
    if(ema.currentClose <= ema.currentFast || ema.currentClose <= ema.currentSlow)
        return false;
    
    // Condition 2: EMA crossover happened on previous bar
    // Previous bar: fast EMA > slow EMA (crossover just happened)
    if(ema.prevFast <= ema.prevSlow)
        return false;
    
    // Condition 3: Before previous bar: fast EMA <= slow EMA (before crossover)
    if(ema.prev2Fast > ema.prev2Slow)
        return false;
    
    // Condition 4: Crossover is fresh (happened exactly on previous bar)
    // This is already ensured by conditions 2 and 3
    
    // All conditions met
    return true;
}

//+------------------------------------------------------------------+
//| Check for SELL signal (exit conditions)                          |
//+------------------------------------------------------------------+
bool CheckSellSignal(EMAValues &ema)
{
    // Exit Condition: Price below EMA20 AND candle body not touching EMA20
    
    // Check if close price is below EMA20
    if(ema.currentClose >= ema.currentFast)
        return false;
    
    // Calculate candle body midpoint
    double bodyMidpoint = (ema.currentOpen + ema.currentClose) / 2.0;
    
    // Check if candle body touches EMA20
    // Body touches EMA20 if: EMA20 is between open and close prices
    double minPrice = MathMin(ema.currentOpen, ema.currentClose);
    double maxPrice = MathMax(ema.currentOpen, ema.currentClose);
    
    if(ema.currentFast >= minPrice && ema.currentFast <= maxPrice)
    {
        // Candle body touches EMA20 line - don't exit
        return false;
    }
    
    // Additional filter: Check if price is significantly below EMA20
    // (at least 0.1% below to avoid whipsaws)
    double priceBelowPercent = ((ema.currentFast - ema.currentClose) / ema.currentFast) * 100;
    if(priceBelowPercent < 0.1)
        return false;
    
    // All exit conditions met
    return true;
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
    return "EMA 20/50 Crossover Strategy - " +
           "Entry: Price above both EMAs with crossover on previous bar. " +
           "Exit: Price below EMA20 with candle body not touching EMA20.";
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