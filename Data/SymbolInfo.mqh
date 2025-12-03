//+------------------------------------------------------------------+
//| SymbolInfo.mqh - Symbol and instrument information management   |
//+------------------------------------------------------------------+
#ifndef SYMBOLINFO_MQH
#define SYMBOLINFO_MQH

#include "..\Utilities\Logger.mqh"

//+------------------------------------------------------------------+
//| Symbol trading session structure                                |
//+------------------------------------------------------------------+
struct SSymbolSession {
    int      sessionIndex;       // Session index (0-3)
    ENUM_DAY_OF_WEEK dayOfWeek;  // Day of week
    int      openHour;           // Session open hour
    int      openMinute;         // Session open minute
    int      closeHour;          // Session close hour
    int      closeMinute;        // Session close minute
};

//+------------------------------------------------------------------+
//| Symbol configuration structure                                  |
//+------------------------------------------------------------------+
struct SSymbolConfig {
    string   symbol;             // Symbol name
    double   point;              // Point value
    double   tickSize;           // Minimum price change
    double   tickValue;          // Value per tick
    int      digits;             // Number of decimal places
    double   contractSize;       // Contract size
    string   currencyBase;       // Base currency
    string   currencyProfit;     // Profit currency
    string   currencyMargin;     // Margin currency
    double   marginInitial;      // Initial margin
    double   marginMaintenance;  // Maintenance margin
    double   marginLong;         // Long position margin
    double   marginShort;        // Short position margin
    double   marginLimit;        // Margin limit
    double   marginStop;         // Margin stop level
    double   marginStopLimit;    // Margin stop limit
    double   spread;             // Current spread
    double   spreadFloat;        // Is spread floating?
    double   stopsLevel;         // Stops level in points
    double   freezeLevel;        // Freeze level in points
    long     volumeMin;          // Minimum volume
    long     volumeMax;          // Maximum volume
    long     volumeStep;         // Volume step
    long     volumeLimit;        // Volume limit
    double   swapLong;           // Long swap
    double   swapShort;          // Short swap
    int      swapMode;           // Swap calculation mode
    int      swapRollover3days;  // Swap rollover day
    int      expirationMode;     // Expiration mode
    datetime expirationTime;     // Expiration time
    int      fillingMode;        // Order filling mode
    int      orderMode;          // Order execution mode
};

//+------------------------------------------------------------------+
//| CSymbolInfo - Symbol information management class               |
//+------------------------------------------------------------------+
class CSymbolInfo {
private:
    string            m_symbol;
    SSymbolConfig     m_config;
    SSymbolSession    m_sessions[4];  // Up to 4 trading sessions
    int               m_sessionCount;
    CLogger*          m_logger;
    
    // Cache for performance
    double            m_point;
    double            m_tickValue;
    double            m_marginRate;
    MqlTick           m_lastTick;
    datetime          m_lastTickTime;
    
    // Timezone and session management
    int               m_gmtOffset;
    bool              m_isSessionActive[7][24];  // Day x Hour matrix
    
public:
    // Constructor/Destructor
    CSymbolInfo(string symbol);
    ~CSymbolInfo();
    
    // Initialization
    bool Initialize();
    void Refresh();
    
    // Symbol properties
    string GetSymbol() const { return m_symbol; }
    double GetPoint() const { return m_point; }
    double GetTickValue() const { return m_tickValue; }
    int GetDigits() const { return (int)m_config.digits; }
    double GetSpread() const { return m_config.spread; }
    double GetContractSize() const { return m_config.contractSize; }
    double GetMarginRate() const { return m_marginRate; }
    
    // Current price information
    double GetBid();
    double GetAsk();
    double GetLast();
    datetime GetLastTickTime();
    
    // Volume information
    long GetVolumeMin() const { return m_config.volumeMin; }
    long GetVolumeMax() const { return m_config.volumeMax; }
    long GetVolumeStep() const { return m_config.volumeStep; }
    
    // Margin calculations
    double CalculateMargin(ENUM_ORDER_TYPE type, double volume);
    double CalculateProfit(double priceOpen, double priceClose, 
                          ENUM_ORDER_TYPE type, double volume);
    double CalculateSwap(ENUM_ORDER_TYPE type, double volume, datetime time = 0);
    
    // Trading session management
    bool IsTradingAllowed();
    bool IsSessionActive();
    bool IsMarketOpen();
    datetime GetSessionOpenTime();
    datetime GetSessionCloseTime();
    int GetMinutesToSessionClose();
    
    // Validation functions
    bool ValidatePrice(double price, ENUM_ORDER_TYPE type);
    bool ValidateVolume(double volume);
    bool ValidateStops(double price, double stopLoss, double takeProfit, 
                      ENUM_ORDER_TYPE type);
    
    // Tick data management
    bool GetTick(MqlTick &tick);
    bool GetLastTicks(MqlTick &ticks[], int count);
    
    // Timezone functions
    datetime LocalToGMT(datetime localTime);
    datetime GMTToLocal(datetime gmtTime);
    int GetGMTOffset() const { return m_gmtOffset; }
    
    // Information display
    void PrintInfo();
    string GetInfoString();
    
private:
    bool LoadSymbolConfig();
    bool LoadTradingSessions();
    void BuildSessionMatrix();
    bool IsTimeInSession(datetime time);
    void UpdateTickCache();
    double NormalizePrice(double price);
    double NormalizeVolume(double volume);
};

#endif