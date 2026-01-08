// StrategyBase.mqh - Abstract base class for all trading strategies
//+------------------------------------------------------------------+
//| Description: Base class that all trading strategies must inherit |
//|              from. Provides common interface and functionality.  |
//+------------------------------------------------------------------+
#ifndef STRATEGYBASE_MQH
#define STRATEGYBASE_MQH

#include "ScannerCore.mqh"

//+------------------------------------------------------------------+
//| Strategy type enumeration                                        |
//+------------------------------------------------------------------+
enum ENUM_STRATEGY_TYPE
{
    STRATEGY_TYPE_NONE = 0,
    STRATEGY_TYPE_BBREVERSAL = 1,
    STRATEGY_TYPE_PTS = 2
    
};

//+------------------------------------------------------------------+
//| Base signal structure                                            |
//+------------------------------------------------------------------+
struct BaseSignal
{
    datetime timestamp;
    string   symbol;
    string   strategyName;
    string   signal;        // "BUY", "SELL", "EXIT"
    double   price;
    double   value1;        // Strategy-specific value 1 (EMA20 for EMA)
    double   value2;        // Strategy-specific value 2 (EMA50 for EMA)
    string   timeframe;
    string   action;        // "SCREENED", "TRADED", "EXIT_SIGNAL"
    string   comment;       // Additional info
    
    BaseSignal()
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
    }
};

//+------------------------------------------------------------------+
//| Base settings structure                                          |
//+------------------------------------------------------------------+
struct BaseSettings
{
    string   name;
    bool     enabled;
    double   lotSize;
    double   dailyLossLimit;
    int      maxPositions;
    int      magicNumber;
    
    BaseSettings()
    {
        name = "";
        enabled = false;
        lotSize = 0.01;
        dailyLossLimit = 100.0;
        maxPositions = 10;
        magicNumber = 0;
    }
};

//+------------------------------------------------------------------+
//| Abstract Strategy Base Class                                     |
//+------------------------------------------------------------------+
class CStrategyBase
{
protected:
    BaseSettings    m_settings;
    string          m_strategyName;
    ENUM_STRATEGY_TYPE m_type;
    
public:
    // Constructor
    CStrategyBase() { m_strategyName = "BaseStrategy"; m_type = STRATEGY_TYPE_BBREVERSAL; } 
    
    // Virtual destructor
    virtual ~CStrategyBase() {}
    
    // Pure virtual functions that must be implemented by derived classes
    virtual bool      Initialize() = 0;
    virtual void      Deinitialize() = 0;
    virtual BaseSignal CheckSignal(string symbol, ENUM_TIMEFRAMES timeframe) = 0;
    virtual bool      ExecuteSignal(BaseSignal &signal) = 0;
    virtual bool      ShouldExitPosition(string symbol) = 0;
    virtual void      OnTimer() = 0;
    
    // Common methods with default implementation
    virtual string    GetName() { return m_strategyName; }
    virtual ENUM_STRATEGY_TYPE GetType() { return m_type; }
    virtual bool      IsEnabled() { return m_settings.enabled; }
    virtual void      SetEnabled(bool enabled) { m_settings.enabled = enabled; }
    virtual int       GetMagicNumber() { return m_settings.magicNumber; }
    virtual double    GetDailyLossLimit() { return m_settings.dailyLossLimit; }
    virtual int       GetMaxPositions() { return m_settings.maxPositions; }
    
    // Position counting
    virtual int       CountOpenPositions()
    {
        int count = 0;
        for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
            ulong ticket = PositionGetTicket(i);
            if(PositionGetString(POSITION_SYMBOL) != "")
            {
                if(PositionGetInteger(POSITION_MAGIC) == m_settings.magicNumber)
                    count++;
            }
        }
        return count;
    }
    
    // Check if symbol has open position from this strategy
    virtual bool      HasOpenPosition(string symbol)
    {
        for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
            ulong ticket = PositionGetTicket(i);
            if(PositionGetString(POSITION_SYMBOL) == symbol)
            {
                if(PositionGetInteger(POSITION_MAGIC) == m_settings.magicNumber)
                    return true;
            }
        }
        return false;
    }
    
    // Get P&L for today's positions
    virtual double    GetTodayPNL()
    {
        double pnl = 0.0;
        MqlDateTime today;
        TimeCurrent(today);
        today.hour = 0; today.min = 0; today.sec = 0;
        datetime startOfDay = StructToTime(today);
        
        for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
            ulong ticket = PositionGetTicket(i);
            if(PositionGetInteger(POSITION_MAGIC) == m_settings.magicNumber)
            {
                // Check if position was opened today
                datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
                if(openTime >= startOfDay)
                {
                    pnl += PositionGetDouble(POSITION_PROFIT);
                }
            }
        }
        return pnl;
    }
    
    // Validate settings
    virtual bool      ValidateSettings() 
    { 
        if(m_settings.lotSize <= 0) return false;
        if(m_settings.maxPositions < 0) return false;
        if(m_settings.magicNumber == 0) return false;
        return true;
    }
    
    // Print settings
    virtual void      PrintSettings()
    {
        Print("=== Strategy: ", m_strategyName, " ===");
        Print("Enabled: ", m_settings.enabled ? "Yes" : "No");
        Print("Lot Size: ", m_settings.lotSize);
        Print("Daily Loss Limit: $", m_settings.dailyLossLimit);
        Print("Max Positions: ", m_settings.maxPositions);
        Print("Magic Number: ", m_settings.magicNumber);
        Print("============================");
    }
};

#endif // STRATEGYBASE_MQH