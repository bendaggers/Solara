// Indicators/IndicatorTypes.mqh
//+------------------------------------------------------------------+
//| Description: Types, enums, and constants for Indicator System   |
//+------------------------------------------------------------------+
#ifndef INDICATORTYPES_MQH
#define INDICATORTYPES_MQH

//+------------------------------------------------------------------+
//| Indicator Types Enumeration                                      |
//+------------------------------------------------------------------+
enum ENUM_INDICATOR_TYPE
{
    INDICATOR_EMA = 0,      // Exponential Moving Average
    INDICATOR_ATR = 1,      // Average True Range
    INDICATOR_BB  = 2,      // Bollinger Bands
    INDICATOR_RSI = 3,      // Relative Strength Index
    INDICATOR_MACD = 4,     // Moving Average Convergence Divergence
    INDICATOR_SMA = 5,      // Simple Moving Average
    INDICATOR_WMA = 6,      // Weighted Moving Average
    INDICATOR_SMMA = 7,     // Smoothed Moving Average
    INDICATOR_STOCH = 8,    // Stochastic Oscillator
    INDICATOR_ADX = 9,      // Average Directional Index
    
    INDICATOR_CUSTOM = 99   // Custom/User-defined indicator
};

//+------------------------------------------------------------------+
//| Bollinger Band Band Type                                         |
//+------------------------------------------------------------------+
enum ENUM_BB_BAND
{
    BB_UPPER = 0,   // Upper Bollinger Band
    BB_MIDDLE = 1,  // Middle Bollinger Band (SMA)
    BB_LOWER = 2    // Lower Bollinger Band
};

//+------------------------------------------------------------------+
//| Cache Entry Structure (64 bytes total)                           |
//+------------------------------------------------------------------+
struct CacheEntry
{
    string          key;            // Unique key (e.g., "EURUSD_H4_EMA_50")
    double          value;          // Indicator value
    datetime        timestamp;      // When value was calculated
    int             accessCount;    // How many times accessed
    uchar           flags;          // Bit flags (isDirty, isValid, etc.)
    datetime        expiresAt;      // When cache entry expires
    
    // Constructor
    CacheEntry() 
    {
        key = "";
        value = 0.0;
        timestamp = 0;
        accessCount = 0;
        flags = 0;
        expiresAt = 0;
    }
};

//+------------------------------------------------------------------+
//| Indicator Parameters Structure                                   |
//+------------------------------------------------------------------+
struct IndicatorParams
{
    ENUM_INDICATOR_TYPE  type;      // Indicator type
    int                  period;    // Main period
    double               param1;    // Additional parameter 1 (BB deviation, etc.)
    double               param2;    // Additional parameter 2
    int                  param3;    // Additional parameter 3 (integer)
    ENUM_MA_METHOD       method;    // MA method for MA-based indicators
    ENUM_APPLIED_PRICE   price;     // Applied price
    
    // Constructor with defaults
    IndicatorParams()
    {
        type = INDICATOR_EMA;
        period = 20;
        param1 = 0.0;
        param2 = 0.0;
        param3 = 0;
        method = MODE_EMA;
        price = PRICE_CLOSE;
    }
};

//+------------------------------------------------------------------+
//| Handle Information Structure                                     |
//+------------------------------------------------------------------+
struct HandleInfo
{
    int         handle;             // MT5 indicator handle
    int         refCount;           // How many strategies using it
    datetime    createdAt;          // When handle was created
    datetime    lastUsed;           // When handle was last used
    string      key;                // Associated cache key
    bool        isValid;            // Is handle still valid
    
    HandleInfo()
    {
        handle = INVALID_HANDLE;
        refCount = 0;
        createdAt = 0;
        lastUsed = 0;
        key = "";
        isValid = false;
    }
};

//+------------------------------------------------------------------+
//| Performance Statistics Structure                                 |
//+------------------------------------------------------------------+
struct PerformanceStats
{
    // Cache statistics
    int         memoryHits;         // Memory cache hits
    int         memoryMisses;       // Memory cache misses
    int         fileHits;           // File cache hits
    int         fileMisses;         // File cache misses
    int         mt5Calculations;    // MT5 calculations performed
    
    // Timing statistics
    double      avgMemoryTime;      // Average time for memory cache (ms)
    double      avgFileTime;        // Average time for file cache (ms)
    double      avgMT5Time;         // Average time for MT5 calculation (ms)
    
    // Handle statistics
    int         handlesCreated;     // Total handles created
    int         handlesReleased;    // Total handles released
    int         currentHandles;     // Current active handles
    
    // Constructor
    PerformanceStats()
    {
        memoryHits = 0;
        memoryMisses = 0;
        fileHits = 0;
        fileMisses = 0;
        mt5Calculations = 0;
        
        avgMemoryTime = 0.0;
        avgFileTime = 0.0;
        avgMT5Time = 0.0;
        
        handlesCreated = 0;
        handlesReleased = 0;
        currentHandles = 0;
    }
};

//+------------------------------------------------------------------+
//| SYSTEM CONSTANTS                                                 |
//+------------------------------------------------------------------+

// Cache Configuration
#define MAX_MEMORY_CACHE_ENTRIES    200     // Maximum entries in memory cache
#define MEMORY_CACHE_TTL_SECONDS    5       // Time-to-live for memory cache
#define FILE_CACHE_TTL_SECONDS      86400   // 24 hours for file cache
#define HANDLE_CLEANUP_MINUTES      60      // Clean unused handles after 60 min

// Binary File Format
#define INDICATOR_MAGIC_NUMBER      0x534F4C41  // "SOLA" in hex
#define INDICATOR_FILE_VERSION      1
#define CACHE_ENTRY_SIZE            64      // Size of each cache entry in bytes
#define FILE_HEADER_SIZE            64      // Size of file header

// Cache Entry Flags (bit positions)
#define FLAG_IS_DIRTY               0x01    // Needs to be saved to file
#define FLAG_IS_VALID               0x02    // Entry is valid
#define FLAG_FROM_FILE              0x04    // Value loaded from file cache
#define FLAG_FROM_MT5               0x08    // Value calculated from MT5

// Error Codes
#define ERROR_INVALID_HANDLE        -1
#define ERROR_CACHE_FULL           -2
#define ERROR_FILE_IO              -3
#define ERROR_INVALID_PARAMS       -4
#define ERROR_INDICATOR_FAILED     -5

//+------------------------------------------------------------------+
//| Helper Functions                                                 |
//+------------------------------------------------------------------+

// Convert indicator type to string
string IndicatorTypeToString(ENUM_INDICATOR_TYPE type)
{
    switch(type)
    {
        case INDICATOR_EMA:     return "EMA";
        case INDICATOR_ATR:     return "ATR";
        case INDICATOR_BB:      return "BB";
        case INDICATOR_RSI:     return "RSI";
        case INDICATOR_MACD:    return "MACD";
        case INDICATOR_SMA:     return "SMA";
        case INDICATOR_WMA:     return "WMA";
        case INDICATOR_SMMA:    return "SMMA";
        case INDICATOR_STOCH:   return "STOCH";
        case INDICATOR_ADX:     return "ADX";
        default:                return "UNKNOWN";
    }
}

// Convert string to indicator type
ENUM_INDICATOR_TYPE StringToIndicatorType(string typeStr)
{
    if(typeStr == "EMA")     return INDICATOR_EMA;
    if(typeStr == "ATR")     return INDICATOR_ATR;
    if(typeStr == "BB")      return INDICATOR_BB;
    if(typeStr == "RSI")     return INDICATOR_RSI;
    if(typeStr == "MACD")    return INDICATOR_MACD;
    if(typeStr == "SMA")     return INDICATOR_SMA;
    if(typeStr == "WMA")     return INDICATOR_WMA;
    if(typeStr == "SMMA")    return INDICATOR_SMMA;
    if(typeStr == "STOCH")   return INDICATOR_STOCH;
    if(typeStr == "ADX")     return INDICATOR_ADX;
    
    return INDICATOR_CUSTOM;
}

// Check if cache entry is expired
bool IsCacheEntryExpired(CacheEntry &entry)
{
    if(entry.expiresAt == 0) return false;
    return (TimeCurrent() > entry.expiresAt);
}

// Set cache entry expiry
void SetCacheEntryExpiry(CacheEntry &entry, int ttlSeconds)
{
    entry.expiresAt = TimeCurrent() + ttlSeconds;
}

// Get current Unix timestamp
uint GetUnixTimestamp()
{
    return (uint)TimeCurrent();
}

//+------------------------------------------------------------------+
//| Cache Entry Comparison for sorting                               |
//+------------------------------------------------------------------+

// Compare by last access time (for LRU eviction)
int CompareByAccessTime(const CacheEntry &a, const CacheEntry &b)
{
    if(a.timestamp < b.timestamp) return -1;
    if(a.timestamp > b.timestamp) return 1;
    return 0;
}

// Compare by access count (for LFU eviction)
int CompareByAccessCount(const CacheEntry &a, const CacheEntry &b)
{
    if(a.accessCount < b.accessCount) return -1;
    if(a.accessCount > b.accessCount) return 1;
    return 0;
}

#endif // INDICATORTYPES_MQH