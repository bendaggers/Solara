//+------------------------------------------------------------------+
//| StrategyBase.mqh - Abstract base class for all Solara strategies |
//+------------------------------------------------------------------+
#ifndef STRATEGYBASE_MQH
#define STRATEGYBASE_MQH

#include "..\Utilities\Logger.mqh"
#include "..\Utilities\ErrorHandler.mqh"
#include "..\Utilities\DateTimeUtils.mqh"
#include "..\Utilities\MathUtils.mqh"

//+------------------------------------------------------------------+
//| Strategy execution frequencies                                   |
//+------------------------------------------------------------------+
enum ENUM_STRATEGY_FREQUENCY {
    STRATEGY_FREQ_TICK,      // Execute on every tick
    STRATEGY_FREQ_M1,        // Every minute
    STRATEGY_FREQ_M5,        // Every 5 minutes
    STRATEGY_FREQ_M15,       // Every 15 minutes
    STRATEGY_FREQ_M30,       // Every 30 minutes
    STRATEGY_FREQ_H1,        // Hourly
    STRATEGY_FREQ_H4,        // Every 4 hours
    STRATEGY_FREQ_DAILY,     // Daily
    STRATEGY_FREQ_WEEKLY     // Weekly
};

//+------------------------------------------------------------------+
//| Strategy states                                                  |
//+------------------------------------------------------------------+
enum ENUM_STRATEGY_STATE {
    STRATEGY_STATE_UNINITIALIZED, // Not initialized
    STRATEGY_STATE_INITIALIZED,   // Initialized but not running
    STRATEGY_STATE_RUNNING,       // Actively running
    STRATEGY_STATE_PAUSED,        // Temporarily paused
    STRATEGY_STATE_STOPPED,       // Stopped (can be restarted)
    STRATEGY_STATE_ERROR          // Error state
};

//+------------------------------------------------------------------+
//| Trade signal structure                                           |
//+------------------------------------------------------------------+
struct StrategySignal {
    ENUM_ORDER_TYPE signalType;   // ORDER_TYPE_BUY, ORDER_TYPE_SELL, etc.
    double strength;              // Signal strength 0-1
    double entryPrice;            // Suggested entry price
    double stopLoss;              // Suggested stop loss
    double takeProfit;            // Suggested take profit
    double volume;                // Suggested volume
    string comment;               // Signal comment
    datetime expiration;          // Signal expiration time
    int magicNumber;              // Magic number for order identification
};

//+------------------------------------------------------------------+
//| Strategy configuration structure                                 |
//+------------------------------------------------------------------+
struct StrategyConfig {
    string strategyName;
    string strategyVersion;
    bool enabled;
    ENUM_STRATEGY_FREQUENCY frequency;
    int magicNumber;
    string symbol;
    ENUM_TIMEFRAMES timeframe;
    double riskPercent;
    double maxDrawdownPercent;
    int maxOpenPositions;
    bool allowHedge;
    bool enableTrailingStop;
    // Strategy-specific parameters
    double params[50];           // Generic parameter array
    string stringParams[20];     // Generic string parameters
};

//+------------------------------------------------------------------+
//| Strategy performance metrics                                     |
//+------------------------------------------------------------------+
struct StrategyPerformance {
    int totalTrades;
    int winningTrades;
    int losingTrades;
    double totalProfit;
    double totalLoss;
    double netProfit;
    double profitFactor;
    double winRate;
    double maxDrawdown;
    double maxDrawdownPercent;
    double averageWin;
    double averageLoss;
    double averageTrade;
    double sharpeRatio;
    double recoveryFactor;
    datetime lastUpdate;
};

//+------------------------------------------------------------------+
//| CStrategyBase - Abstract strategy base class                     |
//+------------------------------------------------------------------+
class CStrategyBase {
protected:
    // Core properties
    string m_strategyName;
    string m_strategyVersion;
    ENUM_STRATEGY_STATE m_state;
    ENUM_STRATEGY_FREQUENCY m_frequency;
    StrategyConfig m_config;
    StrategyPerformance m_performance;
    
    // Technical properties
    string m_symbol;
    ENUM_TIMEFRAMES m_timeframe;
    int m_magicNumber;
    bool m_enabled;
    bool m_initialized;
    
    // Time tracking
    datetime m_lastTickTime;
    datetime m_lastBarTime;
    datetime m_lastExecutionTime;
    
    // Components
    CLogger* m_logger;
    CErrorHandler* m_errorHandler;
    CDateTimeUtils* m_dateTimeUtils;
    CMathUtils* m_mathUtils;
    
    // Internal tracking
    int m_openPositions;
    double m_equityPeak;
    double m_equityValley;
    double m_currentDrawdown;

public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CStrategyBase(string name, string version = "1.0") {
        m_strategyName = name;
        m_strategyVersion = version;
        m_state = STRATEGY_STATE_UNINITIALIZED;
        m_frequency = STRATEGY_FREQ_TICK;
        m_enabled = false;
        m_initialized = false;
        m_magicNumber = 0;
        m_symbol = _Symbol;
        m_timeframe = PERIOD_CURRENT;
        
        m_lastTickTime = 0;
        m_lastBarTime = 0;
        m_lastExecutionTime = 0;
        m_openPositions = 0;
        m_equityPeak = 0;
        m_equityValley = 0;
        m_currentDrawdown = 0;
        
        // Initialize components
        m_logger = GlobalLogger;
        m_errorHandler = GlobalErrorHandler;
        m_dateTimeUtils = GlobalDateTimeUtils;
        m_mathUtils = GlobalMathUtils;
        
        // Initialize performance metrics
        InitializePerformanceMetrics();
        
        LogInfo("Strategy instance created: " + name);
    }
    
    virtual ~CStrategyBase() {
        LogInfo("Strategy instance destroyed: " + m_strategyName);
    }
    
    //+------------------------------------------------------------------+
    //| Pure virtual methods - must be implemented by derived classes    |
    //+------------------------------------------------------------------+
    virtual bool Initialize() = 0;
    virtual void Deinitialize() = 0;
    virtual void OnTick() = 0;
    virtual void OnTimer() = 0;
    virtual void OnBar() = 0;
    virtual StrategySignal GenerateSignal() = 0;
    virtual void OnTradeTransaction(const MqlTradeTransaction& trans,
                                   const MqlTradeRequest& request,
                                   const MqlTradeResult& result) = 0;
    
    //+------------------------------------------------------------------+
    //| Public interface methods                                         |
    //+------------------------------------------------------------------+
    string GetName() const { return m_strategyName; }
    string GetVersion() const { return m_strategyVersion; }
    ENUM_STRATEGY_STATE GetState() const { return m_state; }
    ENUM_STRATEGY_FREQUENCY GetFrequency() const { return m_frequency; }
    bool IsEnabled() const { return m_enabled; }
    bool IsInitialized() const { return m_initialized; }
    int GetMagicNumber() const { return m_magicNumber; }
    string GetSymbol() const { return m_symbol; }
    ENUM_TIMEFRAMES GetTimeframe() const { return m_timeframe; }
    
    StrategyConfig GetConfig() const { return m_config; }
    StrategyPerformance GetPerformance() const { return m_performance; }
    
    void SetEnabled(bool enabled) {
        if(m_enabled != enabled) {
            m_enabled = enabled;
            LogInfo("Strategy " + (enabled ? "enabled" : "disabled"));
        }
    }
    
    void SetSymbol(string symbol) {
        if(m_symbol != symbol) {
            m_symbol = symbol;
            LogInfo("Symbol changed to: " + symbol);
        }
    }
    
    void SetTimeframe(ENUM_TIMEFRAMES timeframe) {
        if(m_timeframe != timeframe) {
            m_timeframe = timeframe;
            LogInfo("Timeframe changed to: " + IntegerToString(timeframe));
        }
    }
    
    void SetMagicNumber(int magic) {
        if(m_magicNumber != magic) {
            m_magicNumber = magic;
            LogInfo("Magic number changed to: " + IntegerToString(magic));
        }
    }
    
    //+------------------------------------------------------------------+
    //| Strategy lifecycle management                                    |
    //+------------------------------------------------------------------+
    bool Start() {
        if(!m_initialized) {
            LogError("Cannot start uninitialized strategy");
            return false;
        }
        
        if(m_state == STRATEGY_STATE_RUNNING) {
            LogWarn("Strategy already running");
            return true;
        }
        
        m_state = STRATEGY_STATE_RUNNING;
        m_enabled = true;
        
        LogInfo("Strategy started");
        return true;
    }
    
    bool Stop() {
        if(m_state == STRATEGY_STATE_STOPPED) {
            return true;
        }
        
        m_state = STRATEGY_STATE_STOPPED;
        m_enabled = false;
        
        LogInfo("Strategy stopped");
        return true;
    }
    
    bool Pause() {
        if(m_state == STRATEGY_STATE_RUNNING) {
            m_state = STRATEGY_STATE_PAUSED;
            LogInfo("Strategy paused");
            return true;
        }
        return false;
    }
    
    bool Resume() {
        if(m_state == STRATEGY_STATE_PAUSED) {
            m_state = STRATEGY_STATE_RUNNING;
            LogInfo("Strategy resumed");
            return true;
        }
        return false;
    }
    
    //+------------------------------------------------------------------+
    //| Performance tracking methods                                     |
    //+------------------------------------------------------------------+
    void UpdatePerformanceMetrics(double profit) {
        m_performance.totalTrades++;
        m_performance.netProfit += profit;
        
        if(profit > 0) {
            m_performance.winningTrades++;
            m_performance.totalProfit += profit;
        } else {
            m_performance.losingTrades++;
            m_performance.totalLoss += MathAbs(profit);
        }
        
        // Calculate derived metrics
        if(m_performance.totalTrades > 0) {
            m_performance.winRate = (double)m_performance.winningTrades / m_performance.totalTrades * 100;
        }
        
        if(m_performance.totalLoss != 0) {
            m_performance.profitFactor = m_performance.totalProfit / m_performance.totalLoss;
        } else {
            m_performance.profitFactor = m_performance.totalProfit > 0 ? 1000 : 0; // Large number if no losses
        }
        
        if(m_performance.winningTrades > 0) {
            m_performance.averageWin = m_performance.totalProfit / m_performance.winningTrades;
        }
        
        if(m_performance.losingTrades > 0) {
            m_performance.averageLoss = m_performance.totalLoss / m_performance.losingTrades;
        }
        
        m_performance.averageTrade = m_performance.netProfit / m_performance.totalTrades;
        m_performance.lastUpdate = TimeCurrent();
        
        // Update drawdown
        UpdateDrawdown();
    }
    
    void ResetPerformance() {
        InitializePerformanceMetrics();
        LogInfo("Performance metrics reset");
    }
    
    //+------------------------------------------------------------------+
    //| Utility methods for derived classes                              |
    //+------------------------------------------------------------------+
public:
    void InitializePerformanceMetrics() {
        m_performance.totalTrades = 0;
        m_performance.winningTrades = 0;
        m_performance.losingTrades = 0;
        m_performance.totalProfit = 0;
        m_performance.totalLoss = 0;
        m_performance.netProfit = 0;
        m_performance.profitFactor = 0;
        m_performance.winRate = 0;
        m_performance.maxDrawdown = 0;
        m_performance.maxDrawdownPercent = 0;
        m_performance.averageWin = 0;
        m_performance.averageLoss = 0;
        m_performance.averageTrade = 0;
        m_performance.sharpeRatio = 0;
        m_performance.recoveryFactor = 0;
        m_performance.lastUpdate = TimeCurrent();
    }
    
    void UpdateDrawdown() {
        double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
        
        if(currentEquity > m_equityPeak) {
            m_equityPeak = currentEquity;
            m_equityValley = currentEquity;
        }
        
        if(currentEquity < m_equityValley) {
            m_equityValley = currentEquity;
        }
        
        m_currentDrawdown = m_equityPeak - m_equityValley;
        double drawdownPercent = (m_equityPeak > 0) ? (m_currentDrawdown / m_equityPeak) * 100 : 0;
        
        if(drawdownPercent > m_performance.maxDrawdownPercent) {
            m_performance.maxDrawdown = m_currentDrawdown;
            m_performance.maxDrawdownPercent = drawdownPercent;
        }
    }
    
    bool IsNewBar() {
        if(m_dateTimeUtils == NULL) return false;
        
        datetime currentBarTime = m_dateTimeUtils.GetBarOpenTime(m_timeframe, 0);
        if(currentBarTime != m_lastBarTime) {
            m_lastBarTime = currentBarTime;
            return true;
        }
        return false;
    }
    
    bool ShouldExecute() {
        if(!m_enabled || m_state != STRATEGY_STATE_RUNNING) {
            return false;
        }
        
        datetime currentTime = TimeCurrent();
        
        // Check execution frequency
        switch(m_frequency) {
            case STRATEGY_FREQ_TICK:
                return true;
                
            case STRATEGY_FREQ_M1:
                return (currentTime - m_lastExecutionTime) >= 60;
                
            case STRATEGY_FREQ_M5:
                return (currentTime - m_lastExecutionTime) >= 300;
                
            case STRATEGY_FREQ_M15:
                return (currentTime - m_lastExecutionTime) >= 900;
                
            case STRATEGY_FREQ_M30:
                return (currentTime - m_lastExecutionTime) >= 1800;
                
            case STRATEGY_FREQ_H1:
                return (currentTime - m_lastExecutionTime) >= 3600;
                
            case STRATEGY_FREQ_H4:
                return (currentTime - m_lastExecutionTime) >= 14400;
                
            case STRATEGY_FREQ_DAILY:
                return !m_dateTimeUtils.IsSameDay(currentTime, m_lastExecutionTime);
                
            case STRATEGY_FREQ_WEEKLY: {
                MqlDateTime currentDt, lastDt;
                TimeToStruct(currentTime, currentDt);
                TimeToStruct(m_lastExecutionTime, lastDt);
                return (currentDt.day_of_week < lastDt.day_of_week) || 
                       (currentTime - m_lastExecutionTime) >= 604800;
            }
        }
        
        return false;
    }
    
    void UpdateExecutionTime() {
        m_lastExecutionTime = TimeCurrent();
    }
    
    //+------------------------------------------------------------------+
    //| Logging methods                                                  |
    //+------------------------------------------------------------------+
    void LogError(string message) {
        if(m_logger != NULL) {
            m_logger.Error(message, "Strategy:" + m_strategyName);
        }
    }
    
    void LogWarn(string message) {
        if(m_logger != NULL) {
            m_logger.Warn(message, "Strategy:" + m_strategyName);
        }
    }
    
    void LogInfo(string message) {
        if(m_logger != NULL) {
            m_logger.Info(message, "Strategy:" + m_strategyName);
        }
    }
    
    void LogDebug(string message) {
        if(m_logger != NULL) {
            m_logger.Debug(message, "Strategy:" + m_strategyName);
        }
    }
    
    void LogTrace(string message) {
        if(m_logger != NULL) {
            m_logger.Trace(message, "Strategy:" + m_strategyName);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Error handling methods                                           |
    //+------------------------------------------------------------------+
    bool HandleError(string message, int errorCode = 0, ENUM_ERROR_SEVERITY severity = ERROR_SEVERITY_ERROR) {
        if(m_errorHandler != NULL) {
            return m_errorHandler.HandleStrategyError(message, m_strategyName, "StrategyBase");
        }
        return false;
    }
    
    //+------------------------------------------------------------------+
    //| Validation methods                                               |
    //+------------------------------------------------------------------+
    bool ValidateSymbol(string symbol) {
        if(symbol == "" || symbol == NULL) {
            LogError("Invalid symbol: " + symbol);
            return false;
        }
        
        if(!SymbolInfoInteger(symbol, SYMBOL_SELECT)) {
            LogError("Symbol not available: " + symbol);
            return false;
        }
        
        return true;
    }
    
    bool ValidateVolume(double volume, string symbol = "") {
        if(symbol == "") symbol = m_symbol;
        
        double minVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
        double maxVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
        double stepVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
        
        if(volume < minVolume || volume > maxVolume) {
            LogError(StringFormat("Volume %.2f outside allowed range [%.2f, %.2f]", 
                                 volume, minVolume, maxVolume));
            return false;
        }
        
        // Check if volume is multiple of step
        double normalizedVolume = MathRound(volume / stepVolume) * stepVolume;
        if(MathAbs(volume - normalizedVolume) > 0.0001) {
            LogError(StringFormat("Volume %.2f not multiple of step %.2f", volume, stepVolume));
            return false;
        }
        
        return true;
    }
};

#endif