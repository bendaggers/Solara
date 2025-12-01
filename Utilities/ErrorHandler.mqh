//+------------------------------------------------------------------+
//| ErrorHandler.mqh - Comprehensive error handling for Solara       |
//+------------------------------------------------------------------+
#ifndef ERRORHANDLER_MQH
#define ERRORHANDLER_MQH

#include "Logger.mqh"

//+------------------------------------------------------------------+
//| Error severity levels                                            |
//+------------------------------------------------------------------+
enum ENUM_ERROR_SEVERITY {
    ERROR_SEVERITY_INFO = 0,     // Informational
    ERROR_SEVERITY_WARNING = 1,  // Warning - continue operation
    ERROR_SEVERITY_ERROR = 2,    // Error - may affect functionality
    ERROR_SEVERITY_CRITICAL = 3  // Critical - requires immediate attention
};

//+------------------------------------------------------------------+
//| Error categories                                                 |
//+------------------------------------------------------------------+
enum ENUM_ERROR_CATEGORY {
    ERROR_CATEGORY_SYSTEM = 0,       // System/Platform errors
    ERROR_CATEGORY_STRATEGY = 1,     // Strategy-related errors
    ERROR_CATEGORY_EXECUTION = 2,    // Trade execution errors
    ERROR_CATEGORY_DATA = 3,         // Market data errors
    ERROR_CATEGORY_RISK = 4,         // Risk management errors
    ERROR_CATEGORY_NETWORK = 5       // Network/connectivity errors
};

//+------------------------------------------------------------------+
//| Error information structure                                      |
//+------------------------------------------------------------------+
struct ErrorInfo {
    datetime timestamp;
    ENUM_ERROR_SEVERITY severity;
    ENUM_ERROR_CATEGORY category;
    int errorCode;
    string errorMessage;
    string context;
    string component;
    string suggestion;
};

//+------------------------------------------------------------------+
//| CErrorHandler - Main error handling class                        |
//+------------------------------------------------------------------+
class CErrorHandler {
private:
    CArrayObj m_errorHistory;
    int m_maxHistorySize;
    bool m_autoRecovery;
    bool m_enabled;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CErrorHandler(void) : 
        m_maxHistorySize(500),
        m_autoRecovery(true),
        m_enabled(true)
    {
        m_errorHistory.Clear();
    }
    
    ~CErrorHandler(void) {
        m_errorHistory.Clear();
    }
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetAutoRecovery(bool enable) { m_autoRecovery = enable; }
    void SetEnabled(bool enable) { m_enabled = enable; }
    void SetMaxHistorySize(int size) { m_maxHistorySize = size; }
    
    bool GetAutoRecovery() const { return m_autoRecovery; }
    bool GetEnabled() const { return m_enabled; }
    int GetHistorySize() const { return m_errorHistory.Total(); }
    
    //+------------------------------------------------------------------+
    //| Public error handling methods                                    |
    //+------------------------------------------------------------------+
    bool HandleError(int errorCode, string message, string context = "", 
                    ENUM_ERROR_SEVERITY severity = ERROR_SEVERITY_ERROR,
                    ENUM_ERROR_CATEGORY category = ERROR_CATEGORY_SYSTEM,
                    string component = "") {
        
        if(!m_enabled) return false;
        
        ErrorInfo* error = new ErrorInfo();
        error.timestamp = TimeCurrent();
        error.severity = severity;
        error.category = category;
        error.errorCode = errorCode;
        error.errorMessage = message;
        error.context = context;
        error.component = component;
        error.suggestion = GetErrorSuggestion(errorCode, severity);
        
        // Add to history
        if(m_errorHistory.Total() >= m_maxHistorySize) {
            m_errorHistory.Delete(0);
        }
        m_errorHistory.Add(error);
        
        // Log the error
        LogError(error);
        
        // Attempt auto-recovery for non-critical errors
        if(m_autoRecovery && severity < ERROR_SEVERITY_CRITICAL) {
            return AttemptRecovery(error);
        }
        
        return false;
    }
    
    bool HandleTradeError(int errorCode, string operation, string symbol = "", double volume = 0) {
        string context = StringFormat("Trade: %s, Symbol: %s, Volume: %.2f", operation, symbol, volume);
        return HandleError(errorCode, GetTradeErrorDescription(errorCode), context, 
                         ERROR_SEVERITY_ERROR, ERROR_CATEGORY_EXECUTION, "OrderExecutor");
    }
    
    bool HandleDataError(string message, string symbol = "", string dataType = "") {
        string context = StringFormat("Data: %s, Symbol: %s", dataType, symbol);
        return HandleError(0, message, context, ERROR_SEVERITY_WARNING, ERROR_CATEGORY_DATA, "MarketData");
    }
    
    bool HandleStrategyError(string message, string strategyName, string context = "") {
        string fullContext = StringFormat("Strategy: %s, Context: %s", strategyName, context);
        return HandleError(0, message, fullContext, ERROR_SEVERITY_ERROR, ERROR_CATEGORY_STRATEGY, strategyName);
    }
    
    //+------------------------------------------------------------------+
    //| Error history management                                         |
    //+------------------------------------------------------------------+
    void ClearHistory() {
        m_errorHistory.Clear();
    }
    
    int GetErrorCount(ENUM_ERROR_SEVERITY severity = -1, ENUM_ERROR_CATEGORY category = -1) {
        int count = 0;
        for(int i = 0; i < m_errorHistory.Total(); i++) {
            ErrorInfo* error = m_errorHistory.At(i);
            if((severity == -1 || error.severity == severity) &&
               (category == -1 || error.category == category)) {
                count++;
            }
        }
        return count;
    }
    
    void GetRecentErrors(int count, ErrorInfo &errors[]) {
        int total = m_errorHistory.Total();
        int start = MathMax(0, total - count);
        int size = total - start;
        
        ArrayResize(errors, size);
        for(int i = 0; i < size; i++) {
            ErrorInfo* error = m_errorHistory.At(start + i);
            errors[i] = error;
        }
    }
    
    string GetErrorSummary() {
        int total = m_errorHistory.Total();
        int critical = GetErrorCount(ERROR_SEVERITY_CRITICAL);
        int errors = GetErrorCount(ERROR_SEVERITY_ERROR);
        int warnings = GetErrorCount(ERROR_SEVERITY_WARNING);
        
        return StringFormat("Errors: Total=%d, Critical=%d, Errors=%d, Warnings=%d", 
                           total, critical, errors, warnings);
    }

private:
    //+------------------------------------------------------------------+
    //| Internal methods                                                 |
    //+------------------------------------------------------------------+
    void LogError(ErrorInfo* error) {
        if(GlobalLogger == NULL) return;
        
        string levelStr = "";
        switch(error.severity) {
            case ERROR_SEVERITY_INFO:     levelStr = "INFO"; break;
            case ERROR_SEVERITY_WARNING:  levelStr = "WARN"; break;
            case ERROR_SEVERITY_ERROR:    levelStr = "ERROR"; break;
            case ERROR_SEVERITY_CRITICAL: levelStr = "CRITICAL"; break;
        }
        
        string categoryStr = "";
        switch(error.category) {
            case ERROR_CATEGORY_SYSTEM:    categoryStr = "SYSTEM"; break;
            case ERROR_CATEGORY_STRATEGY:  categoryStr = "STRATEGY"; break;
            case ERROR_CATEGORY_EXECUTION: categoryStr = "EXECUTION"; break;
            case ERROR_CATEGORY_DATA:      categoryStr = "DATA"; break;
            case ERROR_CATEGORY_RISK:      categoryStr = "RISK"; break;
            case ERROR_CATEGORY_NETWORK:   categoryStr = "NETWORK"; break;
        }
        
        string logMessage = StringFormat("%s [%s] Code=%d: %s", 
                                        categoryStr, levelStr, error.errorCode, error.errorMessage);
        
        if(error.severity == ERROR_SEVERITY_CRITICAL) {
            GlobalLogger.Error(logMessage, error.context, error.component);
        } else if(error.severity == ERROR_SEVERITY_ERROR) {
            GlobalLogger.Error(logMessage, error.context, error.component);
        } else if(error.severity == ERROR_SEVERITY_WARNING) {
            GlobalLogger.Warn(logMessage, error.context, error.component);
        } else {
            GlobalLogger.Info(logMessage, error.context, error.component);
        }
        
        // Log suggestion if available
        if(error.suggestion != "") {
            GlobalLogger.Info("Suggestion: " + error.suggestion, error.context, error.component);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Error recovery attempts                                          |
    //+------------------------------------------------------------------+
    bool AttemptRecovery(ErrorInfo* error) {
        switch(error.category) {
            case ERROR_CATEGORY_NETWORK:
                return RecoverNetworkError(error);
            case ERROR_CATEGORY_DATA:
                return RecoverDataError(error);
            case ERROR_CATEGORY_EXECUTION:
                return RecoverExecutionError(error);
            default:
                return false;
        }
    }
    
    bool RecoverNetworkError(ErrorInfo* error) {
        // Simple network recovery - wait and retry
        GlobalLogger.Info("Attempting network error recovery", "ErrorHandler");
        Sleep(1000);
        return true;
    }
    
    bool RecoverDataError(ErrorInfo* error) {
        GlobalLogger.Info("Attempting data error recovery", "ErrorHandler");
        // Data errors might require refreshing symbol data
        return true;
    }
    
    bool RecoverExecutionError(ErrorInfo* error) {
        GlobalLogger.Info("Attempting execution error recovery", "ErrorHandler");
        // Execution errors might require modifying order parameters
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Error code descriptions and suggestions                          |
    //+------------------------------------------------------------------+
    string GetTradeErrorDescription(int errorCode) {
        switch(errorCode) {
            case 10004: return "Requote detected";
            case 10006: return "Request rejected";
            case 10007: return "Request canceled by trader";
            case 10008: return "Order placed timeout";
            case 10009: return "Invalid order request";
            case 10010: return "Invalid volume";
            case 10011: return "Invalid price";
            case 10012: return "Invalid stops";
            case 10013: return "Trade disabled";
            case 10014: return "Market closed";
            case 10015: return "Insufficient funds";
            case 10016: return "Price changed";
            case 10017: return "Off quotes";
            case 10018: return "Broker busy";
            case 10019: return "Requote";
            case 10020: return "Order locked";
            case 10021: return "Long positions only allowed";
            case 10022: return "Too many requests";
            default: return "Unknown trade error: " + IntegerToString(errorCode);
        }
    }
    
    string GetErrorSuggestion(int errorCode, ENUM_ERROR_SEVERITY severity) {
        if(severity == ERROR_SEVERITY_CRITICAL) {
            return "Immediate attention required. Consider stopping trading.";
        }
        
        switch(errorCode) {
            case 10004: case 10019: return "Check current prices and retry";
            case 10008: return "Check internet connection and retry";
            case 10013: return "Check trading permissions and account status";
            case 10014: return "Wait for market opening hours";
            case 10015: return "Check account balance and margin requirements";
            case 10016: case 10017: return "Update price and retry";
            case 10018: case 10022: return "Reduce request frequency and retry";
            default: return "Review error details and adjust parameters";
        }
    }
};

//+------------------------------------------------------------------+
//| Global error handler instance                                    |
//+------------------------------------------------------------------+
CErrorHandler* GlobalErrorHandler = NULL;

//+------------------------------------------------------------------+
//| Error handler initialization                                     |
//+------------------------------------------------------------------+
void InitializeGlobalErrorHandler(bool autoRecovery = true) {
    if(GlobalErrorHandler == NULL) {
        GlobalErrorHandler = new CErrorHandler();
        GlobalErrorHandler.SetAutoRecovery(autoRecovery);
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global error handler initialized", "ErrorHandler");
        }
    }
}

//+------------------------------------------------------------------+
//| Error handler cleanup                                            |
//+------------------------------------------------------------------+
void CleanupGlobalErrorHandler() {
    if(GlobalErrorHandler != NULL) {
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global error handler cleanup", "ErrorHandler");
        }
        delete GlobalErrorHandler;
        GlobalErrorHandler = NULL;
    }
}

#endif