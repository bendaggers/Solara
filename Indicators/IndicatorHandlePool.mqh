// Indicators/IndicatorHandlePool.mqh
//+------------------------------------------------------------------+
//| Description: MT5 Indicator Handle Management with Reference      |
//|              Counting for Indicator System                       |
//+------------------------------------------------------------------+
#ifndef INDICATORHANDLEPOOL_MQH
#define INDICATORHANDLEPOOL_MQH

#include "IndicatorTypes.mqh"
#include "IndicatorKey.mqh"
#include "IndicatorUtils.mqh"

//+------------------------------------------------------------------+
//| Indicator Handle Pool Class                                      |
//+------------------------------------------------------------------+
class CIndicatorHandlePool
{
private:
    // Handle storage with reference counting
    struct PoolHandle
    {
        int         handle;         // MT5 indicator handle
        string      key;            // Cache key for this handle
        int         refCount;       // How many strategies using it
        datetime    created;        // When handle was created
        datetime    lastUsed;       // When handle was last used
        bool        isValid;        // Is handle still valid?
        int         errorCount;     // Number of consecutive errors
        
        PoolHandle()
        {
            handle = INVALID_HANDLE;
            key = "";
            refCount = 0;
            created = 0;
            lastUsed = 0;
            isValid = false;
            errorCount = 0;
        }
    };
    
    PoolHandle     m_handles[100];  // Pool of handles (max 100)
    int            m_handleCount;   // Current number of handles
    int            m_maxHandles;    // Maximum handles allowed
    int            m_cleanupMinutes; // Cleanup interval in minutes
    
    // Statistics
    int            m_handlesCreated;
    int            m_handlesReleased;
    int            m_handleErrors;
    PerformanceStats m_stats;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor                                                      |
    //+------------------------------------------------------------------+
    CIndicatorHandlePool(int maxHandles = 50, int cleanupMinutes = HANDLE_CLEANUP_MINUTES)
    {
        m_handleCount = 0;
        m_maxHandles = maxHandles;
        m_cleanupMinutes = cleanupMinutes;
        m_handlesCreated = 0;
        m_handlesReleased = 0;
        m_handleErrors = 0;
        
        Print("IndicatorHandlePool initialized. Max handles: ", m_maxHandles, 
              ", Cleanup: ", m_cleanupMinutes, " minutes");
    }
    
    //+------------------------------------------------------------------+
    //| Destructor                                                       |
    //+------------------------------------------------------------------+
    ~CIndicatorHandlePool()
    {
        // Release all handles
        ReleaseAllHandles();
        
        Print("IndicatorHandlePool destroyed. Created: ", m_handlesCreated, 
              ", Released: ", m_handlesReleased, ", Errors: ", m_handleErrors);
    }
    
    //+------------------------------------------------------------------+
    //| Get or create EMA handle                                         |
    //+------------------------------------------------------------------+
    int GetEMAHandle(string symbol, ENUM_TIMEFRAMES timeframe, int period,
                    ENUM_MA_METHOD method = MODE_EMA, ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        string key = CIndicatorKey::CreateEMAKey(symbol, timeframe, period, method, price);
        return GetHandle(key, symbol, timeframe, INDICATOR_EMA, period, 0, 0, method, price);
    }
    
    //+------------------------------------------------------------------+
    //| Get or create ATR handle                                         |
    //+------------------------------------------------------------------+
    int GetATRHandle(string symbol, ENUM_TIMEFRAMES timeframe, int period)
    {
        string key = CIndicatorKey::CreateATRKey(symbol, timeframe, period);
        return GetHandle(key, symbol, timeframe, INDICATOR_ATR, period);
    }
    
    //+------------------------------------------------------------------+
    //| Get or create Bollinger Bands handle                            |
    //+------------------------------------------------------------------+
    int GetBBHandle(string symbol, ENUM_TIMEFRAMES timeframe, int period, double deviation,
                   ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        string key = CIndicatorKey::CreateBBKey(symbol, timeframe, period, deviation, price);
        IndicatorParams params;
        params.type = INDICATOR_BB;
        params.period = period;
        params.param1 = deviation;
        params.price = price;
        
        return GetHandle(key, symbol, timeframe, params);
    }
    
    //+------------------------------------------------------------------+
    //| Get or create SMA handle                                         |
    //+------------------------------------------------------------------+
    int GetSMAHandle(string symbol, ENUM_TIMEFRAMES timeframe, int period,
                    ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        string key = CIndicatorKey::CreateSMAKey(symbol, timeframe, period, price);
        return GetHandle(key, symbol, timeframe, INDICATOR_SMA, period, 0, 0, MODE_SMA, price);
    }
    
    //+------------------------------------------------------------------+
    //| Get or create generic indicator handle                          |
    //+------------------------------------------------------------------+
    int GetHandle(string key, string symbol, ENUM_TIMEFRAMES timeframe, 
                 ENUM_INDICATOR_TYPE type, int period = 0, double param1 = 0.0, 
                 double param2 = 0.0, ENUM_MA_METHOD method = MODE_SMA, 
                 ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        IndicatorParams params;
        params.type = type;
        params.period = period;
        params.param1 = param1;
        params.param2 = param2;
        params.method = method;
        params.price = price;
        
        return GetHandle(key, symbol, timeframe, params);
    }
    
    //+------------------------------------------------------------------+
    //| Get or create handle with parameters                            |
    //+------------------------------------------------------------------+
    int GetHandle(string key, string symbol, ENUM_TIMEFRAMES timeframe, IndicatorParams &params)
    {
        ulong startTime = GetMicrosecondCount();
        
        // Check if handle already exists in pool
        int handleIndex = FindHandleByKey(key);
        
        if(handleIndex != -1)
        {
            // Handle exists - update reference count and usage
            m_handles[handleIndex].refCount++;
            m_handles[handleIndex].lastUsed = TimeCurrent();
            
            // Validate handle
            if(!ValidateHandle(m_handles[handleIndex].handle))
            {
                // Handle is invalid - recreate it
                Print("WARNING: Handle invalid, recreating: ", key);
                if(!RecreateHandle(handleIndex, symbol, timeframe, params))
                {
                    m_handleErrors++;
                    UpdateStats(false, GetMicrosecondCount() - startTime);
                    return INVALID_HANDLE;
                }
            }
            
            UpdateStats(true, GetMicrosecondCount() - startTime);
            return m_handles[handleIndex].handle;
        }
        
        // Need to create new handle
        if(m_handleCount >= m_maxHandles)
        {
            // Pool is full - try to cleanup unused handles
            CleanupUnusedHandles();
            
            if(m_handleCount >= m_maxHandles)
            {
                // Still full - cannot create new handle
                Print("ERROR: Handle pool full (", m_handleCount, "/", m_maxHandles, ")");
                UpdateStats(false, GetMicrosecondCount() - startTime);
                return INVALID_HANDLE;
            }
        }
        
        // Create new handle
        int newHandle = CreateIndicatorHandle(symbol, timeframe, params);
        
        if(newHandle == INVALID_HANDLE)
        {
            m_handleErrors++;
            UpdateStats(false, GetMicrosecondCount() - startTime);
            return INVALID_HANDLE;
        }
        
        // Add to pool
        handleIndex = AddToPool(key, newHandle);
        if(handleIndex == -1)
        {
            // Failed to add to pool - release handle
            IndicatorRelease(newHandle);
            UpdateStats(false, GetMicrosecondCount() - startTime);
            return INVALID_HANDLE;
        }
        
        m_handlesCreated++;
        UpdateStats(false, GetMicrosecondCount() - startTime);
        
        return newHandle;
    }
    
    //+------------------------------------------------------------------+
    //| Release handle (decrement reference count)                       |
    //+------------------------------------------------------------------+
    bool ReleaseHandle(string key)
    {
        int handleIndex = FindHandleByKey(key);
        
        if(handleIndex == -1)
        {
            Print("WARNING: Attempt to release non-existent handle: ", key);
            return false;
        }
        
        m_handles[handleIndex].refCount--;
        m_handles[handleIndex].lastUsed = TimeCurrent();
        
        // If no more references and handle is old, release it
        if(m_handles[handleIndex].refCount <= 0)
        {
            datetime ageMinutes = (TimeCurrent() - m_handles[handleIndex].lastUsed) / 60;
            if(ageMinutes > m_cleanupMinutes)
            {
                return RemoveFromPool(handleIndex);
            }
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Force release handle (immediate)                                |
    //+------------------------------------------------------------------+
    bool ForceReleaseHandle(string key)
    {
        int handleIndex = FindHandleByKey(key);
        
        if(handleIndex == -1)
            return false;
            
        return RemoveFromPool(handleIndex);
    }
    
    //+------------------------------------------------------------------+
    //| Release all handles                                              |
    //+------------------------------------------------------------------+
    void ReleaseAllHandles()
    {
        Print("Releasing all indicator handles...");
        
        for(int i = m_handleCount - 1; i >= 0; i--)
        {
            RemoveFromPool(i);
        }
        
        Print("All handles released");
    }
    
    //+------------------------------------------------------------------+
    //| Get reference count for a handle                                 |
    //+------------------------------------------------------------------+
    int GetRefCount(string key)
    {
        int handleIndex = FindHandleByKey(key);
        
        if(handleIndex == -1)
            return 0;
            
        return m_handles[handleIndex].refCount;
    }
    
    //+------------------------------------------------------------------+
    //| Check if handle exists in pool                                   |
    //+------------------------------------------------------------------+
    bool HasHandle(string key)
    {
        return (FindHandleByKey(key) != -1);
    }
    
    //+------------------------------------------------------------------+
    //| Get handle by key                                                |
    //+------------------------------------------------------------------+
    int GetHandleByKey(string key)
    {
        int handleIndex = FindHandleByKey(key);
        
        if(handleIndex == -1)
            return INVALID_HANDLE;
            
        return m_handles[handleIndex].handle;
    }
    
    //+------------------------------------------------------------------+
    //| Cleanup unused handles                                           |
    //+------------------------------------------------------------------+
    int CleanupUnusedHandles()
    {
        int removed = 0;
        
        for(int i = m_handleCount - 1; i >= 0; i--)
        {
            if(m_handles[i].refCount <= 0)
            {
                datetime ageMinutes = (TimeCurrent() - m_handles[i].lastUsed) / 60;
                if(ageMinutes > m_cleanupMinutes)
                {
                    if(RemoveFromPool(i))
                        removed++;
                }
            }
        }
        
        if(removed > 0)
            Print("Cleaned up ", removed, " unused handles");
            
        return removed;
    }
    
    //+------------------------------------------------------------------+
    //| Validate all handles in pool                                     |
    //+------------------------------------------------------------------+
    int ValidateAllHandles()
    {
        int invalidCount = 0;
        
        for(int i = 0; i < m_handleCount; i++)
        {
            if(!ValidateHandle(m_handles[i].handle))
            {
                m_handles[i].isValid = false;
                invalidCount++;
                
                // Try to recreate if still in use
                if(m_handles[i].refCount > 0)
                {
                    Print("WARNING: Invalid handle still in use: ", m_handles[i].key);
                }
            }
            else
            {
                m_handles[i].isValid = true;
                m_handles[i].errorCount = 0;
            }
        }
        
        if(invalidCount > 0)
            Print("Found ", invalidCount, " invalid handles");
            
        return invalidCount;
    }
    
    //+------------------------------------------------------------------+
    //| Get pool statistics                                              |
    //+------------------------------------------------------------------+
    void GetStats(int &created, int &released, int &current, int &errors, 
                 int &refCountTotal, double &avgRefCount)
    {
        created = m_handlesCreated;
        released = m_handlesReleased;
        current = m_handleCount;
        errors = m_handleErrors;
        
        // Calculate reference count statistics
        refCountTotal = 0;
        for(int i = 0; i < m_handleCount; i++)
        {
            refCountTotal += m_handles[i].refCount;
        }
        
        if(m_handleCount > 0)
            avgRefCount = (double)refCountTotal / m_handleCount;
        else
            avgRefCount = 0.0;
    }
    
    //+------------------------------------------------------------------+
    //| Get performance statistics                                       |
    //+------------------------------------------------------------------+
    PerformanceStats GetPerformanceStats()
    {
        return m_stats;
    }
    

    //+------------------------------------------------------------------+
    //| Print pool contents (for debugging)                              |
    //+------------------------------------------------------------------+
    void PrintPoolContents(bool detailed = false)
    {
        Print("=== Handle Pool Contents (", m_handleCount, "/", m_maxHandles, " handles) ===");
        Print("Created: ", m_handlesCreated, ", Released: ", m_handlesReleased, 
              ", Errors: ", m_handleErrors);
        
        if(!detailed || m_handleCount == 0)
        {
            Print("Handles: ", GetHandleKeysAsString());
            return;
        }
        
        // Detailed print
        int refCountTotal = 0;
        
        for(int i = 0; i < m_handleCount && i < 20; i++) // Limit output
        {
            // FIX: Direct array access instead of reference
            string age = CIndicatorUtils::FormatPercent(
                (double)(TimeCurrent() - m_handles[i].lastUsed) / (m_cleanupMinutes * 60));
                
            string status = m_handles[i].isValid ? "VALID" : "INVALID";
            
            Print(i + 1, ". ", m_handles[i].key, 
                  " (Refs: ", m_handles[i].refCount, ", Age: ", age, 
                  ", Status: ", status, ", Handle: ", m_handles[i].handle, ")");
            
            refCountTotal += m_handles[i].refCount;
        }
        
        if(m_handleCount > 20)
            Print("... and ", m_handleCount - 20, " more handles");
            
        if(m_handleCount > 0)
            Print("Average ref count: ", (double)refCountTotal / m_handleCount);
            
        Print("=== End Handle Pool Contents ===");
    }
    
    //+------------------------------------------------------------------+
    //| Test handle pool functionality                                   |
    //+------------------------------------------------------------------+
    static void TestHandlePool()
    {
        Print("=== Testing Handle Pool ===");
        
        CIndicatorHandlePool pool(10, 1); // Small pool for testing
        
        // Test EMA handle creation
        int handle1 = pool.GetEMAHandle("EURUSD", PERIOD_H4, 50);
        Print("Created EMA handle: ", handle1 != INVALID_HANDLE ? "PASS" : "FAIL");
        
        // Test ATR handle creation
        int handle2 = pool.GetATRHandle("EURUSD", PERIOD_H4, 14);
        Print("Created ATR handle: ", handle2 != INVALID_HANDLE ? "PASS" : "FAIL");
        
        // Test duplicate request (should return same handle)
        int handle3 = pool.GetEMAHandle("EURUSD", PERIOD_H4, 50);
        Print("Duplicate EMA request returns same handle: ", 
              (handle1 == handle3) ? "PASS" : "FAIL");
        
        // Test reference counting
        Print("EMA handle ref count: ", pool.GetRefCount(
              CIndicatorKey::CreateEMAKey("EURUSD", PERIOD_H4, 50)));
        
        // Test release
        pool.ReleaseHandle(CIndicatorKey::CreateEMAKey("EURUSD", PERIOD_H4, 50));
        Print("After release, EMA ref count: ", pool.GetRefCount(
              CIndicatorKey::CreateEMAKey("EURUSD", PERIOD_H4, 50)));
        
        // Test pool statistics
        int created, released, current, errors, refCountTotal;
        double avgRefCount;
        pool.GetStats(created, released, current, errors, refCountTotal, avgRefCount);
        
        Print("Pool stats - Created: ", created, ", Released: ", released, 
              ", Current: ", current, ", Errors: ", errors);
        
        // Print pool contents
        pool.PrintPoolContents(true);
        
        // Test cleanup
        Sleep(61000); // Wait 61 seconds for cleanup (1 minute + buffer)
        int cleaned = pool.CleanupUnusedHandles();
        Print("Cleaned up handles after 1 min: ", cleaned);
        
        Print("=== Handle Pool Test Complete ===");
    }
    
private:
    //+------------------------------------------------------------------+
    //| Find handle by key in pool                                       |
    //+------------------------------------------------------------------+
    int FindHandleByKey(string key)
    {
        for(int i = 0; i < m_handleCount; i++)
        {
            if(m_handles[i].key == key)
                return i;
        }
        return -1;
    }
    
    //+------------------------------------------------------------------+
    //| Add handle to pool                                               |
    //+------------------------------------------------------------------+
    int AddToPool(string key, int handle)
    {
        if(m_handleCount >= 100)
            return -1;
            
        int index = m_handleCount;
        
        m_handles[index].handle = handle;
        m_handles[index].key = key;
        m_handles[index].refCount = 1;
        m_handles[index].created = TimeCurrent();
        m_handles[index].lastUsed = TimeCurrent();
        m_handles[index].isValid = true;
        m_handles[index].errorCount = 0;
        
        m_handleCount++;
        
        return index;
    }
    
    //+------------------------------------------------------------------+
    //| Remove handle from pool                                          |
    //+------------------------------------------------------------------+
    bool RemoveFromPool(int index)
    {
        if(index < 0 || index >= m_handleCount)
            return false;
            
        // Release MT5 handle
        if(m_handles[index].handle != INVALID_HANDLE)
        {
            IndicatorRelease(m_handles[index].handle);
            m_handlesReleased++;
        }
        
        // Shift remaining entries
        for(int i = index; i < m_handleCount - 1; i++)
        {
            m_handles[i] = m_handles[i + 1];
        }
        
        // Clear last entry
        m_handles[m_handleCount - 1] = PoolHandle();
        m_handleCount--;
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Create MT5 indicator handle                                      |
    //+------------------------------------------------------------------+
    int CreateIndicatorHandle(string symbol, ENUM_TIMEFRAMES timeframe, IndicatorParams &params)
    {
        switch(params.type)
        {
            case INDICATOR_EMA:
                return iMA(symbol, timeframe, params.period, 0, params.method, params.price);
                
            case INDICATOR_ATR:
                return iATR(symbol, timeframe, params.period);
                
            case INDICATOR_BB:
                return iBands(symbol, timeframe, params.period, 0, params.param1, params.price);
                
            case INDICATOR_SMA:
                return iMA(symbol, timeframe, params.period, 0, MODE_SMA, params.price);
                
            case INDICATOR_RSI:
                return iRSI(symbol, timeframe, params.period, params.price);
                
            case INDICATOR_MACD:
                return iMACD(symbol, timeframe, params.period, (int)params.param1, 
                           (int)params.param2, params.price);
                
            default:
                Print("ERROR: Unsupported indicator type: ", IndicatorTypeToString(params.type));
                return INVALID_HANDLE;
        }
    }
    
    //+------------------------------------------------------------------+
    //| Validate MT5 handle                                              |
    //+------------------------------------------------------------------+
    bool ValidateHandle(int handle)
    {
        if(handle == INVALID_HANDLE)
            return false;
            
        // Try to copy a small amount of data to test handle
        double testBuffer[1];
        int copied = CopyBuffer(handle, 0, 0, 1, testBuffer);
        
        return (copied > 0);
    }
    
    //+------------------------------------------------------------------+
    //| Recreate invalid handle                                         |
    //+------------------------------------------------------------------+
    bool RecreateHandle(int index, string symbol, ENUM_TIMEFRAMES timeframe, IndicatorParams &params)
    {
        if(index < 0 || index >= m_handleCount)
            return false;
            
        // Release old handle
        if(m_handles[index].handle != INVALID_HANDLE)
        {
            IndicatorRelease(m_handles[index].handle);
        }
        
        // Create new handle
        int newHandle = CreateIndicatorHandle(symbol, timeframe, params);
        
        if(newHandle == INVALID_HANDLE)
        {
            m_handles[index].isValid = false;
            m_handles[index].errorCount++;
            return false;
        }
        
        m_handles[index].handle = newHandle;
        m_handles[index].isValid = true;
        m_handles[index].errorCount = 0;
        m_handles[index].lastUsed = TimeCurrent();
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Get all handle keys as string                                    |
    //+------------------------------------------------------------------+
    string GetHandleKeysAsString()
    {
        string keys = "";
        int count = 0;
        
        for(int i = 0; i < m_handleCount && count < 10; i++)
        {
            if(keys != "") keys += ", ";
            keys += m_handles[i].key;
            count++;
        }
        
        if(m_handleCount > 10)
            keys += ", ...";
            
        return keys;
    }
    
    //+------------------------------------------------------------------+
    //| Update performance statistics                                    |
    //+------------------------------------------------------------------+
    void UpdateStats(bool isReused, ulong responseTimeMicros)
    {
        m_stats.currentHandles = m_handleCount;
        
        if(isReused)
        {
            // Handle was reused from pool
            // Update average time for reused handles
            double responseTimeMs = responseTimeMicros / 1000.0;
            // We don't track this separately in current stats structure
        }
        else
        {
            // New handle was created
            m_stats.handlesCreated++;
        }
    }
    
    //+------------------------------------------------------------------+
    //| Get current time in microseconds                                 |
    //+------------------------------------------------------------------+
    ulong GetMicrosecondCount()
    {
        return GetTickCount() * 1000;
    }
};

#endif // INDICATORHANDLEPOOL_MQH