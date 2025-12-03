//+------------------------------------------------------------------+
//| MarketData.mqh - Real-time market data management               |
//+------------------------------------------------------------------+
#ifndef MARKETDATA_MQH
#define MARKETDATA_MQH

#include "SymbolInfo.mqh"

//+------------------------------------------------------------------+
//| Market data event types                                         |
//+------------------------------------------------------------------+
enum ENUM_MARKET_EVENT {
    MARKET_EVENT_TICK = 0,
    MARKET_EVENT_BAR_OPEN = 1,
    MARKET_EVENT_BAR_CLOSE = 2,
    MARKET_EVENT_SPIKE = 3,
    MARKET_EVENT_GAP = 4,
    MARKET_EVENT_VOLUME_SPIKE = 5,
    MARKET_EVENT_SPREAD_CHANGE = 6
};

//+------------------------------------------------------------------+
//| Market data event structure                                     |
//+------------------------------------------------------------------+
struct SMarketEvent {
    ENUM_MARKET_EVENT eventType;
    datetime          eventTime;
    string            symbol;
    double            value1;
    double            value2;
    string            description;
};

//+------------------------------------------------------------------+
//| Market statistics structure                                     |
//+------------------------------------------------------------------+
struct SMarketStats {
    double    avgSpread;          // Average spread
    double    maxSpread;          // Maximum spread
    double    minSpread;          // Minimum spread
    double    avgVolatility;      // Average volatility (ATR)
    double    currentVolatility;  // Current volatility
    double    volumeRatio;        // Current volume / average volume
    int       tickCount;          // Tick count in period
    double    bidAskImbalance;    // Bid/Ask volume imbalance
    datetime  lastUpdate;         // Last statistics update
};

//+------------------------------------------------------------------+
//| Secondary timeframe data structure                              |
//+------------------------------------------------------------------+
struct SSecondaryTFData {
    ENUM_TIMEFRAMES   timeframe;
    MqlRates          rates[];    // Dynamic array for rates
    int               bufferSize;
    bool              isInitialized;
};

//+------------------------------------------------------------------+
//| CMarketData - Market data management class                      |
//+------------------------------------------------------------------+
class CMarketData {
private:
    // Core components
    CLogger*          m_logger;
    CSymbolInfo*      m_symbolInfo;
    
    // Data storage
    string            m_symbol;
    ENUM_TIMEFRAMES   m_timeframe;
    MqlRates          m_rates[];          // Primary timeframe rates
    MqlTick           m_ticks[];          // Tick buffer
    SMarketStats      m_stats;
    
    // Multi-timeframe support
    SSecondaryTFData  m_secondaryTFs[5];  // Fixed array of structures
    int               m_secondaryTFCount;
    
    // Time management
    datetime          m_currentBarTime;
    datetime          m_lastTickTime;
    datetime          m_lastStatsUpdate;
    
    // Event management
    SMarketEvent      m_lastEvents[10];
    int               m_eventIndex;
    
    // Configuration
    int               m_historyDepth;     // Bars to keep in memory
    int               m_tickBufferSize;   // Ticks to keep in memory
    bool              m_enableStats;
    bool              m_enableEvents;
    
public:
    // Constructor/Destructor
    CMarketData(string symbol, ENUM_TIMEFRAMES timeframe);
    ~CMarketData();
    
    // Initialization
    bool Initialize(int historyDepth = 1000, int tickBufferSize = 10000);
    void Deinitialize();
    void Refresh();
    
    // Data access methods
    // Price data
    double GetBid();
    double GetAsk();
    double GetLast();
    double GetSpread();
    double GetPoint();
    
    // Time and bar data
    datetime GetCurrentTime();
    datetime GetBarOpenTime(int shift = 0);
    datetime GetBarCloseTime(int shift = 0);
    bool IsNewBar();
    
    // Historical data access
    bool GetRates(MqlRates &rates[], int count = 100, int startPos = 0);
    bool GetTicks(MqlTick &ticks[], int count = 100, datetime from = 0);
    
    // Bar data at specific shift
    double GetOpen(int shift = 0);
    double GetHigh(int shift = 0);
    double GetLow(int shift = 0);
    double GetClose(int shift = 0);
    long   GetVolume(int shift = 0);
    long   GetTickVolume(int shift = 0);
    double GetRealVolume(int shift = 0);
    
    // Calculated market data
    double GetPrice(ENUM_ORDER_TYPE type);
    double GetMidPrice();
    double GetPipValue();
    double GetATR(int period = 14, int shift = 0);
    double GetVolatility(int period = 20);
    
    // Market statistics
    SMarketStats GetMarketStats();
    void UpdateMarketStats();
    
    // Market state detection
    bool IsMarketOpen();
    bool IsSessionActive();
    bool IsVolatile(double threshold = 0.002);
    bool IsTrending(ENUM_TIMEFRAMES tf = PERIOD_H1, int period = 20);
    bool IsRanging(ENUM_TIMEFRAMES tf = PERIOD_H1, int period = 20);
    
    // Event monitoring
    void OnTick();
    void OnTimer();
    void CheckMarketEvents();
    SMarketEvent GetLastEvent();
    bool GetEvents(SMarketEvent &events[], int count = 5);
    
    // Gap detection
    double GetGapSize(int shift = 1);
    bool HasGap(double threshold = 0.001);
    
    // Spread monitoring
    double GetAverageSpread(int period = 20);
    bool IsSpreadNormal(double multiplier = 2.0);
    
    // Volume analysis
    double GetVolumeRatio(int period = 20);
    bool IsVolumeSpike(double threshold = 2.0);
    
    // Multi-timeframe support
    bool AddSecondaryTimeframe(ENUM_TIMEFRAMES tf, int bufferSize = 500);
    bool GetSecondaryRates(ENUM_TIMEFRAMES tf, MqlRates &rates[], int count = 100);
    bool RemoveSecondaryTimeframe(ENUM_TIMEFRAMES tf);
    
    // Data validation
    bool IsDataValid();
    bool IsDataFresh(int maxSeconds = 60);
    int  GetDataAgeSeconds();
    
    // Debug and information
    void PrintMarketInfo();
    string GetMarketStateString();
    
private:
    // Internal methods
    bool LoadHistoryData();
    bool LoadTickData();
    void UpdateRatesBuffer();
    void UpdateTickBuffer();
    void DetectBarEvents();
    void DetectTickEvents();
    void RecordEvent(ENUM_MARKET_EVENT type, double val1 = 0, double val2 = 0, string desc = "");
    
    // Statistics calculation
    void CalculateSpreadStats();
    void CalculateVolatilityStats();
    void CalculateVolumeStats();
    
    // Helper functions
    double CalculateATRFromRates(int period, int shift);
    bool IsPriceSpike(double current, double previous, double threshold);
    bool IsTimeToUpdateStats();
    
    // Buffer management
    bool ResizeRatesBuffer(int newSize);
    bool ResizeTickBuffer(int newSize);
    void ShiftRatesBuffer(int shift);
    void ShiftTickBuffer(int shift);
    
    // Secondary timeframe management
    int FindSecondaryTFIndex(ENUM_TIMEFRAMES tf);
    bool LoadSecondaryTFData(int index);
};

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CMarketData::CMarketData(string symbol, ENUM_TIMEFRAMES timeframe) :
    m_symbol(symbol),
    m_timeframe(timeframe),
    m_logger(NULL),
    m_symbolInfo(NULL),
    m_historyDepth(1000),
    m_tickBufferSize(10000),
    m_enableStats(true),
    m_enableEvents(true),
    m_currentBarTime(0),
    m_lastTickTime(0),
    m_lastStatsUpdate(0),
    m_eventIndex(0),
    m_secondaryTFCount(0)
{
    // Initialize secondary timeframe array
    for(int i = 0; i < 5; i++) {
        m_secondaryTFs[i].timeframe = PERIOD_CURRENT;
        m_secondaryTFs[i].bufferSize = 0;
        m_secondaryTFs[i].isInitialized = false;
    }
    
    // Initialize market stats
    m_stats.avgSpread = 0;
    m_stats.maxSpread = 0;
    m_stats.minSpread = 0;
    m_stats.avgVolatility = 0;
    m_stats.currentVolatility = 0;
    m_stats.volumeRatio = 0;
    m_stats.tickCount = 0;
    m_stats.bidAskImbalance = 0;
    m_stats.lastUpdate = 0;
}

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CMarketData::~CMarketData() {
    Deinitialize();
}

//+------------------------------------------------------------------+
//| Initialize market data                                           |
//+------------------------------------------------------------------+
bool CMarketData::Initialize(int historyDepth = 1000, int tickBufferSize = 10000) {
    m_historyDepth = historyDepth;
    m_tickBufferSize = tickBufferSize;
    
    // Initialize logger (simplified - in real implementation, get from SolaraCore)
    m_logger = new CLogger();
    
    // Initialize symbol info
    m_symbolInfo = new CSymbolInfo(m_symbol);
    if(!m_symbolInfo.Initialize()) {
        if(m_logger != NULL) m_logger.Error("Failed to initialize SymbolInfo for " + m_symbol);
        return false;
    }
    
    // Load historical data
    if(!LoadHistoryData()) {
        if(m_logger != NULL) m_logger.Error("Failed to load historical data for " + m_symbol);
        return false;
    }
    
    // Load tick data
    if(!LoadTickData()) {
        if(m_logger != NULL) m_logger.Warn("Failed to load tick data for " + m_symbol);
    }
    
    if(m_logger != NULL) m_logger.Info("MarketData initialized for " + m_symbol + " on " + TimeframeToString(m_timeframe));
    return true;
}

//+------------------------------------------------------------------+
//| Deinitialize market data                                         |
//+------------------------------------------------------------------+
void CMarketData::Deinitialize() {
    // Clean up secondary timeframe arrays
    for(int i = 0; i < 5; i++) {
        ArrayFree(m_secondaryTFs[i].rates);
    }
    
    // Clean up primary arrays
    ArrayFree(m_rates);
    ArrayFree(m_ticks);
    
    // Delete objects
    if(m_symbolInfo != NULL) {
        delete m_symbolInfo;
        m_symbolInfo = NULL;
    }
    
    if(m_logger != NULL) {
        delete m_logger;
        m_logger = NULL;
    }
}

//+------------------------------------------------------------------+
//| Refresh market data                                              |
//+------------------------------------------------------------------+
void CMarketData::Refresh() {
    UpdateRatesBuffer();
    UpdateTickBuffer();
    
    if(m_enableStats && IsTimeToUpdateStats()) {
        UpdateMarketStats();
    }
    
    if(m_enableEvents) {
        CheckMarketEvents();
    }
}

//+------------------------------------------------------------------+
//| Get current bid price                                            |
//+------------------------------------------------------------------+
double CMarketData::GetBid() {
    if(m_symbolInfo == NULL) return 0;
    return m_symbolInfo.GetBid();
}

//+------------------------------------------------------------------+
//| Get current ask price                                            |
//+------------------------------------------------------------------+
double CMarketData::GetAsk() {
    if(m_symbolInfo == NULL) return 0;
    return m_symbolInfo.GetAsk();
}

//+------------------------------------------------------------------+
//| Get current last price                                           |
//+------------------------------------------------------------------+
double CMarketData::GetLast() {
    if(m_symbolInfo == NULL) return 0;
    return m_symbolInfo.GetLast();
}

//+------------------------------------------------------------------+
//| Get current spread                                               |
//+------------------------------------------------------------------+
double CMarketData::GetSpread() {
    if(m_symbolInfo == NULL) return 0;
    return m_symbolInfo.GetSpread();
}

//+------------------------------------------------------------------+
//| Get point value                                                  |
//+------------------------------------------------------------------+
double CMarketData::GetPoint() {
    if(m_symbolInfo == NULL) return 0;
    return m_symbolInfo.GetPoint();
}

//+------------------------------------------------------------------+
//| Get current time                                                 |
//+------------------------------------------------------------------+
datetime CMarketData::GetCurrentTime() {
    return TimeCurrent();
}

//+------------------------------------------------------------------+
//| Check if new bar has formed                                      |
//+------------------------------------------------------------------+
bool CMarketData::IsNewBar() {
    datetime currentBarTime = iTime(m_symbol, m_timeframe, 0);
    if(currentBarTime != m_currentBarTime) {
        m_currentBarTime = currentBarTime;
        return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Get open price at shift                                          |
//+------------------------------------------------------------------+
double CMarketData::GetOpen(int shift = 0) {
    if(shift >= ArraySize(m_rates) || shift < 0) return 0;
    return m_rates[shift].open;
}

//+------------------------------------------------------------------+
//| Get high price at shift                                          |
//+------------------------------------------------------------------+
double CMarketData::GetHigh(int shift = 0) {
    if(shift >= ArraySize(m_rates) || shift < 0) return 0;
    return m_rates[shift].high;
}

//+------------------------------------------------------------------+
//| Get low price at shift                                           |
//+------------------------------------------------------------------+
double CMarketData::GetLow(int shift = 0) {
    if(shift >= ArraySize(m_rates) || shift < 0) return 0;
    return m_rates[shift].low;
}

//+------------------------------------------------------------------+
//| Get close price at shift                                         |
//+------------------------------------------------------------------+
double CMarketData::GetClose(int shift = 0) {
    if(shift >= ArraySize(m_rates) || shift < 0) return 0;
    return m_rates[shift].close;
}

//+------------------------------------------------------------------+
//| Get volume at shift                                              |
//+------------------------------------------------------------------+
long CMarketData::GetVolume(int shift = 0) {
    if(shift >= ArraySize(m_rates) || shift < 0) return 0;
    return m_rates[shift].tick_volume;
}

//+------------------------------------------------------------------+
//| Get price for order type                                         |
//+------------------------------------------------------------------+
double CMarketData::GetPrice(ENUM_ORDER_TYPE type) {
    if(type == ORDER_TYPE_BUY || type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_BUY_STOP) {
        return GetAsk();
    } else {
        return GetBid();
    }
}

//+------------------------------------------------------------------+
//| Get mid price                                                    |
//+------------------------------------------------------------------+
double CMarketData::GetMidPrice() {
    return (GetBid() + GetAsk()) / 2.0;
}

//+------------------------------------------------------------------+
//| Check if market is open                                          |
//+------------------------------------------------------------------+
bool CMarketData::IsMarketOpen() {
    if(m_symbolInfo == NULL) return false;
    return m_symbolInfo.IsMarketOpen();
}

//+------------------------------------------------------------------+
//| Check if trading session is active                               |
//+------------------------------------------------------------------+
bool CMarketData::IsSessionActive() {
    if(m_symbolInfo == NULL) return false;
    return m_symbolInfo.IsSessionActive();
}

//+------------------------------------------------------------------+
//| Update rates buffer                                              |
//+------------------------------------------------------------------+
void CMarketData::UpdateRatesBuffer() {
    int requiredSize = m_historyDepth;
    if(ArraySize(m_rates) != requiredSize) {
        if(!ResizeRatesBuffer(requiredSize)) {
            return;
        }
    }
    
    // Copy rates data
    if(CopyRates(m_symbol, m_timeframe, 0, requiredSize, m_rates) <= 0) {
        if(m_logger != NULL) m_logger.Error("Failed to copy rates for " + m_symbol);
    }
}

//+------------------------------------------------------------------+
//| Update tick buffer                                               |
//+------------------------------------------------------------------+
void CMarketData::UpdateTickBuffer() {
    // For simplicity, we'll just update the last tick
    // In a full implementation, you'd maintain a rolling buffer
    MqlTick lastTick;
    if(SymbolInfoTick(m_symbol, lastTick)) {
        m_lastTickTime = lastTick.time;
    }
}

//+------------------------------------------------------------------+
//| Resize rates buffer                                              |
//+------------------------------------------------------------------+
bool CMarketData::ResizeRatesBuffer(int newSize) {
    if(newSize <= 0) return false;
    
    if(ArrayResize(m_rates, newSize) != newSize) {
        if(m_logger != NULL) m_logger.Error("Failed to resize rates buffer to " + IntegerToString(newSize));
        return false;
    }
    return true;
}

//+------------------------------------------------------------------+
//| Resize tick buffer                                               |
//+------------------------------------------------------------------+
bool CMarketData::ResizeTickBuffer(int newSize) {
    if(newSize <= 0) return false;
    
    if(ArrayResize(m_ticks, newSize) != newSize) {
        if(m_logger != NULL) m_logger.Warn("Failed to resize tick buffer to " + IntegerToString(newSize));
        return false;
    }
    return true;
}

//+------------------------------------------------------------------+
//| Load historical data                                             |
//+------------------------------------------------------------------+
bool CMarketData::LoadHistoryData() {
    UpdateRatesBuffer();
    return ArraySize(m_rates) > 0;
}

//+------------------------------------------------------------------+
//| Load tick data                                                   |
//+------------------------------------------------------------------+
bool CMarketData::LoadTickData() {
    // Initialize tick buffer
    return ResizeTickBuffer(m_tickBufferSize);
}

//+------------------------------------------------------------------+
//| Check market events                                              |
//+------------------------------------------------------------------+
void CMarketData::CheckMarketEvents() {
    // Check for new bar
    if(IsNewBar()) {
        RecordEvent(MARKET_EVENT_BAR_CLOSE, GetClose(1), GetVolume(1), "Bar closed");
    }
    
    // Check for price spikes
    if(ArraySize(m_rates) >= 2) {
        double currentClose = GetClose(0);
        double previousClose = GetClose(1);
        double change = MathAbs(currentClose - previousClose) / previousClose;
        
        if(change > 0.001) { // 0.1% change
            RecordEvent(MARKET_EVENT_SPIKE, currentClose, change, "Price spike detected");
        }
    }
}

//+------------------------------------------------------------------+
//| Record an event                                                  |
//+------------------------------------------------------------------+
void CMarketData::RecordEvent(ENUM_MARKET_EVENT type, double val1, double val2, string desc) {
    m_eventIndex = (m_eventIndex + 1) % 10;
    
    m_lastEvents[m_eventIndex].eventType = type;
    m_lastEvents[m_eventIndex].eventTime = TimeCurrent();
    m_lastEvents[m_eventIndex].symbol = m_symbol;
    m_lastEvents[m_eventIndex].value1 = val1;
    m_lastEvents[m_eventIndex].value2 = val2;
    m_lastEvents[m_eventIndex].description = desc;
    
    if(m_logger != NULL) {
        m_logger.Info("Market Event: " + desc);
    }
}

//+------------------------------------------------------------------+
//| Get last event                                                   |
//+------------------------------------------------------------------+
SMarketEvent CMarketData::GetLastEvent() {
    return m_lastEvents[m_eventIndex];
}

//+------------------------------------------------------------------+
//| Get multiple events                                              |
//+------------------------------------------------------------------+
bool CMarketData::GetEvents(SMarketEvent &events[], int count = 5) {
    if(count <= 0 || count > 10) count = 5;
    
    if(ArrayResize(events, count) != count) {
        return false;
    }
    
    for(int i = 0; i < count; i++) {
        int index = (m_eventIndex - i + 10) % 10;
        events[i] = m_lastEvents[index];
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Update market statistics                                         |
//+------------------------------------------------------------------+
void CMarketData::UpdateMarketStats() {
    CalculateSpreadStats();
    CalculateVolatilityStats();
    m_stats.lastUpdate = TimeCurrent();
}

//+------------------------------------------------------------------+
//| Calculate spread statistics                                      |
//+------------------------------------------------------------------+
void CMarketData::CalculateSpreadStats() {
    double currentSpread = GetSpread();
    
    if(m_stats.avgSpread == 0) {
        m_stats.avgSpread = currentSpread;
        m_stats.minSpread = currentSpread;
        m_stats.maxSpread = currentSpread;
    } else {
        m_stats.avgSpread = (m_stats.avgSpread * 0.9) + (currentSpread * 0.1);
        m_stats.minSpread = MathMin(m_stats.minSpread, currentSpread);
        m_stats.maxSpread = MathMax(m_stats.maxSpread, currentSpread);
    }
}

//+------------------------------------------------------------------+
//| Calculate volatility statistics                                  |
//+------------------------------------------------------------------+
void CMarketData::CalculateVolatilityStats() {
    // Simplified volatility calculation
    if(ArraySize(m_rates) >= 20) {
        double sum = 0;
        for(int i = 0; i < 20; i++) {
            sum += (m_rates[i].high - m_rates[i].low) / m_rates[i].close;
        }
        m_stats.currentVolatility = sum / 20.0;
        
        if(m_stats.avgVolatility == 0) {
            m_stats.avgVolatility = m_stats.currentVolatility;
        } else {
            m_stats.avgVolatility = (m_stats.avgVolatility * 0.9) + (m_stats.currentVolatility * 0.1);
        }
    }
}

//+------------------------------------------------------------------+
//| Check if it's time to update statistics                          |
//+------------------------------------------------------------------+
bool CMarketData::IsTimeToUpdateStats() {
    return (TimeCurrent() - m_lastStatsUpdate) > 60; // Update every minute
}

//+------------------------------------------------------------------+
//| Add secondary timeframe                                          |
//+------------------------------------------------------------------+
bool CMarketData::AddSecondaryTimeframe(ENUM_TIMEFRAMES tf, int bufferSize = 500) {
    if(m_secondaryTFCount >= 5) {
        if(m_logger != NULL) m_logger.Error("Maximum secondary timeframes reached (5)");
        return false;
    }
    
    int index = m_secondaryTFCount;
    m_secondaryTFs[index].timeframe = tf;
    m_secondaryTFs[index].bufferSize = bufferSize;
    
    if(!LoadSecondaryTFData(index)) {
        return false;
    }
    
    m_secondaryTFCount++;
    return true;
}

//+------------------------------------------------------------------+
//| Load secondary timeframe data                                    |
//+------------------------------------------------------------------+
bool CMarketData::LoadSecondaryTFData(int index) {
    if(index < 0 || index >= 5) return false;
    
    ENUM_TIMEFRAMES tf = m_secondaryTFs[index].timeframe;
    int bufferSize = m_secondaryTFs[index].bufferSize;
    
    if(ArrayResize(m_secondaryTFs[index].rates, bufferSize) != bufferSize) {
        if(m_logger != NULL) m_logger.Error("Failed to allocate buffer for secondary TF");
        return false;
    }
    
    if(CopyRates(m_symbol, tf, 0, bufferSize, m_secondaryTFs[index].rates) <= 0) {
        if(m_logger != NULL) m_logger.Error("Failed to copy rates for secondary TF");
        return false;
    }
    
    m_secondaryTFs[index].isInitialized = true;
    return true;
}

//+------------------------------------------------------------------+
//| Find secondary timeframe index                                   |
//+------------------------------------------------------------------+
int CMarketData::FindSecondaryTFIndex(ENUM_TIMEFRAMES tf) {
    for(int i = 0; i < m_secondaryTFCount; i++) {
        if(m_secondaryTFs[i].timeframe == tf) {
            return i;
        }
    }
    return -1;
}

//+------------------------------------------------------------------+
//| Utility: Timeframe to string                                     |
//+------------------------------------------------------------------+
string TimeframeToString(ENUM_TIMEFRAMES tf) {
    switch(tf) {
        case PERIOD_M1: return "M1";
        case PERIOD_M5: return "M5";
        case PERIOD_M15: return "M15";
        case PERIOD_M30: return "M30";
        case PERIOD_H1: return "H1";
        case PERIOD_H4: return "H4";
        case PERIOD_D1: return "D1";
        case PERIOD_W1: return "W1";
        case PERIOD_MN1: return "MN1";
        default: return "CURRENT";
    }
}

#endif