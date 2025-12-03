// Execution/OrderExecutor.mqh
#ifndef ORDEREXECUTOR_MQH
#define ORDEREXECUTOR_MQH

#include "..\Utilities\Logger.mqh"
#include "..\Utilities\ErrorHandler.mqh"
#include "..\Core\PositionManager.mqh"
#include "OrderValidator.mqh"
#include "BrokerInterface.mqh"
#include "SlippageManager.mqh"
#include "OrderTypes.mqh"

//+------------------------------------------------------------------+
//| Execution state machine                                          |
//+------------------------------------------------------------------+
enum ENUM_EXECUTION_STATE {
    STATE_IDLE,                 // Ready for new execution
    STATE_VALIDATING,           // Validating trade request
    STATE_EXECUTING,            // Executing with broker
    STATE_CONFIRMING,           // Confirming execution
    STATE_UPDATING,             // Updating position manager
    STATE_ERROR,                // Error occurred
    STATE_RETRYING,             // Retrying execution
    STATE_COMPLETED             // Execution completed
};

//+------------------------------------------------------------------+
//| COrderExecutor - Main execution engine                          |
//+------------------------------------------------------------------+
class COrderExecutor {
private:
    // Component references
    CLogger*            m_logger;
    CErrorHandler*      m_errorHandler;
    CPositionManager*   m_positionManager;
    COrderValidator*    m_validator;
    CBrokerInterface*   m_broker;
    CSlippageManager*   m_slippageManager;
    
    // Execution configuration
    ENUM_EXECUTION_MODE m_executionMode;
    bool                m_asyncExecution;     // Asynchronous execution
    bool                m_requireConfirmation;// Require execution confirmation
    int                 m_maxRetries;         // Max retry attempts
    int                 m_retryDelay;         // Delay between retries (ms)
    int                 m_executionTimeout;   // Timeout for execution (ms)
    
    // Execution state
    ENUM_EXECUTION_STATE m_currentState;
    STradeRequest        m_currentRequest;
    STradeResult         m_currentResult;
    int                  m_currentRetry;
    datetime             m_executionStartTime;
    
    // Execution queue (for async)
    STradeRequest        m_executionQueue[];
    bool                 m_isProcessingQueue;
    
    // Metrics and reporting
    SExecutionMetrics    m_metrics;
    SExecutionEvent      m_lastEvents[20];
    int                  m_eventIndex;
    
public:
    // Constructor/Destructor
    COrderExecutor();
    ~COrderExecutor();
    
    // Initialization
    bool Initialize(CPositionManager* posMgr = NULL);
    void Deinitialize();
    
    // Core execution methods (Synchronous interface)
    STradeResult ExecuteTrade(const STradeRequest &request);
    STradeResult CloseTrade(ulong ticket, double volume = 0, string comment = "");
    STradeResult CloseAllTrades(string symbol = "", ulong magic = 0);
    
    // Async execution methods
    bool QueueTrade(const STradeRequest &request);
    bool ProcessQueue();
    int GetQueueSize() const;
    void ClearQueue();
    
    // Execution control
    void SetExecutionMode(ENUM_EXECUTION_MODE mode);
    void SetAsyncExecution(bool async);
    void SetRequireConfirmation(bool require);
    void SetMaxRetries(int retries);
    void SetRetryDelay(int milliseconds);
    void SetExecutionTimeout(int milliseconds);
    
    // Event handlers (to be called from OnTick/OnTimer)
    void OnTick();
    void OnTimer();
    void OnTradeTransaction(const MqlTradeTransaction &trans,
                           const MqlTradeRequest &request,
                           const MqlTradeResult &result);
    
    // Execution state
    ENUM_EXECUTION_STATE GetCurrentState() const { return m_currentState; }
    bool IsBusy() const { return m_currentState != STATE_IDLE; }
    bool IsQueueProcessing() const { return m_isProcessingQueue; }
    
    // Metrics and reporting
    SExecutionMetrics GetMetrics() const { return m_metrics; }
    void ResetMetrics();
    void PrintExecutionReport();
    bool GetRecentEvents(SExecutionEvent &events[], int count = 10);
    
    // Component access
    COrderValidator* GetValidator() const { return m_validator; }
    CBrokerInterface* GetBrokerInterface() const { return m_broker; }
    CSlippageManager* GetSlippageManager() const { return m_slippageManager; }
    
private:
    // Execution state machine
    void ProcessStateMachine();
    void ChangeState(ENUM_EXECUTION_STATE newState);
    
    // State handlers
    void HandleIdleState();
    void HandleValidatingState();
    void HandleExecutingState();
    void HandleConfirmingState();
    void HandleUpdatingState();
    void HandleErrorState();
    void HandleRetryingState();
    
    // Execution steps
    SValidationResult ValidateTrade();
    STradeResult ExecuteWithBroker();
    bool ConfirmExecution();
    bool UpdatePositionManager();
    bool HandleExecutionError();
    
    // Async queue processing
    void ProcessNextInQueue();
    void AddToQueue(const STradeRequest &request);
    STradeRequest GetNextFromQueue();
    
    // Event recording

    void RecordEvent(ENUM_EXECUTION_EVENT eventType, 
                    const STradeRequest &request, 
                    const STradeResult &result, 
                    int errorCode);
    void RecordEvent(ENUM_EXECUTION_EVENT eventType, int errorCode = 0);
    void RecordEvent(ENUM_EXECUTION_EVENT eventType, const STradeRequest &request, int errorCode = 0);
    void RecordEvent(ENUM_EXECUTION_EVENT eventType, const STradeResult &result, int errorCode = 0);
    void RecordExecutionMetrics(const STradeResult &result);
    
    // Helper methods
    bool ShouldRetryExecution(const STradeResult &result);
    void PrepareForRetry();
    void CleanupAfterExecution();
    
    // Logging
    void LogExecution(const STradeRequest &request, const STradeResult &result);
    void LogStateChange(ENUM_EXECUTION_STATE oldState, ENUM_EXECUTION_STATE newState);
};
#endif