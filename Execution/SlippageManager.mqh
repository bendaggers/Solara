// Execution/SlippageManager.mqh
#ifndef SLIPPAGEMANAGER_MQH
#define SLIPPAGEMANAGER_MQH

#include "..\Utilities\Logger.mqh"
#include "..\Data\MarketData.mqh"
#include "OrderTypes.mqh"

//+------------------------------------------------------------------+
//| CSlippageManager - Execution quality monitoring                 |
//+------------------------------------------------------------------+
class CSlippageManager {
private:
    CLogger*            m_logger;
    CMarketData*        m_marketData;
    
    // Slippage tracking
    struct SSlippageRecord {
        datetime timestamp;
        string symbol;
        ENUM_ORDER_TYPE orderType;
        double expectedPrice;
        double executedPrice;
        double slippagePips;
        double volume;
        double spreadAtExecution;
    };
    
    SSlippageRecord     m_slippageHistory[100];
    int                 m_historyIndex;
    
    // Configuration
    double              m_maxAllowedSlippage;  // Max slippage in pips
    bool                m_monitorSlippage;
    bool                m_logSlippageEvents;
    
public:
    // Constructor/Destructor
    CSlippageManager();
    ~CSlippageManager();
    
    // Initialization
    bool Initialize(CMarketData* marketData = NULL);
    void Deinitialize();
    
    // Slippage estimation and monitoring
    double EstimateSlippage(string symbol, ENUM_ORDER_TYPE type, double volume);
    void RecordExecution(ulong ticket, double expectedPrice, double executedPrice, 
                        string symbol, ENUM_ORDER_TYPE type, double volume);
    
    // Execution quality analysis
    double GetAverageSlippage(string symbol, ENUM_ORDER_TYPE type = 0, int period = 20);
    double GetMaxSlippage(string symbol, int period = 100);
    double GetSlippageStdDev(string symbol, int period = 20);
    double GetExecutionQualityScore(string symbol);
    
    // Market condition analysis
    bool IsHighSlippagePeriod(string symbol);
    bool ShouldDelayExecution(string symbol, double volume);
    double GetOptimalExecutionTime(string symbol);
    
    // Configuration
    void SetMaxAllowedSlippage(double pips);
    void SetMonitorSlippage(bool monitor);
    void SetLogSlippageEvents(bool log);
    
    // Reporting
    void PrintSlippageReport();
    string GetSlippageSummary();
    
private:
    // Internal calculations
    double CalculateMarketImpact(string symbol, double volume);
    double CalculateExpectedSpread(string symbol);
    double CalculateVolatilityFactor(string symbol);
    
    // Historical analysis
    void AnalyzeSlippagePatterns();
    bool DetectSlippageSpikes(string symbol);
    
    // Helper methods
    double PipsToPrice(string symbol, double pips);
    double PriceToPips(string symbol, double priceDifference);
    double GetCurrentSpread(string symbol);
};
#endif