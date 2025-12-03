//+------------------------------------------------------------------+
//| StrategyManager.mqh - Manages strategy lifecycle for Solara      |
//+------------------------------------------------------------------+
#ifndef STRATEGYMANAGER_MQH
#define STRATEGYMANAGER_MQH

#include "StrategyBase.mqh"
#include "..\Utilities\Logger.mqh"
#include "..\Utilities\ErrorHandler.mqh"
#include "..\Utilities\ArrayUtils.mqh"

//+------------------------------------------------------------------+
//| Strategy manager configuration                                   |
//+------------------------------------------------------------------+
struct StrategyManagerConfig {
    int maxStrategies;
    bool enableAutoRecovery;
    bool enablePerformanceMonitoring;
    int performanceUpdateInterval;
    double maxTotalDrawdownPercent;
    int maxTotalPositions;
};

//+------------------------------------------------------------------+
//| CStrategyManager - Main strategy management class                |
//+------------------------------------------------------------------+
class CStrategyManager {
private:
    // Strategy storage
    CArrayObj m_strategies;
    string m_strategyNames[];
    
    // Configuration
    StrategyManagerConfig m_config;
    
    // State tracking
    bool m_initialized;
    bool m_running;
    datetime m_lastUpdateTime;
    
    // Performance tracking
    double m_totalNetProfit;
    double m_totalDrawdown;
    int m_totalPositions;
    
    // Components
    CLogger* m_logger;
    CErrorHandler* m_errorHandler;
    CArrayUtils* m_arrayUtils;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CStrategyManager() {
        m_initialized = false;
        m_running = false;
        m_lastUpdateTime = 0;
        m_totalNetProfit = 0;
        m_totalDrawdown = 0;
        m_totalPositions = 0;
        
        // Default configuration
        m_config.maxStrategies = 50;
        m_config.enableAutoRecovery = true;
        m_config.enablePerformanceMonitoring = true;
        m_config.performanceUpdateInterval = 60; // seconds
        m_config.maxTotalDrawdownPercent = 20.0;
        m_config.maxTotalPositions = 100;
        
        // Initialize components
        m_logger = GlobalLogger;
        m_errorHandler = GlobalErrorHandler;
        m_arrayUtils = GlobalArrayUtils;
        
        m_strategies.Clear();
        ArrayResize(m_strategyNames, 0);
        
        LogInfo("Strategy Manager created");
    }
    
    ~CStrategyManager() {
        Deinitialize();
        LogInfo("Strategy Manager destroyed");
    }
    
    //+------------------------------------------------------------------+
    //| Initialization and lifecycle                                     |
    //+------------------------------------------------------------------+
    bool Initialize() {
        if(m_initialized) {
            LogWarn("Strategy Manager already initialized");
            return true;
        }
        
        LogInfo("Initializing Strategy Manager...");
        
        // Validate components
        if(m_logger == NULL) {
            Print("Error: Logger not initialized");
            return false;
        }
        
        m_initialized = true;
        m_running = true;
        
        LogInfo("Strategy Manager initialized successfully");
        LogInfo(StringFormat("Configuration: MaxStrategies=%d, AutoRecovery=%s", 
                            m_config.maxStrategies, m_config.enableAutoRecovery ? "Yes" : "No"));
        
        return true;
    }
    
    void Deinitialize() {
        if(!m_initialized) return;
        
        LogInfo("Deinitializing Strategy Manager...");
        
        // Stop all strategies
        StopAllStrategies();
        
        // Remove all strategies
        for(int i = m_strategies.Total() - 1; i >= 0; i--) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL) {
                    strategy.Deinitialize();
                }
                m_strategies.Delete(i);
            }
        }
        
        m_strategies.Clear();
        ArrayResize(m_strategyNames, 0);
        
        m_initialized = false;
        m_running = false;
        
        LogInfo("Strategy Manager deinitialized");
    }
    
    //+------------------------------------------------------------------+
    //| Strategy management methods                                      |
    //+------------------------------------------------------------------+
    bool RegisterStrategy(CStrategyBase* strategy) {
        if(!m_initialized) {
            LogError("Cannot register strategy - Manager not initialized");
            return false;
        }
        
        if(strategy == NULL) {
            LogError("Cannot register NULL strategy");
            return false;
        }
        
        if(m_strategies.Total() >= m_config.maxStrategies) {
            LogError("Cannot register strategy - maximum number reached: " + IntegerToString(m_config.maxStrategies));
            return false;
        }
        
        string strategyName = strategy.GetName();
        
        // Check if strategy already registered
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* existingStrategy = dynamic_cast<CStrategyBase*>(obj);
                if(existingStrategy != NULL && existingStrategy.GetName() == strategyName) {
                    LogError("Strategy already registered: " + strategyName);
                    return false;
                }
            }
        }
        
        // Add to collections
        if(m_strategies.Add(dynamic_cast<CObject*>(strategy))) {
            int newSize = ArraySize(m_strategyNames) + 1;
            ArrayResize(m_strategyNames, newSize);
            m_strategyNames[newSize - 1] = strategyName;
            
            LogInfo("Strategy registered: " + strategyName);
            return true;
        }
        
        LogError("Failed to register strategy: " + strategyName);
        return false;
    }
    
    bool UnregisterStrategy(string strategyName) {
        int index = -1;
        CStrategyBase* strategyToRemove = NULL;
        
        // Find the strategy
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL && strategy.GetName() == strategyName) {
                    index = i;
                    strategyToRemove = strategy;
                    break;
                }
            }
        }
        
        if(index < 0) {
            LogWarn("Strategy not found for unregistering: " + strategyName);
            return false;
        }
        
        if(strategyToRemove != NULL) {
            strategyToRemove.Stop();
            strategyToRemove.Deinitialize();
        }
        
        m_strategies.Delete(index);
        
        // Remove from names array
        int nameIndex = -1;
        for(int i = 0; i < ArraySize(m_strategyNames); i++) {
            if(m_strategyNames[i] == strategyName) {
                nameIndex = i;
                break;
            }
        }
        
        if(nameIndex >= 0) {
            for(int i = nameIndex; i < ArraySize(m_strategyNames) - 1; i++) {
                m_strategyNames[i] = m_strategyNames[i + 1];
            }
            ArrayResize(m_strategyNames, ArraySize(m_strategyNames) - 1);
        }
        
        LogInfo("Strategy unregistered: " + strategyName);
        return true;
    }
    
    bool InitializeStrategy(string strategyName) {
        CStrategyBase* strategy = GetStrategy(strategyName);
        if(strategy == NULL) {
            LogError("Strategy not found for initialization: " + strategyName);
            return false;
        }
        
        if(strategy.IsInitialized()) {
            LogWarn("Strategy already initialized: " + strategyName);
            return true;
        }
        
        if(strategy.Initialize()) {
            LogInfo("Strategy initialized: " + strategyName);
            return true;
        } else {
            LogError("Failed to initialize strategy: " + strategyName);
            return false;
        }
    }
    
    bool StartStrategy(string strategyName) {
        CStrategyBase* strategy = GetStrategy(strategyName);
        if(strategy == NULL) {
            LogError("Strategy not found for starting: " + strategyName);
            return false;
        }
        
        if(!strategy.IsInitialized()) {
            LogError("Cannot start uninitialized strategy: " + strategyName);
            return false;
        }
        
        if(strategy.Start()) {
            LogInfo("Strategy started: " + strategyName);
            return true;
        } else {
            LogError("Failed to start strategy: " + strategyName);
            return false;
        }
    }
    
    bool StopStrategy(string strategyName) {
        CStrategyBase* strategy = GetStrategy(strategyName);
        if(strategy == NULL) {
            LogError("Strategy not found for stopping: " + strategyName);
            return false;
        }
        
        if(strategy.Stop()) {
            LogInfo("Strategy stopped: " + strategyName);
            return true;
        } else {
            LogError("Failed to stop strategy: " + strategyName);
            return false;
        }
    }
    
    //+------------------------------------------------------------------+
    //| Batch operations                                                 |
    //+------------------------------------------------------------------+
    bool InitializeAllStrategies() {
        LogInfo("Initializing all strategies...");
        
        bool allSuccess = true;
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL && !strategy.IsInitialized()) {
                    if(!strategy.Initialize()) {
                        LogError("Failed to initialize strategy: " + strategy.GetName());
                        allSuccess = false;
                    }
                }
            }
        }
        
        if(allSuccess) {
            LogInfo("All strategies initialized successfully");
        } else {
            LogWarn("Some strategies failed to initialize");
        }
        
        return allSuccess;
    }
    
    bool StartAllStrategies() {
        LogInfo("Starting all strategies...");
        
        bool allSuccess = true;
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL && strategy.IsInitialized()) {
                    if(!strategy.Start()) {
                        LogError("Failed to start strategy: " + strategy.GetName());
                        allSuccess = false;
                    }
                }
            }
        }
        
        if(allSuccess) {
            LogInfo("All strategies started successfully");
        } else {
            LogWarn("Some strategies failed to start");
        }
        
        return allSuccess;
    }
    
    bool StopAllStrategies() {
        LogInfo("Stopping all strategies...");
        
        bool allSuccess = true;
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL) {
                    if(!strategy.Stop()) {
                        LogError("Failed to stop strategy: " + strategy.GetName());
                        allSuccess = false;
                    }
                }
            }
        }
        
        if(allSuccess) {
            LogInfo("All strategies stopped successfully");
        } else {
            LogWarn("Some strategies failed to stop");
        }
        
        return allSuccess;
    }
    
    //+------------------------------------------------------------------+
    //| Strategy access and information                                  |
    //+------------------------------------------------------------------+
    CStrategyBase* GetStrategy(string strategyName) {
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL && strategy.GetName() == strategyName) {
                    return strategy;
                }
            }
        }
        return NULL;
    }
    
    int GetStrategyCount() const {
        return m_strategies.Total();
    }
    
    int GetActiveStrategyCount() {
        int count = 0;
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL && strategy.IsEnabled() && strategy.GetState() == STRATEGY_STATE_RUNNING) {
                    count++;
                }
            }
        }
        return count;
    }
    
    void GetStrategyNames(string &names[]) {
        if(m_arrayUtils != NULL) {
            m_arrayUtils.ArrayCopy(m_strategyNames, names);
        } else {
            ArrayCopy(names, m_strategyNames);
        }
    }
    
    void GetActiveStrategyNames(string &names[]) {
        ArrayResize(names, 0);
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL && strategy.IsEnabled() && strategy.GetState() == STRATEGY_STATE_RUNNING) {
                    int size = ArraySize(names);
                    ArrayResize(names, size + 1);
                    names[size] = strategy.GetName();
                }
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Event processing methods                                         |
    //+------------------------------------------------------------------+
    void OnTick() {
        if(!m_running) return;
        
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL && strategy.IsEnabled() && strategy.GetState() == STRATEGY_STATE_RUNNING) {
                    if(strategy.GetFrequency() == STRATEGY_FREQ_TICK || strategy.ShouldExecute()) {
                        strategy.OnTick();
                        strategy.UpdateExecutionTime();
                    }
                    
                    // Check for new bar
                    if(strategy.IsNewBar()) {
                        strategy.OnBar();
                    }
                }
            }
        }
        
        // Update performance monitoring
        UpdatePerformanceMonitoring();
    }
    
    void OnTimer() {
        if(!m_running) return;
        
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL && strategy.IsEnabled() && strategy.GetState() == STRATEGY_STATE_RUNNING) {
                    strategy.OnTimer();
                }
            }
        }
    }
    
    void OnTradeTransaction(const MqlTradeTransaction& trans,
                           const MqlTradeRequest& request,
                           const MqlTradeResult& result) {
        if(!m_running) return;
        
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL && strategy.IsEnabled()) {
                    strategy.OnTradeTransaction(trans, request, result);
                }
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetConfig(const StrategyManagerConfig &config) {
        m_config = config;
        LogInfo("Strategy Manager configuration updated");
    }
    
    StrategyManagerConfig GetConfig() const {
        return m_config;
    }
    
    void SetMaxStrategies(int maxStrategies) {
        if(maxStrategies > 0 && maxStrategies != m_config.maxStrategies) {
            m_config.maxStrategies = maxStrategies;
            LogInfo("Max strategies set to: " + IntegerToString(maxStrategies));
        }
    }
    
    void SetAutoRecovery(bool enable) {
        if(m_config.enableAutoRecovery != enable) {
            m_config.enableAutoRecovery = enable;
            LogInfo("Auto recovery " + (enable ? "enabled" : "disabled"));
        }
    }

private:
    //+------------------------------------------------------------------+
    //| Internal helper methods                                          |
    //+------------------------------------------------------------------+
    void RemoveStrategyName(string strategyName) {
        int index = -1;
        for(int i = 0; i < ArraySize(m_strategyNames); i++) {
            if(m_strategyNames[i] == strategyName) {
                index = i;
                break;
            }
        }
        
        if(index >= 0) {
            for(int i = index; i < ArraySize(m_strategyNames) - 1; i++) {
                m_strategyNames[i] = m_strategyNames[i + 1];
            }
            ArrayResize(m_strategyNames, ArraySize(m_strategyNames) - 1);
        }
    }
    
    void UpdatePerformanceMonitoring() {
        if(!m_config.enablePerformanceMonitoring) return;
        
        datetime currentTime = TimeCurrent();
        if(currentTime - m_lastUpdateTime < m_config.performanceUpdateInterval) {
            return;
        }
        
        m_lastUpdateTime = currentTime;
        
        // Update total performance metrics
        m_totalNetProfit = 0;
        m_totalPositions = 0;
        
        for(int i = 0; i < m_strategies.Total(); i++) {
            CObject* obj = m_strategies.At(i);
            if(obj != NULL) {
                CStrategyBase* strategy = dynamic_cast<CStrategyBase*>(obj);
                if(strategy != NULL) {
                    StrategyPerformance perf = strategy.GetPerformance();
                    m_totalNetProfit += perf.netProfit;
                    m_totalPositions += perf.totalTrades;
                }
            }
        }
        
        // Check for drawdown limits
        double equity = AccountInfoDouble(ACCOUNT_EQUITY);
        double balance = AccountInfoDouble(ACCOUNT_BALANCE);
        double drawdownPercent = (balance > 0) ? ((balance - equity) / balance) * 100 : 0;
        
        if(drawdownPercent > m_config.maxTotalDrawdownPercent) {
            LogWarn(StringFormat("Total drawdown limit exceeded: %.2f%% > %.2f%%", 
                               drawdownPercent, m_config.maxTotalDrawdownPercent));
            // Could trigger automatic stop here
        }
        
        // Check position limits
        if(m_totalPositions > m_config.maxTotalPositions) {
            LogWarn(StringFormat("Total position limit exceeded: %d > %d", 
                               m_totalPositions, m_config.maxTotalPositions));
        }
    }
    
    //+------------------------------------------------------------------+
    //| Logging methods                                                  |
    //+------------------------------------------------------------------+
    void LogError(string message) {
        if(m_logger != NULL) {
            m_logger.Error(message, "StrategyManager");
        }
    }
    
    void LogWarn(string message) {
        if(m_logger != NULL) {
            m_logger.Warn(message, "StrategyManager");
        }
    }
    
    void LogInfo(string message) {
        if(m_logger != NULL) {
            m_logger.Info(message, "StrategyManager");
        }
    }
};

#endif