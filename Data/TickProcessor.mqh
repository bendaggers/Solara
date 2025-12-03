// TickProcessor.mqh - Advanced tick data processing for Solara Platform
//+------------------------------------------------------------------+
//| Description: Processes tick-by-tick data for market analysis     |
//|              including volume profiling, tick statistics, and    |
//|              high-frequency data management                      |
//+------------------------------------------------------------------+
#ifndef TICKPROCESSOR_MQH
#define TICKPROCESSOR_MQH

//+------------------------------------------------------------------+
//| Includes                                                         |
//+------------------------------------------------------------------+
#include "..\Utilities\Logger.mqh"
#include "MarketData.mqh"
#include "..\Utilities\DateTimeUtils.mqh"
#include "..\Utilities\ArrayUtils.mqh"

//+------------------------------------------------------------------+
//| Tick data structure for MT5                                      |
//+------------------------------------------------------------------+
struct STickData {
    datetime time;          // Time of the last price update
    double   bid;           // Current Bid price
    double   ask;           // Current Ask price
    double   last;          // Last deal price
    long     volume;        // Volume for the current Last price
    long     time_msc;      // Time of a price update in milliseconds
    uint     flags;         // Tick flags
    double   volume_real;   // Volume for the current Last price with greater accuracy
    double   spread;        // Current spread (ask - bid)
    
    // Default constructor
    STickData() : 
        time(0), 
        bid(0), 
        ask(0), 
        last(0), 
        volume(0), 
        time_msc(0), 
        flags(0), 
        volume_real(0), 
        spread(0) 
    {}
    
    // Constructor from MqlTick
    STickData(const MqlTick &tick) {
        time = tick.time;
        bid = tick.bid;
        ask = tick.ask;
        last = tick.last;
        volume = (long)tick.volume;
        time_msc = tick.time_msc;
        flags = tick.flags;
        volume_real = tick.volume_real;
        spread = tick.ask - tick.bid;
    }
};

//+------------------------------------------------------------------+
//| Volume Profile level structure                                   |
//+------------------------------------------------------------------+
struct SVolumeLevel {
    double    price;         // Price level
    long      volume;        // Total volume at this level
    long      bid_volume;    // Bid volume
    long      ask_volume;    // Ask volume
    datetime  first_time;    // First time price reached this level
    datetime  last_time;     // Last time price reached this level
    int       tick_count;    // Number of ticks at this level
    
    // Default constructor
    SVolumeLevel() : 
        price(0), 
        volume(0), 
        bid_volume(0), 
        ask_volume(0), 
        first_time(0), 
        last_time(0), 
        tick_count(0) 
    {}
};

//+------------------------------------------------------------------+
//| Tick statistics structure                                        |
//+------------------------------------------------------------------+
struct STickStats {
    datetime  period_start;     // Start time of statistics period
    int       total_ticks;      // Total number of ticks
    int       bid_updates;      // Number of bid updates
    int       ask_updates;      // Number of ask updates
    int       last_updates;     // Number of last price updates
    double    avg_spread;       // Average spread in points
    double    max_spread;       // Maximum spread in points
    double    min_spread;       // Minimum spread in points
    long      total_volume;     // Total volume
    double    volatility;       // Standard deviation of price changes
    double    avg_tick_speed;   // Average ticks per second
    double    bid_ask_ratio;    // Ratio of bid to ask volume
    int       session_ticks;    // Ticks in current session
    
    // Default constructor
    STickStats() {
        Reset();
    }
    
    void Reset() {
        period_start = TimeCurrent();
        total_ticks = 0;
        bid_updates = 0;
        ask_updates = 0;
        last_updates = 0;
        avg_spread = 0;
        max_spread = 0;
        min_spread = 0;
        total_volume = 0;
        volatility = 0;
        avg_tick_speed = 0;
        bid_ask_ratio = 0;
        session_ticks = 0;
    }
};

//+------------------------------------------------------------------+
//| Tick velocity structure                                          |
//+------------------------------------------------------------------+
struct STickVelocity {
    double    ticks_per_second;    // Current tick rate
    double    avg_ticks_per_second;// Average tick rate
    double    max_ticks_per_second;// Maximum tick rate
    datetime  last_tick_time;      // Time of last tick
    double    time_since_last;     // Milliseconds since last tick
};

//+------------------------------------------------------------------+
//| Order flow imbalance structure                                   |
//+------------------------------------------------------------------+
struct SOrderFlowImbalance {
    double    imbalance;           // Bid/Ask volume imbalance (-1 to +1)
    double    cumulative_imbalance;// Cumulative imbalance
    long      total_bid_volume;    // Total bid volume
    long      total_ask_volume;    // Total ask volume
    double    price_pressure;      // Price pressure indicator
};

//+------------------------------------------------------------------+
//| CTickProcessor - Advanced tick processing class                  |
//+------------------------------------------------------------------+
class CTickProcessor {
private:
    // Core components
    string           m_symbol;
    ENUM_TIMEFRAMES  m_timeframe;
    CLogger*         m_logger;
    CMarketData*     m_marketData;
    CDateTimeUtils*  m_dateTimeUtils;
    CArrayUtils*     m_arrayUtils;
    
    // Tick buffers
    STickData        m_currentTick;
    STickData        m_previousTick;
    STickData        m_tickBuffer[];      // Dynamic array for tick history
    STickData        m_sessionTicks[];    // Ticks for current session
    int              m_maxBufferSize;
    int              m_maxSessionSize;
    int              m_currentBufferIndex;
    int              m_sessionTickIndex;
    
    // Statistics and analytics
    STickStats       m_stats;
    STickVelocity    m_velocity;
    SOrderFlowImbalance m_imbalance;
    datetime         m_sessionStart;
    datetime         m_lastStatsUpdate;
    double           m_priceStep;
    double           m_pointValue;
    
    // Volume profile
    SVolumeLevel     m_volumeLevels[];
    int              m_numPriceLevels;
    double           m_minPrice;
    double           m_maxPrice;
    bool             m_collectVolumeProfile;
    
    // Flags and configuration
    bool             m_initialized;
    bool             m_enableRealTimeStats;
    bool             m_enableVelocityTracking;
    bool             m_enableOrderFlowAnalysis;
    int              m_statsUpdateInterval; // Seconds between stats updates
    
    // Internal counters
    int              m_ticksSinceLastUpdate;
    long             m_lastUpdateTimeMs;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CTickProcessor(string symbol, ENUM_TIMEFRAMES timeframe = PERIOD_M1);
    ~CTickProcessor();
    
    //+------------------------------------------------------------------+
    //| Initialization methods                                           |
    //+------------------------------------------------------------------+
    bool Initialize(int bufferSize = 10000, int sessionSize = 5000);
    void Deinitialize();
    void Refresh();
    
    //+------------------------------------------------------------------+
    //| Core tick processing methods                                     |
    //+------------------------------------------------------------------+
    bool ProcessNewTick();
    bool ProcessNewTick(const MqlTick &tick);
    bool ProcessNewTick(const STickData &tick);
    void UpdateTickBuffer(const STickData &tick);
    
    //+------------------------------------------------------------------+
    //| Data access methods                                              |
    //+------------------------------------------------------------------+
    STickData GetCurrentTick() const { return m_currentTick; }
    STickData GetPreviousTick() const { return m_previousTick; }
    STickData GetTickAt(int index) const;
    STickStats GetStatistics() const { return m_stats; }
    STickVelocity GetVelocity() const { return m_velocity; }
    SOrderFlowImbalance GetOrderFlowImbalance() const { return m_imbalance; }
    
    // Get tick history
    bool GetTickHistory(STickData &ticks[], int count = 100, int startIndex = -1);
    bool GetSessionTicks(STickData &ticks[]);
    
    //+------------------------------------------------------------------+
    //| Tick analysis methods                                            |
    //+------------------------------------------------------------------+
    double GetCurrentSpread() const;
    double GetSpreadInPips() const;
    bool IsBidMovingUp() const;
    bool IsAskMovingUp() const;
    bool IsSpreadExpanding() const;
    bool IsSpreadContracting() const;
    
    // Tick volume analysis
    long GetTickVolume() const;
    double GetVolumeDelta() const;
    double GetVolumeRatio(int period = 20) const;
    
    // Price analysis
    double GetPriceChange() const;
    double GetBidChange() const;
    double GetAskChange() const;
    double GetVolatility(int period = 100) const;
    double GetAverageTrueRange(int period = 14) const;
    
    //+------------------------------------------------------------------+
    //| Volume profile methods                                           |
    //+------------------------------------------------------------------+
    void EnableVolumeProfile(bool enable = true);
    void UpdateVolumeProfile();
    bool GetVolumeProfile(SVolumeLevel &levels[], int &levelsCount);
    double GetVolumeWeightedAveragePrice() const;
    double GetHighVolumeNode(double &price1, double &price2, double threshold = 0.7) const;
    double GetPointOfControl() const;
    
    //+------------------------------------------------------------------+
    //| Time-based methods                                               |
    //+------------------------------------------------------------------+
    bool IsNewSession() const;
    bool IsMarketOpen() const;
    bool IsHighActivityPeriod() const;
    double GetTimeSinceLastTick() const; // Returns seconds
    int GetTicksInCurrentMinute() const;
    
    //+------------------------------------------------------------------+
    //| Statistical methods                                              |
    //+------------------------------------------------------------------+
    void ResetStatistics();
    void UpdateStatistics();
    void CalculateVelocity();
    void CalculateOrderFlowImbalance();
    void PrintStatistics() const;
    void SaveStatisticsToFile(string filename);
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetMaxBufferSize(int size);
    void SetMaxSessionSize(int size);
    void EnableRealTimeStats(bool enable);
    void EnableVelocityTracking(bool enable);
    void EnableOrderFlowAnalysis(bool enable);
    void SetStatsUpdateInterval(int seconds);
    
    //+------------------------------------------------------------------+
    //| Utility methods                                                  |
    //+------------------------------------------------------------------+
    int SaveTickHistoryToFile(string filename, int maxTicks = 1000);
    int LoadTickHistoryFromFile(string filename);
    void ExportToCSV(string filename, int maxTicks = 1000);
    
    //+------------------------------------------------------------------+
    //| State checking methods                                           |
    //+------------------------------------------------------------------+
    bool IsInitialized() const { return m_initialized; }
    bool IsDataValid() const;
    int GetBufferUsage() const { return m_currentBufferIndex; }
    int GetSessionTickCount() const { return m_sessionTickIndex; }
    
private:
    //+------------------------------------------------------------------+
    //| Helper methods                                                   |
    //+------------------------------------------------------------------+
    void InitializeTickBuffer();
    void InitializeSessionBuffer();
    void InitializeVolumeProfile();
    void UpdatePriceLevels(const STickData &tick);
    double CalculateTickPointValue() const;
    bool IsValidTick(const STickData &tick) const;
    bool IsValidTick(const MqlTick &tick) const;
    void CleanupVolumeProfile();
    void ShiftTickBuffer();
    
    //+------------------------------------------------------------------+
    //| MT5 specific methods                                             |
    //+------------------------------------------------------------------+
    bool GetCurrentMqlTick(MqlTick &tick);
    double SymbolPoint() const;
    int SymbolDigits() const;
    string SymbolName() const { return m_symbol; }
    
    //+------------------------------------------------------------------+
    //| Internal calculation methods                                     |
    //+------------------------------------------------------------------+
    void UpdateSpreadStatistics();
    void UpdateVolumeStatistics(const STickData &tick);
    void UpdateVelocityStatistics();
    void UpdateImbalanceStatistics(const STickData &tick);
    double CalculateStandardDeviation(double &prices[], int period);
    double CalculateTrueRange(int index) const;
    
    //+------------------------------------------------------------------+
    //| Logging methods                                                  |
    //+------------------------------------------------------------------+
    void LogError(string message);
    void LogInfo(string message);
    void LogDebug(string message);
};

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CTickProcessor::CTickProcessor(string symbol, ENUM_TIMEFRAMES timeframe) :
    m_symbol(symbol),
    m_timeframe(timeframe),
    m_logger(NULL),
    m_marketData(NULL),
    m_dateTimeUtils(NULL),
    m_arrayUtils(NULL),
    m_maxBufferSize(10000),
    m_maxSessionSize(5000),
    m_currentBufferIndex(0),
    m_sessionTickIndex(0),
    m_initialized(false),
    m_collectVolumeProfile(false),
    m_enableRealTimeStats(true),
    m_enableVelocityTracking(true),
    m_enableOrderFlowAnalysis(true),
    m_statsUpdateInterval(60),
    m_priceStep(0),
    m_pointValue(0),
    m_minPrice(0),
    m_maxPrice(0),
    m_numPriceLevels(200),
    m_ticksSinceLastUpdate(0),
    m_lastUpdateTimeMs(0)
{
    // Initialize structures
    ResetStatistics();
    
    // Initialize velocity tracking
    m_velocity.ticks_per_second = 0;
    m_velocity.avg_ticks_per_second = 0;
    m_velocity.max_ticks_per_second = 0;
    m_velocity.last_tick_time = 0;
    m_velocity.time_since_last = 0;
    
    // Initialize order flow imbalance
    m_imbalance.imbalance = 0;
    m_imbalance.cumulative_imbalance = 0;
    m_imbalance.total_bid_volume = 0;
    m_imbalance.total_ask_volume = 0;
    m_imbalance.price_pressure = 0;
    
    // Set session start
    m_sessionStart = TimeCurrent();
    m_lastStatsUpdate = TimeCurrent();
}

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CTickProcessor::~CTickProcessor() {
    Deinitialize();
}

//+------------------------------------------------------------------+
//| Initialize the tick processor                                    |
//+------------------------------------------------------------------+
bool CTickProcessor::Initialize(int bufferSize = 10000, int sessionSize = 5000) {
    if(m_initialized) {
        LogInfo("Already initialized");
        return true;
    }
    
    // Set buffer sizes
    m_maxBufferSize = bufferSize;
    m_maxSessionSize = sessionSize;
    
    // Initialize global utilities
    if(GlobalLogger == NULL) {
        LogError("Global logger not initialized");
        return false;
    }
    m_logger = GlobalLogger;
    
    // Initialize date/time utils
    InitializeGlobalDateTimeUtils();
    m_dateTimeUtils = GlobalDateTimeUtils;
    
    // Initialize array utils
    InitializeGlobalArrayUtils();
    m_arrayUtils = GlobalArrayUtils;
    
    // Check if symbol exists
    if(!SymbolInfoInteger(m_symbol, SYMBOL_SELECT)) {
        LogError("Symbol " + m_symbol + " not found");
        return false;
    }
    
    // Initialize market data
    m_marketData = new CMarketData(m_symbol, m_timeframe);
    if(!m_marketData.Initialize()) {
        LogError("Failed to initialize MarketData for " + m_symbol);
        delete m_marketData;
        m_marketData = NULL;
        return false;
    }
    
    // Get symbol properties
    m_priceStep = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_SIZE);
    if(m_priceStep <= 0) {
        m_priceStep = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
    }
    m_pointValue = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_VALUE);
    
    // Initialize tick buffers
    InitializeTickBuffer();
    InitializeSessionBuffer();
    
    // Initialize volume profile if enabled
    if(m_collectVolumeProfile) {
        InitializeVolumeProfile();
    }
    
    // Get initial tick
    MqlTick lastTick;
    if(SymbolInfoTick(m_symbol, lastTick)) {
        m_currentTick = STickData(lastTick);
        m_previousTick = m_currentTick;
        
        // Update statistics with initial tick
        UpdateStatistics();
    }
    
    m_initialized = true;
    LogInfo("Initialized for " + m_symbol + " with buffer size: " + IntegerToString(m_maxBufferSize));
    
    return true;
}

//+------------------------------------------------------------------+
//| Deinitialize                                                     |
//+------------------------------------------------------------------+
void CTickProcessor::Deinitialize() {
    if(!m_initialized) return;
    
    // Save statistics if needed
    if(m_logger != NULL) {
        LogInfo("Deinitializing TickProcessor for " + m_symbol);
    }
    
    // Clean up market data
    if(m_marketData != NULL) {
        m_marketData.Deinitialize();
        delete m_marketData;
        m_marketData = NULL;
    }
    
    // Clean up arrays
    ArrayFree(m_tickBuffer);
    ArrayFree(m_sessionTicks);
    ArrayFree(m_volumeLevels);
    
    m_initialized = false;
}

//+------------------------------------------------------------------+
//| Initialize tick buffer                                           |
//+------------------------------------------------------------------+
void CTickProcessor::InitializeTickBuffer() {
    if(ArrayResize(m_tickBuffer, m_maxBufferSize) < 0) {
        LogError("Failed to allocate tick buffer of size: " + IntegerToString(m_maxBufferSize));
    } else {
        LogDebug("Tick buffer initialized with size: " + IntegerToString(m_maxBufferSize));
    }
    m_currentBufferIndex = 0;
}

//+------------------------------------------------------------------+
//| Initialize session buffer                                        |
//+------------------------------------------------------------------+
void CTickProcessor::InitializeSessionBuffer() {
    if(ArrayResize(m_sessionTicks, m_maxSessionSize) < 0) {
        LogError("Failed to allocate session buffer of size: " + IntegerToString(m_maxSessionSize));
    } else {
        LogDebug("Session buffer initialized with size: " + IntegerToString(m_maxSessionSize));
    }
    m_sessionTickIndex = 0;
}

//+------------------------------------------------------------------+
//| Initialize volume profile                                        |
//+------------------------------------------------------------------+
void CTickProcessor::InitializeVolumeProfile() {
    if(ArrayResize(m_volumeLevels, m_numPriceLevels) < 0) {
        LogError("Failed to allocate volume levels of size: " + IntegerToString(m_numPriceLevels));
        m_collectVolumeProfile = false;
        return;
    }
    
    // Initialize all volume levels
    for(int i = 0; i < m_numPriceLevels; i++) {
        m_volumeLevels[i].price = 0;
        m_volumeLevels[i].volume = 0;
        m_volumeLevels[i].bid_volume = 0;
        m_volumeLevels[i].ask_volume = 0;
        m_volumeLevels[i].first_time = 0;
        m_volumeLevels[i].last_time = 0;
        m_volumeLevels[i].tick_count = 0;
    }
    
    LogDebug("Volume profile initialized with " + IntegerToString(m_numPriceLevels) + " price levels");
}

//+------------------------------------------------------------------+
//| Refresh market data                                              |
//+------------------------------------------------------------------+
void CTickProcessor::Refresh() {
    if(!m_initialized) return;
    
    // Process new tick if available
    ProcessNewTick();
    
    // Update statistics periodically
    if(m_enableRealTimeStats && (TimeCurrent() - m_lastStatsUpdate) >= m_statsUpdateInterval) {
        UpdateStatistics();
        m_lastStatsUpdate = TimeCurrent();
    }
}

//+------------------------------------------------------------------+
//| Process new tick from OnTick()                                   |
//+------------------------------------------------------------------+
bool CTickProcessor::ProcessNewTick() {
    if(!m_initialized) {
        LogError("Not initialized");
        return false;
    }
    
    MqlTick currentTick;
    if(!GetCurrentMqlTick(currentTick)) {
        return false;
    }
    
    return ProcessNewTick(currentTick);
}

//+------------------------------------------------------------------+
//| Process new tick with MqlTick data                               |
//+------------------------------------------------------------------+
bool CTickProcessor::ProcessNewTick(const MqlTick &tick) {
    if(!IsValidTick(tick)) {
        LogDebug("Invalid tick received");
        return false;
    }
    
    STickData newTick(tick);
    return ProcessNewTick(newTick);
}

//+------------------------------------------------------------------+
//| Process new tick with STickData                                  |
//+------------------------------------------------------------------+
bool CTickProcessor::ProcessNewTick(const STickData &tick) {
    if(!m_initialized) {
        return false;
    }
    
    // Check if this is a valid tick (price changed)
    if(!IsValidTick(tick)) {
        return false;
    }
    
    // Store previous tick
    m_previousTick = m_currentTick;
    
    // Update current tick
    m_currentTick = tick;
    
    // Update tick buffer
    UpdateTickBuffer(m_currentTick);
    
    // Update session ticks
    if(m_sessionTickIndex < m_maxSessionSize) {
        m_sessionTicks[m_sessionTickIndex++] = m_currentTick;
    } else {
        // Shift session buffer if full
        for(int i = 1; i < m_maxSessionSize; i++) {
            m_sessionTicks[i-1] = m_sessionTicks[i];
        }
        m_sessionTicks[m_maxSessionSize-1] = m_currentTick;
    }
    
    // Update statistics
    m_stats.total_ticks++;
    m_stats.session_ticks++;
    
    // Update velocity tracking
    if(m_enableVelocityTracking) {
        CalculateVelocity();
    }
    
    // Update order flow imbalance
    if(m_enableOrderFlowAnalysis) {
        CalculateOrderFlowImbalance();
    }
    
    // Update volume profile
    if(m_collectVolumeProfile) {
        UpdateVolumeProfile();
    }
    
    // Increment counter for periodic updates
    m_ticksSinceLastUpdate++;
    
    // Update detailed statistics periodically
    if(m_ticksSinceLastUpdate >= 100) {
        UpdateSpreadStatistics();
        UpdateVolumeStatistics(m_currentTick);
        m_ticksSinceLastUpdate = 0;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Update tick buffer                                               |
//+------------------------------------------------------------------+
void CTickProcessor::UpdateTickBuffer(const STickData &tick) {
    if(m_currentBufferIndex >= m_maxBufferSize) {
        // Buffer is full, shift and add at end
        ShiftTickBuffer();
        m_tickBuffer[m_maxBufferSize-1] = tick;
    } else {
        // Add to next available position
        m_tickBuffer[m_currentBufferIndex] = tick;
        m_currentBufferIndex++;
    }
}

//+------------------------------------------------------------------+
//| Shift tick buffer (ring buffer implementation)                   |
//+------------------------------------------------------------------+
void CTickProcessor::ShiftTickBuffer() {
    // Shift all elements left by one position
    for(int i = 1; i < m_maxBufferSize; i++) {
        m_tickBuffer[i-1] = m_tickBuffer[i];
    }
}

//+------------------------------------------------------------------+
//| Get tick at specific index                                       |
//+------------------------------------------------------------------+
STickData CTickProcessor::GetTickAt(int index) const {
    if(index < 0 || index >= m_currentBufferIndex) {
        STickData empty;
        return empty;
    }
    return m_tickBuffer[index];
}

//+------------------------------------------------------------------+
//| Get tick history                                                 |
//+------------------------------------------------------------------+
bool CTickProcessor::GetTickHistory(STickData &ticks[], int count = 100, int startIndex = -1) {
    if(count <= 0 || m_currentBufferIndex == 0) {
        return false;
    }
    
    // If startIndex is -1, start from most recent
    if(startIndex == -1) {
        startIndex = m_currentBufferIndex - 1;
    }
    
    // Ensure startIndex is valid
    if(startIndex < 0 || startIndex >= m_currentBufferIndex) {
        return false;
    }
    
    // Determine actual count to copy
    int actualCount = MathMin(count, startIndex + 1);
    
    // Resize destination array
    if(ArrayResize(ticks, actualCount) != actualCount) {
        return false;
    }
    
    // Copy ticks in reverse chronological order (newest first)
    for(int i = 0; i < actualCount; i++) {
        ticks[i] = m_tickBuffer[startIndex - i];
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Get current spread                                               |
//+------------------------------------------------------------------+
double CTickProcessor::GetCurrentSpread() const {
    return m_currentTick.spread;
}

//+------------------------------------------------------------------+
//| Get spread in pips                                               |
//+------------------------------------------------------------------+
double CTickProcessor::GetSpreadInPips() const {
    double spread = GetCurrentSpread();
    double point = SymbolPoint();
    
    if(point > 0) {
        return spread / point;
    }
    
    return 0;
}

//+------------------------------------------------------------------+
//| Check if bid is moving up                                        |
//+------------------------------------------------------------------+
bool CTickProcessor::IsBidMovingUp() const {
    return m_currentTick.bid > m_previousTick.bid;
}

//+------------------------------------------------------------------+
//| Check if ask is moving up                                        |
//+------------------------------------------------------------------+
bool CTickProcessor::IsAskMovingUp() const {
    return m_currentTick.ask > m_previousTick.ask;
}

//+------------------------------------------------------------------+
//| Check if spread is expanding                                     |
//+------------------------------------------------------------------+
bool CTickProcessor::IsSpreadExpanding() const {
    return m_currentTick.spread > m_previousTick.spread;
}

//+------------------------------------------------------------------+
//| Check if spread is contracting                                   |
//+------------------------------------------------------------------+
bool CTickProcessor::IsSpreadContracting() const {
    return m_currentTick.spread < m_previousTick.spread;
}

//+------------------------------------------------------------------+
//| Get tick volume                                                  |
//+------------------------------------------------------------------+
long CTickProcessor::GetTickVolume() const {
    if(m_currentTick.volume > m_previousTick.volume) {
        return m_currentTick.volume - m_previousTick.volume;
    }
    return m_currentTick.volume;
}

//+------------------------------------------------------------------+
//| Get volume delta                                                 |
//+------------------------------------------------------------------+
double CTickProcessor::GetVolumeDelta() const {
    return (double)(m_currentTick.volume - m_previousTick.volume);
}

//+------------------------------------------------------------------+
//| Get price change from previous tick                              |
//+------------------------------------------------------------------+
double CTickProcessor::GetPriceChange() const {
    return m_currentTick.last - m_previousTick.last;
}

//+------------------------------------------------------------------+
//| Get bid change                                                   |
//+------------------------------------------------------------------+
double CTickProcessor::GetBidChange() const {
    return m_currentTick.bid - m_previousTick.bid;
}

//+------------------------------------------------------------------+
//| Get ask change                                                   |
//+------------------------------------------------------------------+
double CTickProcessor::GetAskChange() const {
    return m_currentTick.ask - m_previousTick.ask;
}

//+------------------------------------------------------------------+
//| Calculate volatility                                             |
//+------------------------------------------------------------------+
double CTickProcessor::GetVolatility(int period = 100) const {
    if(period <= 0 || m_currentBufferIndex < period) {
        return 0;
    }
    
    // Collect price changes
    double priceChanges[];
    ArrayResize(priceChanges, MathMin(period, m_currentBufferIndex - 1));
    
    int count = 0;
    for(int i = 1; i < MathMin(period + 1, m_currentBufferIndex); i++) {
        if(m_tickBuffer[i].last > 0 && m_tickBuffer[i-1].last > 0) {
            priceChanges[count++] = MathLog(m_tickBuffer[i].last / m_tickBuffer[i-1].last);
        }
    }
    
    if(count < 2) return 0;
    
    // Calculate standard deviation
    double sum = 0;
    double sumSq = 0;
    
    for(int i = 0; i < count; i++) {
        sum += priceChanges[i];
        sumSq += priceChanges[i] * priceChanges[i];
    }
    
    double mean = sum / count;
    double variance = (sumSq / count) - (mean * mean);
    
    return MathSqrt(variance) * MathSqrt(252); // Annualized volatility
}

//+------------------------------------------------------------------+
//| Enable volume profile                                            |
//+------------------------------------------------------------------+
void CTickProcessor::EnableVolumeProfile(bool enable) {
    m_collectVolumeProfile = enable;
    if(enable && !m_initialized) {
        LogInfo("Volume profile will be enabled after initialization");
    } else if(enable && m_initialized) {
        InitializeVolumeProfile();
    }
}

//+------------------------------------------------------------------+
//| Update volume profile                                            |
//+------------------------------------------------------------------+
void CTickProcessor::UpdateVolumeProfile() {
    if(!m_collectVolumeProfile) return;
    
    UpdatePriceLevels(m_currentTick);
}

//+------------------------------------------------------------------+
//| Update price levels for volume profile                           |
//+------------------------------------------------------------------+
void CTickProcessor::UpdatePriceLevels(const STickData &tick) {
    // Update min/max price range
    if(m_minPrice == 0 || tick.bid < m_minPrice) m_minPrice = tick.bid;
    if(m_maxPrice == 0 || tick.ask > m_maxPrice) m_maxPrice = tick.ask;
    
    // Calculate price range and level size
    double priceRange = m_maxPrice - m_minPrice;
    if(priceRange <= 0 || m_numPriceLevels <= 0) return;
    
    double levelSize = priceRange / m_numPriceLevels;
    if(levelSize <= 0) return;
    
    // Find appropriate level for current price
    int bidLevel = (int)((tick.bid - m_minPrice) / levelSize);
    int askLevel = (int)((tick.ask - m_minPrice) / levelSize);
    
    // Ensure levels are within bounds
    bidLevel = MathMin(MathMax(bidLevel, 0), m_numPriceLevels - 1);
    askLevel = MathMin(MathMax(askLevel, 0), m_numPriceLevels - 1);
    
    // Update bid level
    m_volumeLevels[bidLevel].price = m_minPrice + (bidLevel * levelSize) + (levelSize / 2);
    m_volumeLevels[bidLevel].volume += tick.volume;
    m_volumeLevels[bidLevel].bid_volume += tick.volume;
    m_volumeLevels[bidLevel].tick_count++;
    
    if(m_volumeLevels[bidLevel].first_time == 0) {
        m_volumeLevels[bidLevel].first_time = tick.time;
    }
    m_volumeLevels[bidLevel].last_time = tick.time;
    
    // Update ask level (if different from bid level)
    if(askLevel != bidLevel) {
        m_volumeLevels[askLevel].price = m_minPrice + (askLevel * levelSize) + (levelSize / 2);
        m_volumeLevels[askLevel].volume += tick.volume;
        m_volumeLevels[askLevel].ask_volume += tick.volume;
        m_volumeLevels[askLevel].tick_count++;
        
        if(m_volumeLevels[askLevel].first_time == 0) {
            m_volumeLevels[askLevel].first_time = tick.time;
        }
        m_volumeLevels[askLevel].last_time = tick.time;
    }
}

//+------------------------------------------------------------------+
//| Get volume profile data                                          |
//+------------------------------------------------------------------+
bool CTickProcessor::GetVolumeProfile(SVolumeLevel &levels[], int &levelsCount) {
    if(!m_collectVolumeProfile || m_numPriceLevels == 0) {
        levelsCount = 0;
        return false;
    }
    
    // Count non-zero levels
    int count = 0;
    for(int i = 0; i < m_numPriceLevels; i++) {
        if(m_volumeLevels[i].volume > 0) {
            count++;
        }
    }
    
    if(count == 0) {
        levelsCount = 0;
        return false;
    }
    
    // Resize output array
    if(ArrayResize(levels, count) != count) {
        levelsCount = 0;
        return false;
    }
    
    // Copy non-zero levels
    int index = 0;
    for(int i = 0; i < m_numPriceLevels; i++) {
        if(m_volumeLevels[i].volume > 0) {
            levels[index++] = m_volumeLevels[i];
        }
    }
    
    levelsCount = count;
    return true;
}

//+------------------------------------------------------------------+
//| Get Volume Weighted Average Price                                |
//+------------------------------------------------------------------+
double CTickProcessor::GetVolumeWeightedAveragePrice() const {
    if(!m_collectVolumeProfile) return 0;
    
    double totalVolumeValue = 0;
    long totalVolume = 0;
    
    for(int i = 0; i < m_numPriceLevels; i++) {
        if(m_volumeLevels[i].volume > 0) {
            totalVolumeValue += m_volumeLevels[i].price * m_volumeLevels[i].volume;
            totalVolume += m_volumeLevels[i].volume;
        }
    }
    
    if(totalVolume > 0) {
        return totalVolumeValue / totalVolume;
    }
    
    return 0;
}

//+------------------------------------------------------------------+
//| Get Point of Control (highest volume node)                       |
//+------------------------------------------------------------------+
double CTickProcessor::GetPointOfControl() const {
    if(!m_collectVolumeProfile) return 0;
    
    long maxVolume = 0;
    double pocPrice = 0;
    
    for(int i = 0; i < m_numPriceLevels; i++) {
        if(m_volumeLevels[i].volume > maxVolume) {
            maxVolume = m_volumeLevels[i].volume;
            pocPrice = m_volumeLevels[i].price;
        }
    }
    
    return pocPrice;
}

//+------------------------------------------------------------------+
//| Check if new session has started                                 |
//+------------------------------------------------------------------+
bool CTickProcessor::IsNewSession() const {
    if(m_dateTimeUtils == NULL) return false;
    
    MqlDateTime currentDt, sessionDt;
    TimeToStruct(TimeCurrent(), currentDt);
    TimeToStruct(m_sessionStart, sessionDt);
    
    return (currentDt.day != sessionDt.day);
}

//+------------------------------------------------------------------+
//| Check if market is open                                          |
//+------------------------------------------------------------------+
bool CTickProcessor::IsMarketOpen() const {
    if(m_marketData == NULL) return false;
    return m_marketData.IsMarketOpen();
}

//+------------------------------------------------------------------+
//| Calculate velocity statistics                                    |
//+------------------------------------------------------------------+
void CTickProcessor::CalculateVelocity() {
    datetime currentTime = TimeCurrent();
    
    if(m_velocity.last_tick_time == 0) {
        m_velocity.last_tick_time = currentTime;
        return;
    }
    
    // Calculate time since last tick in seconds
    double timeDiff = (double)(currentTime - m_velocity.last_tick_time);
    if(timeDiff > 0) {
        m_velocity.ticks_per_second = 1.0 / timeDiff;
        m_velocity.time_since_last = timeDiff * 1000; // Convert to milliseconds
        
        // Update average
        if(m_velocity.avg_ticks_per_second == 0) {
            m_velocity.avg_ticks_per_second = m_velocity.ticks_per_second;
        } else {
            // Exponential moving average
            m_velocity.avg_ticks_per_second = (m_velocity.avg_ticks_per_second * 0.9) + 
                                             (m_velocity.ticks_per_second * 0.1);
        }
        
        // Update max
        if(m_velocity.ticks_per_second > m_velocity.max_ticks_per_second) {
            m_velocity.max_ticks_per_second = m_velocity.ticks_per_second;
        }
    }
    
    m_velocity.last_tick_time = currentTime;
}

//+------------------------------------------------------------------+
//| Calculate order flow imbalance                                   |
//+------------------------------------------------------------------+
void CTickProcessor::CalculateOrderFlowImbalance() {
    // Simple bid/ask volume imbalance calculation
    long totalVolume = m_imbalance.total_bid_volume + m_imbalance.total_ask_volume;
    
    if(totalVolume > 0) {
        // Calculate imbalance (-1 to +1 where negative = more bids, positive = more asks)
        m_imbalance.imbalance = (double)(m_imbalance.total_ask_volume - m_imbalance.total_bid_volume) / totalVolume;
        
        // Update cumulative imbalance
        m_imbalance.cumulative_imbalance += m_imbalance.imbalance;
        
        // Simple price pressure indicator
        if(m_imbalance.imbalance > 0.2) {
            m_imbalance.price_pressure = 1; // Buying pressure
        } else if(m_imbalance.imbalance < -0.2) {
            m_imbalance.price_pressure = -1; // Selling pressure
        } else {
            m_imbalance.price_pressure = 0; // Balanced
        }
    }
    
    // Update volume counts from current tick
    if(m_currentTick.volume > 0) {
        if(m_currentTick.last >= m_currentTick.ask) {
            // Price at or above ask suggests buying pressure
            m_imbalance.total_ask_volume += m_currentTick.volume;
        } else if(m_currentTick.last <= m_currentTick.bid) {
            // Price at or below bid suggests selling pressure
            m_imbalance.total_bid_volume += m_currentTick.volume;
        }
    }
}

//+------------------------------------------------------------------+
//| Reset statistics                                                 |
//+------------------------------------------------------------------+
void CTickProcessor::ResetStatistics() {
    m_stats.Reset();
    m_sessionStart = TimeCurrent();
    m_ticksSinceLastUpdate = 0;
}

//+------------------------------------------------------------------+
//| Update statistics                                                |
//+------------------------------------------------------------------+
void CTickProcessor::UpdateStatistics() {
    // Update spread statistics
    UpdateSpreadStatistics();
    
    // Update velocity
    if(m_enableVelocityTracking) {
        CalculateVelocity();
    }
    
    // Update order flow
    if(m_enableOrderFlowAnalysis) {
        CalculateOrderFlowImbalance();
    }
    
    // Calculate volatility
    m_stats.volatility = GetVolatility(100);
}

//+------------------------------------------------------------------+
//| Update spread statistics                                         |
//+------------------------------------------------------------------+
void CTickProcessor::UpdateSpreadStatistics() {
    double currentSpread = GetSpreadInPips();
    
    if(m_stats.avg_spread == 0) {
        m_stats.avg_spread = currentSpread;
        m_stats.min_spread = currentSpread;
        m_stats.max_spread = currentSpread;
    } else {
        // Exponential moving average
        m_stats.avg_spread = (m_stats.avg_spread * 0.95) + (currentSpread * 0.05);
        m_stats.min_spread = MathMin(m_stats.min_spread, currentSpread);
        m_stats.max_spread = MathMax(m_stats.max_spread, currentSpread);
    }
}

//+------------------------------------------------------------------+
//| Update volume statistics                                         |
//+------------------------------------------------------------------+
void CTickProcessor::UpdateVolumeStatistics(const STickData &tick) {
    m_stats.total_volume += tick.volume;
    
    // Update bid/ask ratio
    if(m_imbalance.total_bid_volume + m_imbalance.total_ask_volume > 0) {
        m_stats.bid_ask_ratio = (double)m_imbalance.total_bid_volume / 
                                 (m_imbalance.total_bid_volume + m_imbalance.total_ask_volume);
    }
}

//+------------------------------------------------------------------+
//| Print statistics                                                 |
//+------------------------------------------------------------------+
void CTickProcessor::PrintStatistics() const {
    if(m_logger == NULL) return;
    
    string stats = StringFormat(
        "Tick Statistics for %s:\n" +
        "Total Ticks: %d | Session Ticks: %d\n" +
        "Spread: Current=%.2f pips, Avg=%.2f, Min=%.2f, Max=%.2f\n" +
        "Total Volume: %lld | Volatility: %.4f\n" +
        "Tick Velocity: Current=%.2f/s, Avg=%.2f/s, Max=%.2f/s\n" +
        "Order Flow: Imbalance=%.3f, Cumulative=%.3f, Pressure=%d",
        m_symbol,
        m_stats.total_ticks,
        m_stats.session_ticks,
        GetSpreadInPips(),
        m_stats.avg_spread,
        m_stats.min_spread,
        m_stats.max_spread,
        m_stats.total_volume,
        m_stats.volatility,
        m_velocity.ticks_per_second,
        m_velocity.avg_ticks_per_second,
        m_velocity.max_ticks_per_second,
        m_imbalance.imbalance,
        m_imbalance.cumulative_imbalance,
        (int)m_imbalance.price_pressure
    );
    
    m_logger.Info(stats, "TickProcessor");
}

//+------------------------------------------------------------------+
//| Set maximum buffer size                                          |
//+------------------------------------------------------------------+
void CTickProcessor::SetMaxBufferSize(int size) {
    if(size > 0 && size != m_maxBufferSize) {
        m_maxBufferSize = size;
        if(m_initialized) {
            // Reinitialize buffer with new size
            ArrayFree(m_tickBuffer);
            InitializeTickBuffer();
            LogInfo("Buffer size changed to: " + IntegerToString(size));
        }
    }
}

//+------------------------------------------------------------------+
//| Set maximum session size                                         |
//+------------------------------------------------------------------+
void CTickProcessor::SetMaxSessionSize(int size) {
    if(size > 0 && size != m_maxSessionSize) {
        m_maxSessionSize = size;
        if(m_initialized) {
            // Reinitialize session buffer with new size
            ArrayFree(m_sessionTicks);
            InitializeSessionBuffer();
            LogInfo("Session buffer size changed to: " + IntegerToString(size));
        }
    }
}

//+------------------------------------------------------------------+
//| Enable real-time statistics                                      |
//+------------------------------------------------------------------+
void CTickProcessor::EnableRealTimeStats(bool enable) {
    m_enableRealTimeStats = enable;
    LogInfo("Real-time statistics " + (enable ? "enabled" : "disabled"));
}

//+------------------------------------------------------------------+
//| Enable velocity tracking                                         |
//+------------------------------------------------------------------+
void CTickProcessor::EnableVelocityTracking(bool enable) {
    m_enableVelocityTracking = enable;
    LogInfo("Velocity tracking " + (enable ? "enabled" : "disabled"));
}

//+------------------------------------------------------------------+
//| Enable order flow analysis                                       |
//+------------------------------------------------------------------+
void CTickProcessor::EnableOrderFlowAnalysis(bool enable) {
    m_enableOrderFlowAnalysis = enable;
    LogInfo("Order flow analysis " + (enable ? "enabled" : "disabled"));
}

//+------------------------------------------------------------------+
//| Set statistics update interval                                   |
//+------------------------------------------------------------------+
void CTickProcessor::SetStatsUpdateInterval(int seconds) {
    if(seconds > 0) {
        m_statsUpdateInterval = seconds;
        LogInfo("Stats update interval set to " + IntegerToString(seconds) + " seconds");
    }
}

//+------------------------------------------------------------------+
//| Get current MqlTick                                              |
//+------------------------------------------------------------------+
bool CTickProcessor::GetCurrentMqlTick(MqlTick &tick) {
    return SymbolInfoTick(m_symbol, tick);
}

//+------------------------------------------------------------------+
//| Get symbol point value                                           |
//+------------------------------------------------------------------+
double CTickProcessor::SymbolPoint() const {
    return SymbolInfoDouble(m_symbol, SYMBOL_POINT);
}

//+------------------------------------------------------------------+
//| Get symbol digits                                                |
//+------------------------------------------------------------------+
int CTickProcessor::SymbolDigits() const {
    return (int)SymbolInfoInteger(m_symbol, SYMBOL_DIGITS);
}

//+------------------------------------------------------------------+
//| Check if tick is valid                                           |
//+------------------------------------------------------------------+
bool CTickProcessor::IsValidTick(const STickData &tick) const {
    return (tick.bid > 0 && tick.ask > 0 && tick.time > 0 && tick.ask > tick.bid);
}

//+------------------------------------------------------------------+
//| Check if MqlTick is valid                                        |
//+------------------------------------------------------------------+
bool CTickProcessor::IsValidTick(const MqlTick &tick) const {
    return (tick.bid > 0 && tick.ask > 0 && tick.time > 0 && tick.ask > tick.bid);
}

//+------------------------------------------------------------------+
//| Check if data is valid                                           |
//+------------------------------------------------------------------+
bool CTickProcessor::IsDataValid() const {
    return (m_initialized && m_currentTick.bid > 0 && m_currentTick.ask > 0);
}

//+------------------------------------------------------------------+
//| Log error message                                                |
//+------------------------------------------------------------------+
void CTickProcessor::LogError(string message) {
    if(m_logger != NULL) {
        m_logger.Error(message, "TickProcessor");
    } else {
        Print("ERROR [TickProcessor]: " + message);
    }
}

//+------------------------------------------------------------------+
//| Log info message                                                 |
//+------------------------------------------------------------------+
void CTickProcessor::LogInfo(string message) {
    if(m_logger != NULL) {
        m_logger.Info(message, "TickProcessor");
    } else {
        Print("INFO [TickProcessor]: " + message);
    }
}

//+------------------------------------------------------------------+
//| Log debug message                                                |
//+------------------------------------------------------------------+
void CTickProcessor::LogDebug(string message) {
    if(m_logger != NULL) {
        m_logger.Debug(message, "TickProcessor");
    }
}

//+------------------------------------------------------------------+
//| Save tick history to file                                        |
//+------------------------------------------------------------------+
int CTickProcessor::SaveTickHistoryToFile(string filename, int maxTicks = 1000) {
    if(!m_initialized || m_currentBufferIndex == 0) {
        return 0;
    }
    
    int ticksToSave = MathMin(maxTicks, m_currentBufferIndex);
    int file_handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
    
    if(file_handle == INVALID_HANDLE) {
        LogError("Cannot open file for writing: " + filename);
        return 0;
    }
    
    // Write header
    FileWrite(file_handle, "Time", "Bid", "Ask", "Last", "Volume", "Spread", "Time_msc");
    
    // Write tick data (newest first)
    int count = 0;
    for(int i = m_currentBufferIndex - 1; i >= MathMax(0, m_currentBufferIndex - ticksToSave); i--) {
        FileWrite(file_handle,
                  TimeToString(m_tickBuffer[i].time, TIME_DATE|TIME_SECONDS),
                  DoubleToString(m_tickBuffer[i].bid, SymbolDigits()),
                  DoubleToString(m_tickBuffer[i].ask, SymbolDigits()),
                  DoubleToString(m_tickBuffer[i].last, SymbolDigits()),
                  IntegerToString(m_tickBuffer[i].volume),
                  DoubleToString(m_tickBuffer[i].spread, SymbolDigits()),
                  IntegerToString(m_tickBuffer[i].time_msc));
        count++;
    }
    
    FileClose(file_handle);
    LogInfo("Saved " + IntegerToString(count) + " ticks to " + filename);
    
    return count;
}

//+------------------------------------------------------------------+
//| Export to CSV                                                    |
//+------------------------------------------------------------------+
void CTickProcessor::ExportToCSV(string filename, int maxTicks = 1000) {
    SaveTickHistoryToFile(filename, maxTicks);
}

//+------------------------------------------------------------------+
//| Calculate True Range                                             |
//+------------------------------------------------------------------+
double CTickProcessor::CalculateTrueRange(int index) const {
    if(index <= 0 || index >= m_currentBufferIndex) return 0;
    
    double high = MathMax(m_tickBuffer[index].bid, m_tickBuffer[index-1].bid);
    double low = MathMin(m_tickBuffer[index].bid, m_tickBuffer[index-1].bid);
    
    return high - low;
}

//+------------------------------------------------------------------+
//| Get Average True Range                                           |
//+------------------------------------------------------------------+
double CTickProcessor::GetAverageTrueRange(int period = 14) const {
    if(period <= 0 || m_currentBufferIndex < period + 1) {
        return 0;
    }
    
    double sumTR = 0;
    int count = 0;
    
    for(int i = 1; i <= MathMin(period, m_currentBufferIndex - 1); i++) {
        double tr = CalculateTrueRange(i);
        if(tr > 0) {
            sumTR += tr;
            count++;
        }
    }
    
    if(count > 0) {
        return sumTR / count;
    }
    
    return 0;
}

//+------------------------------------------------------------------+
//| Calculate standard deviation                                     |
//+------------------------------------------------------------------+
double CTickProcessor::CalculateStandardDeviation(double &prices[], int period) {
    if(ArraySize(prices) < period) return 0;
    
    double sum = 0;
    for(int i = 0; i < period; i++) {
        sum += prices[i];
    }
    
    double mean = sum / period;
    double variance = 0;
    
    for(int i = 0; i < period; i++) {
        double diff = prices[i] - mean;
        variance += diff * diff;
    }
    
    variance /= period;
    return MathSqrt(variance);
}

//+------------------------------------------------------------------+
//| Get session ticks                                                |
//+------------------------------------------------------------------+
bool CTickProcessor::GetSessionTicks(STickData &ticks[]) {
    if(m_sessionTickIndex == 0) {
        return false;
    }
    
    if(ArrayResize(ticks, m_sessionTickIndex) != m_sessionTickIndex) {
        return false;
    }
    
    for(int i = 0; i < m_sessionTickIndex; i++) {
        ticks[i] = m_sessionTicks[i];
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Get time since last tick                                         |
//+------------------------------------------------------------------+
double CTickProcessor::GetTimeSinceLastTick() const {
    return (double)(TimeCurrent() - m_currentTick.time);
}

//+------------------------------------------------------------------+
//| Get ticks in current minute                                      |
//+------------------------------------------------------------------+
int CTickProcessor::GetTicksInCurrentMinute() const {
    if(m_currentBufferIndex == 0) return 0;
    
    datetime currentMinute = m_currentTick.time - (m_currentTick.time % 60);
    int count = 0;
    
    for(int i = m_currentBufferIndex - 1; i >= 0; i--) {
        if(m_tickBuffer[i].time >= currentMinute) {
            count++;
        } else {
            break;
        }
    }
    
    return count;
}

//+------------------------------------------------------------------+
//| Save statistics to file                                          |
//+------------------------------------------------------------------+
void CTickProcessor::SaveStatisticsToFile(string filename) {
    int file_handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
    
    if(file_handle == INVALID_HANDLE) {
        LogError("Cannot open file for writing: " + filename);
        return;
    }
    
    // Write statistics
    FileWrite(file_handle, "Statistic", "Value");
    FileWrite(file_handle, "Symbol", m_symbol);
    FileWrite(file_handle, "Total Ticks", IntegerToString(m_stats.total_ticks));
    FileWrite(file_handle, "Session Ticks", IntegerToString(m_stats.session_ticks));
    FileWrite(file_handle, "Average Spread (pips)", DoubleToString(m_stats.avg_spread, 2));
    FileWrite(file_handle, "Min Spread (pips)", DoubleToString(m_stats.min_spread, 2));
    FileWrite(file_handle, "Max Spread (pips)", DoubleToString(m_stats.max_spread, 2));
    FileWrite(file_handle, "Total Volume", IntegerToString(m_stats.total_volume));
    FileWrite(file_handle, "Volatility", DoubleToString(m_stats.volatility, 4));
    FileWrite(file_handle, "Avg Tick Speed (tps)", DoubleToString(m_velocity.avg_ticks_per_second, 2));
    FileWrite(file_handle, "Max Tick Speed (tps)", DoubleToString(m_velocity.max_ticks_per_second, 2));
    FileWrite(file_handle, "Order Flow Imbalance", DoubleToString(m_imbalance.imbalance, 3));
    
    FileClose(file_handle);
    LogInfo("Statistics saved to " + filename);
}

//+------------------------------------------------------------------+
//| Get volume ratio                                                 |
//+------------------------------------------------------------------+
double CTickProcessor::GetVolumeRatio(int period = 20) const {
    if(period <= 0 || m_currentBufferIndex < period) {
        return 0;
    }
    
    long sumVolume = 0;
    int count = 0;
    
    for(int i = 0; i < MathMin(period, m_currentBufferIndex); i++) {
        sumVolume += m_tickBuffer[i].volume;
        count++;
    }
    
    if(count > 0 && sumVolume > 0) {
        double avgVolume = (double)sumVolume / count;
        return (double)m_currentTick.volume / avgVolume;
    }
    
    return 0;
}

//+------------------------------------------------------------------+
//| Check if high activity period                                    |
//+------------------------------------------------------------------+
bool CTickProcessor::IsHighActivityPeriod() const {
    // Simple check: if current tick rate is above average
    return (m_velocity.ticks_per_second > m_velocity.avg_ticks_per_second * 1.5);
}

//+------------------------------------------------------------------+
//| Get high volume node                                             |
//+------------------------------------------------------------------+
double CTickProcessor::GetHighVolumeNode(double &price1, double &price2, double threshold = 0.7) const {
    if(!m_collectVolumeProfile) return 0;
    
    // Find maximum volume
    long maxVolume = 0;
    for(int i = 0; i < m_numPriceLevels; i++) {
        if(m_volumeLevels[i].volume > maxVolume) {
            maxVolume = m_volumeLevels[i].volume;
        }
    }
    
    if(maxVolume == 0) return 0;
    
    // Find nodes with volume above threshold
    double nodes[];
    int nodeCount = 0;
    
    for(int i = 0; i < m_numPriceLevels; i++) {
        if(m_volumeLevels[i].volume >= maxVolume * threshold) {
            ArrayResize(nodes, nodeCount + 1);
            nodes[nodeCount++] = m_volumeLevels[i].price;
        }
    }
    
    if(nodeCount >= 2) {
        price1 = nodes[0];
        price2 = nodes[nodeCount - 1];
        return (price1 + price2) / 2;
    } else if(nodeCount == 1) {
        price1 = price2 = nodes[0];
        return nodes[0];
    }
    
    return 0;
}

//+------------------------------------------------------------------+
//| Cleanup volume profile                                           |
//+------------------------------------------------------------------+
void CTickProcessor::CleanupVolumeProfile() {
    // Reset volume profile data
    for(int i = 0; i < m_numPriceLevels; i++) {
        m_volumeLevels[i].volume = 0;
        m_volumeLevels[i].bid_volume = 0;
        m_volumeLevels[i].ask_volume = 0;
        m_volumeLevels[i].tick_count = 0;
    }
    m_minPrice = 0;
    m_maxPrice = 0;
}

//+------------------------------------------------------------------+
//| Calculate tick point value                                       |
//+------------------------------------------------------------------+
double CTickProcessor::CalculateTickPointValue() const {
    return m_pointValue;
}

//+------------------------------------------------------------------+
//| Load tick history from file                                      |
//+------------------------------------------------------------------+
int CTickProcessor::LoadTickHistoryFromFile(string filename) {
    // Implementation for loading tick history from file
    // This would parse CSV and populate tick buffer
    LogInfo("LoadTickHistoryFromFile not implemented yet");
    return 0;
}

#endif // TICKPROCESSOR_MQH