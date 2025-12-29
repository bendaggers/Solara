// StrategyManager.mqh - Manages multiple trading strategies
//+------------------------------------------------------------------+
//| Description: Orchestrates all strategies, handles timing,        |
//|              and coordinates between strategies                   |
//+------------------------------------------------------------------+
#ifndef STRATEGYMANAGER_MQH
#define STRATEGYMANAGER_MQH

#include "StrategyBase.mqh"
#include "TradeLogger.mqh"

//+------------------------------------------------------------------+
//| Strategy Manager Class                                           |
//+------------------------------------------------------------------+
class CStrategyManager
{
private:
    CStrategyBase*   m_strategies[];     // Array of strategy pointers
    int              m_strategyCount;
    
    // PTS-specific timing variables
    datetime         m_lastDailyFilterTime;
    datetime         m_lastH4ScanTime[6]; // For each H4 scan time
    
public:
    // Constructor
    CStrategyManager() 
    { 
        m_strategyCount = 0; 
        m_lastDailyFilterTime = 0;
        ArrayInitialize(m_lastH4ScanTime, 0);
    }
    
    // Destructor
    ~CStrategyManager() 
    { 
        ClearStrategies(); 
    }
    
    // Add a strategy
    bool AddStrategy(CStrategyBase* strategy)
    {
        if(!strategy || m_strategyCount >= 10) return false;
        
        ArrayResize(m_strategies, m_strategyCount + 1);
        m_strategies[m_strategyCount] = strategy;
        m_strategyCount++;
        
        Print("Strategy added: ", strategy.GetName());
        return true;
    }
    
    // Remove all strategies
    void ClearStrategies()
    {
        for(int i = 0; i < m_strategyCount; i++)
        {
            if(CheckPointer(m_strategies[i]) == POINTER_DYNAMIC)
                delete m_strategies[i];
        }
        ArrayResize(m_strategies, 0);
        m_strategyCount = 0;
    }
    
    // Initialize all strategies
    bool InitializeAll()
    {
        for(int i = 0; i < m_strategyCount; i++)
        {
            if(!m_strategies[i].Initialize())
            {
                Print("ERROR: Failed to initialize strategy: ", m_strategies[i].GetName());
                return false;
            }
        }
        return true;
    }
    
    // Deinitialize all strategies
    void DeinitializeAll()
    {
        for(int i = 0; i < m_strategyCount; i++)
        {
            m_strategies[i].Deinitialize();
        }
    }
    
    // Timer event - called from main EA's OnTimer()
    void OnTimer()
    {
        // Get current time
        MqlDateTime currentTime;
        TimeCurrent(currentTime);
        datetime now = TimeCurrent();
        
        // Check if it's time for PTS Daily Filter (00:05 GMT)
        if(IsTimeForDailyFilter(currentTime, now))
        {
            Print("=== PTS Daily Filter Triggered at ", TimeToString(now, TIME_SECONDS), " ===");
            RunPTSDailyFilter();
            m_lastDailyFilterTime = now;
        }
        
        // Check if it's time for PTS H4 Scan
        if(IsTimeForH4Scan(currentTime, now))
        {
            Print("=== PTS H4 Scan Triggered at ", TimeToString(now, TIME_SECONDS), " ===");
            RunPTSH4Scan();
        }
        
        // Run timer events for all enabled strategies
        for(int i = 0; i < m_strategyCount; i++)
        {
            if(m_strategies[i].IsEnabled())
            {
                m_strategies[i].OnTimer();
            }
        }
    }
    
    // Check if it's time for PTS Daily Filter (00:05 GMT)
    bool IsTimeForDailyFilter(MqlDateTime &currentTime, datetime now)
    {
        // Check if it's 00:05 GMT (± 30 seconds for timer tolerance)
        if(currentTime.hour == 0 && currentTime.min == 5)
        {
            if(now - m_lastDailyFilterTime > 60) // At least 60 seconds since last run
                return true;
        }
        return false;
    }
    
    // Check if it's time for PTS H4 Scan
    bool IsTimeForH4Scan(MqlDateTime &currentTime, datetime now)
    {
        // PTS H4 scan times: 00:05, 04:00, 08:00, 12:00, 16:00, 20:00 GMT
        int scanTimes[6] = {5, 4, 8, 12, 16, 20}; // Hour component
        int currentHour = currentTime.hour;
        int currentMinute = currentTime.min;
        
        // Special case: 00:05 (already handled by daily filter, but also H4 scan)
        if(currentHour == 0 && currentMinute == 5)
        {
            if(now - m_lastH4ScanTime[0] > 60)
                return true;
        }
        
        // Other scan times (on the hour)
        for(int i = 1; i < 6; i++) // Start from 1 (skip 00:05)
        {
            if(currentHour == scanTimes[i] && currentMinute == 0)
            {
                if(now - m_lastH4ScanTime[i] > 60)
                    return true;
            }
        }
        
        return false;
    }
    
    // Run PTS Daily Filter
    void RunPTSDailyFilter()
    {
        // Find PTS strategy
        CStrategyBase* ptsStrategy = FindStrategyByType(STRATEGY_TYPE_PTS);
        if(ptsStrategy && ptsStrategy.IsEnabled())
        {
            // Call PTS-specific daily filter
            // This will be implemented in PTSStrategy class
            Print("Running PTS Daily Filter...");
            // The actual implementation will be in PTSStrategy.mqh
        }
    }
    
    // Run PTS H4 Scan
    void RunPTSH4Scan()
    {
        // Find PTS strategy
        CStrategyBase* ptsStrategy = FindStrategyByType(STRATEGY_TYPE_PTS);
        if(ptsStrategy && ptsStrategy.IsEnabled())
        {
            // Call PTS-specific H4 scan
            Print("Running PTS H4 Scan...");
            // The actual implementation will be in PTSStrategy.mqh
            
            // Update last scan time
            MqlDateTime currentTime;
            TimeCurrent(currentTime);
            int hour = currentTime.hour;
            
            // Map hour to index
            int index = 0;
            if(hour == 0) index = 0;      // 00:05
            else if(hour == 4) index = 1; // 04:00
            else if(hour == 8) index = 2; // 08:00
            else if(hour == 12) index = 3; // 12:00
            else if(hour == 16) index = 4; // 16:00
            else if(hour == 20) index = 5; // 20:00
            
            m_lastH4ScanTime[index] = TimeCurrent();
        }
    }
    
    // Find strategy by type
    CStrategyBase* FindStrategyByType(ENUM_STRATEGY_TYPE type)
    {
        for(int i = 0; i < m_strategyCount; i++)
        {
            if(m_strategies[i].GetType() == type)
                return m_strategies[i];
        }
        return NULL;
    }
    
    // Find strategy by name
    CStrategyBase* FindStrategyByName(string name)
    {
        for(int i = 0; i < m_strategyCount; i++)
        {
            if(m_strategies[i].GetName() == name)
                return m_strategies[i];
        }
        return NULL;
    }
    
    // Get total number of open positions across all strategies
    int GetTotalOpenPositions()
    {
        int total = 0;
        for(int i = 0; i < m_strategyCount; i++)
        {
            if(m_strategies[i].IsEnabled())
                total += m_strategies[i].CountOpenPositions();
        }
        return total;
    }
    
    // Get today's total P&L across all strategies
    double GetTotalTodayPNL()
    {
        double total = 0.0;
        for(int i = 0; i < m_strategyCount; i++)
        {
            if(m_strategies[i].IsEnabled())
                total += m_strategies[i].GetTodayPNL();
        }
        return total;
    }
    
    // Get strategy count
    int GetStrategyCount() { return m_strategyCount; }
    
    // Get strategy by index
    CStrategyBase* GetStrategy(int index)
    {
        if(index >= 0 && index < m_strategyCount)
            return m_strategies[index];
        return NULL;
    }
    
    // Print status of all strategies
    void PrintAllStatus()
    {
        Print("=== Strategy Manager Status ===");
        Print("Total Strategies: ", m_strategyCount);
        
        for(int i = 0; i < m_strategyCount; i++)
        {
            Print(i+1, ". ", m_strategies[i].GetName(), 
                  " [", m_strategies[i].IsEnabled() ? "ENABLED" : "DISABLED", "]");
            Print("   Positions: ", m_strategies[i].CountOpenPositions(), 
                  " / ", m_strategies[i].GetMaxPositions());
            Print("   Today P&L: $", DoubleToString(m_strategies[i].GetTodayPNL(), 2));
        }
        Print("Total Positions: ", GetTotalOpenPositions());
        Print("Total Today P&L: $", DoubleToString(GetTotalTodayPNL(), 2));
        Print("===============================");
    }
};

#endif // STRATEGYMANAGER_MQH