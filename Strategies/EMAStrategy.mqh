// EMAStrategy.mqh - Refactored EMA Crossover Strategy
//+------------------------------------------------------------------+
//| Description: EMA 20/50 crossover strategy refactored to extend   |
//|              StrategyBase class                                  |
//+------------------------------------------------------------------+
#ifndef EMASTRATEGY_MQH
#define EMASTRATEGY_MQH

#include "../StrategyBase.mqh"
#include "../ScannerCore.mqh"
#include "../TradeLogger.mqh"
#include "../Symbols.mqh"

//+------------------------------------------------------------------+
//| EMA Strategy Class                                               |
//+------------------------------------------------------------------+
class CEMAStrategy : public CStrategyBase
{
private:
    // EMA-specific settings
    int               m_fastPeriod;
    int               m_slowPeriod;
    ENUM_TIMEFRAMES   m_timeframes[];  // Timeframes to scan
    int               m_timeframeCount;
    
    // For tracking last bar times per symbol per timeframe
    struct SymbolTimeframeState
    {
        string symbol;
        ENUM_TIMEFRAMES timeframe;
        datetime lastBarTime;
    };
    SymbolTimeframeState m_states[100]; // Simple fixed array
    int m_stateCount;
    
public:
    // Constructor
    CEMAStrategy() : CStrategyBase()
    {
        m_strategyName = "EMA_Crossover";
        m_type = STRATEGY_TYPE_EMA;
        m_fastPeriod = 20;
        m_slowPeriod = 50;
        m_stateCount = 0;
        
        // Default timeframes
        ArrayResize(m_timeframes, 3);
        m_timeframes[0] = PERIOD_H1;
        m_timeframes[1] = PERIOD_H4;
        m_timeframes[2] = PERIOD_D1;
        m_timeframeCount = 3;
        
        // Default settings
        m_settings.name = m_strategyName;
        m_settings.enabled = false;
        m_settings.lotSize = 0.01;
        m_settings.dailyLossLimit = 100.0;
        m_settings.maxPositions = 10;
        m_settings.magicNumber = 12345;
    }
    
    // Destructor
    ~CEMAStrategy() {}
    
    // Initialize strategy
    virtual bool Initialize() override
    {
        Print("Initializing EMA Strategy: ", m_strategyName);
        
        if(!ValidateSettings())
        {
            Print("ERROR: EMA Strategy settings validation failed");
            return false;
        }
        
        // Initialize state tracking
        m_stateCount = 0;
        
        Print("EMA Strategy initialized successfully");
        PrintSettings();
        return true;
    }
    
    // Deinitialize strategy
    virtual void Deinitialize() override
    {
        Print("Deinitializing EMA Strategy: ", m_strategyName);
        m_stateCount = 0;
    }
    
    // Check for signal on specific symbol/timeframe
    virtual BaseSignal CheckSignal(string symbol, ENUM_TIMEFRAMES timeframe) override
    {
        BaseSignal signal;
        signal.symbol = symbol;
        signal.strategyName = m_strategyName;
        signal.timeframe = TimeframeToString(timeframe);
        
        // Check if we already have a position on this symbol
        if(HasOpenPosition(symbol))
        {
            // Check for exit signal
            if(ShouldExitPosition(symbol))
            {
                signal.signal = "SELL"; // Exit signal (assuming long position)
                signal.price = SymbolInfoDouble(symbol, SYMBOL_BID);
                signal.action = "EXIT_SIGNAL";
                signal.comment = "Price below EMA20 exit";
            }
            return signal;
        }
        
        // Check entry conditions
        if(!HasOpenPosition(symbol))
        {
            // Get EMA values
            EMAValues ema = CalculateEMAValues(symbol, timeframe);
            
            if(ema.currentFast > 0 && ema.currentSlow > 0)
            {
                // Check for BUY signal
                if(CheckBuySignal(ema))
                {
                    signal.signal = "BUY";
                    signal.price = SymbolInfoDouble(symbol, SYMBOL_ASK);
                    signal.value1 = ema.currentFast; // EMA20
                    signal.value2 = ema.currentSlow; // EMA50
                    signal.action = m_settings.enabled ? "TRADED" : "SCREENED";
                    signal.comment = "EMA20/50 Crossover";
                }
            }
        }
        
        return signal;
    }
    
    // Execute signal
    virtual bool ExecuteSignal(BaseSignal &signal) override
    {
        if(!m_settings.enabled || signal.signal == "")
            return false;
        
        if(signal.action != "TRADED")
            return false;
        
        // Check daily loss limit
        if(GetTodayPNL() <= -m_settings.dailyLossLimit)
        {
            Print("Daily loss limit reached for EMA Strategy: $", DoubleToString(GetTodayPNL(), 2));
            return false;
        }
        
        // Check max positions
        if(CountOpenPositions() >= m_settings.maxPositions)
        {
            Print("Max positions reached for EMA Strategy: ", CountOpenPositions());
            return false;
        }
        
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
            request.price = SymbolInfoDouble(signal.symbol, SYMBOL_ASK);
        else
            request.price = SymbolInfoDouble(signal.symbol, SYMBOL_BID);
        
        request.deviation = 10;
        request.comment = signal.strategyName + ": " + signal.comment;
        
        bool success = OrderSend(request, result);
        
        if(success && result.retcode == TRADE_RETCODE_DONE)
        {
            Print("EMA Strategy trade executed: ", signal.signal, " ", signal.symbol,
                  " @ ", DoubleToString(request.price, 5));
            return true;
        }
        else
        {
            Print("EMA Strategy trade failed: ", signal.signal, " ", signal.symbol);
            return false;
        }
    }
    
    // Check if position should be exited
    virtual bool ShouldExitPosition(string symbol) override
    {
        // For EMA strategy, exit when price closes below EMA20 on any timeframe
        for(int i = 0; i < m_timeframeCount; i++)
        {
            EMAValues ema = CalculateEMAValues(symbol, m_timeframes[i]);
            if(ema.currentFast > 0 && ema.currentClose < ema.currentFast)
                return true;
        }
        return false;
    }
    
    // Timer event - scan all symbols on all timeframes
    virtual void OnTimer() override
    {
        if(!m_settings.enabled)
            return;
        
        // Get all symbols from Symbols.mqh
        int symbolCount = ::GetSymbolCount();  // Use global scope resolution
        
        for(int s = 0; s < symbolCount; s++)
        {
            string symbol = ::GetSymbol(s);  // Use global scope resolution
            
            if(!IsValidSymbol(symbol))
                continue;
            
            for(int t = 0; t < m_timeframeCount; t++)
            {
                // Check if new bar has formed
                if(IsNewBarForSymbol(symbol, m_timeframes[t]))
                {
                    BaseSignal signal = CheckSignal(symbol, m_timeframes[t]);
                    
                    if(signal.signal != "")
                    {
                        // Log the signal
                        ::LogSignalToCSV("ScannerSignals.csv", signal, true);  // Use global scope
                        
                        // Execute if trading is enabled
                        if(signal.action == "TRADED")
                        {
                            ExecuteSignal(signal);
                        }
                    }
                }
            }
        }
    }
    
    // Check if new bar has formed for specific symbol/timeframe
    bool IsNewBarForSymbol(string symbol, ENUM_TIMEFRAMES timeframe)
    {
        // Find existing state
        for(int i = 0; i < m_stateCount; i++)
        {
            if(m_states[i].symbol == symbol && m_states[i].timeframe == timeframe)
            {
                datetime currentBarTime = iTime(symbol, timeframe, 0);
                if(currentBarTime != m_states[i].lastBarTime)
                {
                    m_states[i].lastBarTime = currentBarTime;
                    return true;
                }
                return false;
            }
        }
        
        // Add new state
        if(m_stateCount < 100)
        {
            m_states[m_stateCount].symbol = symbol;
            m_states[m_stateCount].timeframe = timeframe;
            m_states[m_stateCount].lastBarTime = iTime(symbol, timeframe, 0);
            m_stateCount++;
            return true; // First time checking, treat as new bar
        }
        
        return false;
    }
    
    // EMA-specific methods from original EMAStrategy.mqh
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
    
    // Calculate EMA values
    EMAValues CalculateEMAValues(string symbol, ENUM_TIMEFRAMES timeframe)
    {
        EMAValues ema;
        
        // Get handle for EMA indicators
        int handleFast = iMA(symbol, timeframe, m_fastPeriod, 0, MODE_EMA, PRICE_CLOSE);
        int handleSlow = iMA(symbol, timeframe, m_slowPeriod, 0, MODE_EMA, PRICE_CLOSE);
        
        if(handleFast == INVALID_HANDLE || handleSlow == INVALID_HANDLE)
            return ema;
        
        // Copy EMA values for bars 0 and 1
        double fastValues[2];
        double slowValues[2];
        
        if(CopyBuffer(handleFast, 0, 0, 2, fastValues) < 2)
        {
            IndicatorRelease(handleFast);
            IndicatorRelease(handleSlow);
            return ema;
        }
        
        if(CopyBuffer(handleSlow, 0, 0, 2, slowValues) < 2)
        {
            IndicatorRelease(handleFast);
            IndicatorRelease(handleSlow);
            return ema;
        }
        
        // Get price data for current bar
        MqlRates rates[1];
        if(CopyRates(symbol, timeframe, 0, 1, rates) < 1)
        {
            IndicatorRelease(handleFast);
            IndicatorRelease(handleSlow);
            return ema;
        }
        
        // Assign values
        ema.currentFast = fastValues[0];
        ema.prevFast = fastValues[1];
        ema.currentSlow = slowValues[0];
        ema.prevSlow = slowValues[1];
        ema.currentClose = rates[0].close;
        ema.currentOpen = rates[0].open;
        
        IndicatorRelease(handleFast);
        IndicatorRelease(handleSlow);
        
        return ema;
    }
    
    // Check for BUY signal
    bool CheckBuySignal(EMAValues &ema)
    {
        // Condition 1: Previous candle has crossover of EMA20 above EMA50
        if(!(ema.prevFast > ema.prevSlow))
            return false;
        
        // Condition 2: Current candle close price OR body is above EMA20
        bool closeAboveEMA20 = (ema.currentClose > ema.currentFast);
        double bodyMidpoint = (ema.currentOpen + ema.currentClose) / 2.0;
        bool bodyAboveEMA20 = (bodyMidpoint > ema.currentFast);
        
        if(!(closeAboveEMA20 || bodyAboveEMA20))
            return false;
        
        return true;
    }
    
    // Check for SELL/EXIT signal
    bool CheckSellSignal(EMAValues &ema)
    {
        // Simple exit condition: Price closes below EMA20
        return (ema.currentClose < ema.currentFast);
    }
    
    // Set EMA periods
    void SetPeriods(int fast, int slow)
    {
        m_fastPeriod = fast;
        m_slowPeriod = slow;
    }
    
    // Get EMA periods
    void GetPeriods(int &fast, int &slow)
    {
        fast = m_fastPeriod;
        slow = m_slowPeriod;
    }
    
    // Validate EMA-specific settings
    virtual bool ValidateSettings() override
    {
        if(!CStrategyBase::ValidateSettings())
            return false;
        
        if(m_fastPeriod <= 0 || m_slowPeriod <= 0)
            return false;
        
        if(m_fastPeriod >= m_slowPeriod)
            return false;
        
        return true;
    }
    
    // Print EMA-specific settings
    virtual void PrintSettings() override
    {
        CStrategyBase::PrintSettings();
        Print("Fast EMA Period: ", m_fastPeriod);
        Print("Slow EMA Period: ", m_slowPeriod);
        Print("Timeframes: ");
        for(int i = 0; i < m_timeframeCount; i++)
            Print("  - ", TimeframeToString(m_timeframes[i]));
    }
};

#endif // EMASTRATEGY_MQH