// Execution/BrokerInterface.mqh
#ifndef BROKERINTERFACE_MQH
#define BROKERINTERFACE_MQH

#include "..\Utilities\Logger.mqh"
#include "..\Utilities\ErrorHandler.mqh"
#include "..\Data\SymbolInfo.mqh"
#include "OrderTypes.mqh"

//+------------------------------------------------------------------+
//| Broker execution modes                                           |
//+------------------------------------------------------------------+
enum ENUM_BROKER_EXECUTION {
    BROKER_EXECUTION_MARKET,      // Market execution
    BROKER_EXECUTION_INSTANT,     // Instant execution
    BROKER_EXECUTION_REQUEST      // Execution by request
};

//+------------------------------------------------------------------+
//| Broker fee structure                                             |
//+------------------------------------------------------------------+
struct SBrokerFees {
    double commissionPerLot;      // Commission per lot
    double commissionPerTrade;    // Fixed commission per trade
    double minCommission;         // Minimum commission
    double maxCommission;         // Maximum commission
    bool   commissionInPips;      // Commission expressed in pips
};

//+------------------------------------------------------------------+
//| CBrokerInterface - MT5 broker adaptation                        |
//+------------------------------------------------------------------+
class CBrokerInterface {
private:
    // Components
    CLogger*            m_logger;
    CErrorHandler*      m_errorHandler;
    CSymbolInfo*        m_symbolInfo;
    
    // Broker configuration
    string              m_brokerName;
    ENUM_BROKER_EXECUTION m_executionMode;
    SBrokerFees         m_fees;
    
    // MT5 specific
    bool                m_supportsHedging;
    bool                m_supportsNetting;
    int                 m_maxSlippage;
    int                 m_maxRetries;
    int                 m_retryDelay;
    
    // Execution tracking
    int                 m_totalExecutions;
    int                 m_failedExecutions;
    datetime            m_lastExecutionTime;
    
public:
    // Constructor/Destructor
    CBrokerInterface();
    ~CBrokerInterface();
    
    // Initialization
    bool Initialize();
    void Deinitialize();
    
    // Broker detection and configuration
    bool DetectBroker();
    void ConfigureBrokerSettings();
    SBrokerFees GetCurrentFees() const;
    
    // Core execution methods
    STradeResult ExecuteMarketOrder(const STradeRequest &request);
    STradeResult ExecutePendingOrder(const STradeRequest &request);
    STradeResult ClosePosition(ulong ticket, double volume = 0);
    
    // Order management
    bool ModifyPosition(ulong ticket, double sl, double tp);
    bool DeletePendingOrder(ulong ticket);
    
    // Execution quality
    double GetExecutionQuality(string symbol);
    double GetAverageSlippage(string symbol);
    int GetExecutionSpeed(string symbol); // in milliseconds
    
    // Broker information
    string GetBrokerName() const { return m_brokerName; }
    ENUM_BROKER_EXECUTION GetExecutionMode() const { return m_executionMode; }
    bool SupportsHedging() const { return m_supportsHedging; }
    bool SupportsNetting() const { return m_supportsNetting; }
    
    // Error handling
    string TranslateErrorCode(int errorCode);
    bool IsRecoverableError(int errorCode);
    bool ShouldRetryExecution(int errorCode, int attemptCount);
    int GetRecommendedRetryDelay(int errorCode);
    
    // Statistics
    int GetSuccessRate() const;
    void PrintBrokerInfo();
    
private:
    // Internal MT5 execution
    STradeResult ExecuteOrderMT5(const STradeRequest &request);
    STradeResult ClosePositionMT5(ulong ticket, double volume);
    
    // Fee calculations
    double CalculateCommission(const STradeRequest &request);
    double CalculateSwap(const STradeRequest &request);
    
    // Execution optimization
    double GetOptimalPrice(ENUM_ORDER_TYPE type, string symbol);
    int GetOptimalSlippage(string symbol, ENUM_ORDER_TYPE type, double volume);
    
    // Market condition checks
    bool IsMarketOpen(string symbol);
    bool IsSpreadNormal(string symbol);
    bool IsPriceStable(string symbol);
};
#endif