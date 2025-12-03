//+------------------------------------------------------------------+
//| HistoryManager.mqh - Historical data access and management      |
//+------------------------------------------------------------------+
#ifndef HISTORYMANAGER_MQH
#define HISTORYMANAGER_MQH

#include "MarketData.mqh"

//+------------------------------------------------------------------+
//| Bar data type enumeration                                       |
//+------------------------------------------------------------------+
enum ENUM_HISTORY_DATA_TYPE {
    HIST_DATA_TICKS = 0,     // Tick data
    HIST_DATA_BARS = 1,      // Bar/OHLC data
    HIST_DATA_FXT = 2        // Forex tester data
};

//+------------------------------------------------------------------+
//| Historical data request structure                               |
//+------------------------------------------------------------------+
struct SHistoryRequest {
    string               symbol;
    ENUM_TIMEFRAMES      timeframe;
    datetime             fromDate;
    datetime             toDate;
    int                  count;
    ENUM_HISTORY_DATA_TYPE dataType;  // Type of historical data
};

//+------------------------------------------------------------------+
//| Historical data cache structure                                 |
//+------------------------------------------------------------------+
struct SHistoryCache {
    string               symbol;
    ENUM_TIMEFRAMES      timeframe;
    MqlRates             rates[];
    datetime             cacheTime;
    int                  cacheSize;
    bool                 isLoaded;
    
    // Constructor
    SHistoryCache() : cacheTime(0), cacheSize(0), isLoaded(false) {}
};

//+------------------------------------------------------------------+
//| Data quality metrics                                            |
//+------------------------------------------------------------------+
struct SDataQuality {
    int     totalBars;
    int     missingBars;
    int     duplicateBars;
    int     invalidBars;
    double  completeness;      // Percentage of complete data
    bool    hasGaps;
    int     gapCount;
    string  qualityLevel;      // EXCELLENT, GOOD, FAIR, POOR
};

//+------------------------------------------------------------------+
//| CHistoryManager - Historical data management class              |
//+------------------------------------------------------------------+
class CHistoryManager {
private:
    // Core components
    CLogger*          m_logger;
    
    // Configuration
    string            m_symbol;
    ENUM_TIMEFRAMES   m_primaryTimeframe;
    int               m_maxCacheSize;
    int               m_preloadBars;
    
    // Data caches
    SHistoryCache     m_caches[21];  // One cache per standard timeframe
    int               m_cacheCount;
    
    // Performance metrics
    int               m_totalRequests;
    int               m_cacheHits;
    int               m_cacheMisses;
    ulong             m_lastAccessTime;
    
public:
    // Constructor/Destructor
    CHistoryManager(string symbol = NULL);
    ~CHistoryManager();
    
    // Initialization
    bool Initialize(ENUM_TIMEFRAMES primaryTF = PERIOD_H1, int preloadBars = 1000);
    void Deinitialize();
    
    // Main data access methods
    bool GetRates(ENUM_TIMEFRAMES timeframe, MqlRates &rates[], 
                 int count = 100, int startPos = 0);
    bool GetRatesBetween(ENUM_TIMEFRAMES timeframe, MqlRates &rates[],
                        datetime fromDate, datetime toDate);
    
    bool GetOpenArray(ENUM_TIMEFRAMES timeframe, double &open[], 
                     int count = 100, int startPos = 0);
    bool GetCloseArray(ENUM_TIMEFRAMES timeframe, double &close[], 
                      int count = 100, int startPos = 0);
    
    // Get tick data
    bool GetTicks(MqlTick &ticks[], datetime fromDate, datetime toDate, 
                 uint flags = COPY_TICKS_ALL);
    
    // Time utilities
    datetime GetBarTime(ENUM_TIMEFRAMES timeframe, datetime time);
    
    // Cache management
    bool PreloadData(ENUM_TIMEFRAMES timeframe, int bars);
    bool IsCached(ENUM_TIMEFRAMES timeframe);
    void ClearCache(ENUM_TIMEFRAMES timeframe = PERIOD_CURRENT);
    void ClearAllCaches();
    
    // Utility functions
    static string TimeframeToString(ENUM_TIMEFRAMES timeframe);
    static int GetTimeframeMinutes(ENUM_TIMEFRAMES timeframe);
    
private:
    // Internal cache management
    bool GetCacheData(ENUM_TIMEFRAMES timeframe, SHistoryCache &cache);
    bool LoadToCache(ENUM_TIMEFRAMES timeframe, int bars);
    
    // Helper functions
    int FindCacheIndex(ENUM_TIMEFRAMES timeframe);
    bool ValidateRate(const MqlRates &rate);
    
    // Data loading
    bool LoadRatesFromServer(ENUM_TIMEFRAMES timeframe, MqlRates &rates[],
                            datetime fromDate, datetime toDate);
    bool LoadTicksFromServer(MqlTick &ticks[], datetime fromDate, datetime toDate);
};

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CHistoryManager::CHistoryManager(string symbol) :
    m_symbol(symbol),
    m_primaryTimeframe(PERIOD_H1),
    m_maxCacheSize(10000),
    m_preloadBars(1000),
    m_cacheCount(0),
    m_totalRequests(0),
    m_cacheHits(0),
    m_cacheMisses(0),
    m_lastAccessTime(0),
    m_logger(NULL)
{
    // Initialize cache array
    for(int i = 0; i < 21; i++) {
        m_caches[i].symbol = m_symbol;
        m_caches[i].timeframe = PERIOD_CURRENT;
        m_caches[i].cacheTime = 0;
        m_caches[i].cacheSize = 0;
        m_caches[i].isLoaded = false;
    }
}

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CHistoryManager::~CHistoryManager() {
    Deinitialize();
}

//+------------------------------------------------------------------+
//| Initialize history manager                                       |
//+------------------------------------------------------------------+
bool CHistoryManager::Initialize(ENUM_TIMEFRAMES primaryTF, int preloadBars) {
    m_primaryTimeframe = primaryTF;
    m_preloadBars = preloadBars;
    
    if(m_symbol == NULL || m_symbol == "") {
        m_symbol = Symbol();
    }
    
    // Initialize logger
    m_logger = new CLogger();
    m_logger.Info("HistoryManager initialized for " + m_symbol, "HistoryManager");
    
    // Preload primary timeframe data
    return PreloadData(m_primaryTimeframe, m_preloadBars);
}

//+------------------------------------------------------------------+
//| Deinitialize history manager                                     |
//+------------------------------------------------------------------+
void CHistoryManager::Deinitialize() {
    ClearAllCaches();
    
    if(m_logger != NULL) {
        m_logger.Info("HistoryManager deinitialized", "HistoryManager");
        m_logger.FlushBufferToFile();
        delete m_logger;
        m_logger = NULL;
    }
}

//+------------------------------------------------------------------+
//| Get rates data                                                   |
//+------------------------------------------------------------------+
bool CHistoryManager::GetRates(ENUM_TIMEFRAMES timeframe, MqlRates &rates[], 
                              int count = 100, int startPos = 0) {
    if(count <= 0) {
        if(m_logger != NULL) m_logger.Error("Invalid count in GetRates: " + IntegerToString(count));
        return false;
    }
    
    m_totalRequests++;
    
    // Try to get from cache first
    int cacheIndex = FindCacheIndex(timeframe);
    if(cacheIndex >= 0 && m_caches[cacheIndex].isLoaded && 
       m_caches[cacheIndex].cacheSize >= count + startPos) {
        m_cacheHits++;
        
        if(ArrayResize(rates, count) != count) {
            if(m_logger != NULL) m_logger.Error("Failed to resize rates array");
            return false;
        }
        
        // Copy data from cache
        for(int i = 0; i < count; i++) {
            if(startPos + i < m_caches[cacheIndex].cacheSize) {
                rates[i] = m_caches[cacheIndex].rates[startPos + i];
            }
        }
        
        m_lastAccessTime = GetTickCount();
        return true;
    }
    
    // Cache miss - load directly from server
    m_cacheMisses++;
    return LoadRatesFromServer(timeframe, rates, 0, 0);
}

//+------------------------------------------------------------------+
//| Get rates between dates                                          |
//+------------------------------------------------------------------+
bool CHistoryManager::GetRatesBetween(ENUM_TIMEFRAMES timeframe, MqlRates &rates[],
                                     datetime fromDate, datetime toDate) {
    if(fromDate >= toDate) {
        if(m_logger != NULL) m_logger.Error("Invalid date range in GetRatesBetween");
        return false;
    }
    
    return LoadRatesFromServer(timeframe, rates, fromDate, toDate);
}

//+------------------------------------------------------------------+
//| Get open prices array                                            |
//+------------------------------------------------------------------+
bool CHistoryManager::GetOpenArray(ENUM_TIMEFRAMES timeframe, double &open[], 
                                  int count = 100, int startPos = 0) {
    MqlRates rates[];
    if(!GetRates(timeframe, rates, count, startPos)) {
        return false;
    }
    
    if(ArrayResize(open, count) != count) {
        return false;
    }
    
    for(int i = 0; i < count; i++) {
        open[i] = rates[i].open;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Get close prices array                                           |
//+------------------------------------------------------------------+
bool CHistoryManager::GetCloseArray(ENUM_TIMEFRAMES timeframe, double &close[], 
                                   int count = 100, int startPos = 0) {
    MqlRates rates[];
    if(!GetRates(timeframe, rates, count, startPos)) {
        return false;
    }
    
    if(ArrayResize(close, count) != count) {
        return false;
    }
    
    for(int i = 0; i < count; i++) {
        close[i] = rates[i].close;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Get tick data                                                    |
//+------------------------------------------------------------------+
bool CHistoryManager::GetTicks(MqlTick &ticks[], datetime fromDate, datetime toDate, 
                              uint flags = COPY_TICKS_ALL) {
    return LoadTicksFromServer(ticks, fromDate, toDate);
}

//+------------------------------------------------------------------+
//| Get bar time for specific datetime                              |
//+------------------------------------------------------------------+
datetime CHistoryManager::GetBarTime(ENUM_TIMEFRAMES timeframe, datetime time) {
    int minutes = GetTimeframeMinutes(timeframe);
    if(minutes <= 0) return 0;
    
    datetime barTime = time - (time % (minutes * 60));
    return barTime;
}

//+------------------------------------------------------------------+
//| Preload data for specific timeframe                              |
//+------------------------------------------------------------------+
bool CHistoryManager::PreloadData(ENUM_TIMEFRAMES timeframe, int bars) {
    return LoadToCache(timeframe, bars);
}

//+------------------------------------------------------------------+
//| Check if timeframe data is cached                                |
//+------------------------------------------------------------------+
bool CHistoryManager::IsCached(ENUM_TIMEFRAMES timeframe) {
    int index = FindCacheIndex(timeframe);
    return (index >= 0 && m_caches[index].isLoaded);
}

//+------------------------------------------------------------------+
//| Clear cache for specific timeframe                               |
//+------------------------------------------------------------------+
void CHistoryManager::ClearCache(ENUM_TIMEFRAMES timeframe = PERIOD_CURRENT) {
    int index = FindCacheIndex(timeframe);
    if(index >= 0) {
        ArrayFree(m_caches[index].rates);
        m_caches[index].isLoaded = false;
        m_caches[index].cacheSize = 0;
        m_caches[index].cacheTime = 0;
        
        if(m_logger != NULL) {
            m_logger.Info("Cleared cache for " + TimeframeToString(timeframe), "HistoryManager");
        }
    }
}

//+------------------------------------------------------------------+
//| Clear all caches                                                 |
//+------------------------------------------------------------------+
void CHistoryManager::ClearAllCaches() {
    for(int i = 0; i < 21; i++) {
        if(m_caches[i].isLoaded) {
            ArrayFree(m_caches[i].rates);
            m_caches[i].isLoaded = false;
            m_caches[i].cacheSize = 0;
            m_caches[i].cacheTime = 0;
        }
    }
}

//+------------------------------------------------------------------+
//| Convert timeframe to string                                      |
//+------------------------------------------------------------------+
string CHistoryManager::TimeframeToString(ENUM_TIMEFRAMES timeframe) {
    switch(timeframe) {
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

//+------------------------------------------------------------------+
//| Get timeframe in minutes                                         |
//+------------------------------------------------------------------+
int CHistoryManager::GetTimeframeMinutes(ENUM_TIMEFRAMES timeframe) {
    switch(timeframe) {
        case PERIOD_M1: return 1;
        case PERIOD_M5: return 5;
        case PERIOD_M15: return 15;
        case PERIOD_M30: return 30;
        case PERIOD_H1: return 60;
        case PERIOD_H4: return 240;
        case PERIOD_D1: return 1440;
        case PERIOD_W1: return 10080;
        case PERIOD_MN1: return 43200;
        default: return 0;
    }
}

//+------------------------------------------------------------------+
//| Get cache data for specific timeframe                            |
//+------------------------------------------------------------------+
bool CHistoryManager::GetCacheData(ENUM_TIMEFRAMES timeframe, SHistoryCache &cache) {
    int index = FindCacheIndex(timeframe);
    if(index >= 0) {
        cache = m_caches[index];
        return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Load data to cache                                               |
//+------------------------------------------------------------------+
bool CHistoryManager::LoadToCache(ENUM_TIMEFRAMES timeframe, int bars) {
    int index = FindCacheIndex(timeframe);
    if(index < 0) {
        // Find empty slot
        for(int i = 0; i < 21; i++) {
            if(!m_caches[i].isLoaded) {
                index = i;
                break;
            }
        }
        if(index < 0) {
            if(m_logger != NULL) m_logger.Error("No empty cache slots available");
            return false; // No empty slots
        }
    }
    
    // Initialize cache entry
    m_caches[index].symbol = m_symbol;
    m_caches[index].timeframe = timeframe;
    
    // Resize array
    if(ArrayResize(m_caches[index].rates, bars) != bars) {
        if(m_logger != NULL) m_logger.Error("Failed to allocate cache for " + TimeframeToString(timeframe));
        return false;
    }
    
    // Load data from server
    int copied = CopyRates(m_symbol, timeframe, 0, bars, m_caches[index].rates);
    if(copied <= 0) {
        if(m_logger != NULL) m_logger.Error("Failed to load rates for " + TimeframeToString(timeframe));
        ArrayFree(m_caches[index].rates);
        return false;
    }
    
    // Update cache info
    m_caches[index].cacheSize = copied;
    m_caches[index].cacheTime = TimeCurrent();
    m_caches[index].isLoaded = true;
    m_cacheCount++;
    
    if(m_logger != NULL) {
        m_logger.Info("Cached " + IntegerToString(copied) + " bars for " + TimeframeToString(timeframe), "HistoryManager");
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Find cache index for timeframe                                   |
//+------------------------------------------------------------------+
int CHistoryManager::FindCacheIndex(ENUM_TIMEFRAMES timeframe) {
    for(int i = 0; i < 21; i++) {
        if(m_caches[i].timeframe == timeframe && m_caches[i].isLoaded) {
            return i;
        }
    }
    return -1;
}

//+------------------------------------------------------------------+
//| Validate rate data                                               |
//+------------------------------------------------------------------+
bool CHistoryManager::ValidateRate(const MqlRates &rate) {
    if(rate.time <= 0) return false;
    if(rate.open <= 0 || rate.high <= 0 || rate.low <= 0 || rate.close <= 0) return false;
    if(rate.low > rate.high) return false; // Low should be <= high
    if(rate.open < rate.low || rate.open > rate.high) return false;
    if(rate.close < rate.low || rate.close > rate.high) return false;
    if(rate.tick_volume < 0) return false;
    if(rate.spread < 0) return false;
    if(rate.real_volume < 0) return false;
    
    return true;
}

//+------------------------------------------------------------------+
//| Load rates from server                                           |
//+------------------------------------------------------------------+
bool CHistoryManager::LoadRatesFromServer(ENUM_TIMEFRAMES timeframe, MqlRates &rates[],
                                         datetime fromDate, datetime toDate) {
    int count = 0;
    
    if(fromDate == 0 && toDate == 0) {
        // Load recent bars
        count = 100;
        if(ArrayResize(rates, count) != count) {
            return false;
        }
        count = CopyRates(m_symbol, timeframe, 0, 100, rates);
    } else {
        // Load specific date range
        count = CopyRates(m_symbol, timeframe, fromDate, toDate, rates);
    }
    
    if(count <= 0) {
        if(m_logger != NULL) {
            m_logger.Error("Failed to load rates from server for " + TimeframeToString(timeframe));
        }
        return false;
    }
    
    // Resize to actual count
    ArrayResize(rates, count);
    return true;
}

//+------------------------------------------------------------------+
//| Load ticks from server                                           |
//+------------------------------------------------------------------+
bool CHistoryManager::LoadTicksFromServer(MqlTick &ticks[], datetime fromDate, datetime toDate) {
    int count = CopyTicksRange(m_symbol, ticks, COPY_TICKS_ALL, fromDate * 1000, toDate * 1000);
    
    if(count <= 0) {
        if(m_logger != NULL) {
            m_logger.Error("Failed to load ticks from server");
        }
        return false;
    }
    
    // Resize to actual count
    ArrayResize(ticks, count);
    return true;
}

#endif