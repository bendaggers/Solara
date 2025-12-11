//+------------------------------------------------------------------+
//| MoneyManagerBase.mqh - FIXED VERSION 2                           |
//+------------------------------------------------------------------+
#ifndef MONEYMANAGERBASE_MQH
#define MONEYMANAGERBASE_MQH

// Include required dependencies
#include "..\Configuration\StrategyConfig.mqh"
#include "..\Data\SymbolInfo.mqh"
#include "..\Core\RiskManager.mqh"
#include "..\Utilities\Logger.mqh"

// Forward declarations
class CSymbolInfo;
class CRiskManager;

//+------------------------------------------------------------------+
//| Money management method enumeration                              |
//+------------------------------------------------------------------+
enum ENUM_MONEY_MANAGEMENT {
    MM_FIXED_FRACTIONAL = 0,
    MM_FIXED_RATIO = 1,
    MM_KELLY_CRITERION = 2,
    MM_VOLATILITY_BASED = 3,
    MM_FIXED_LOT = 4,
    MM_CUSTOM = 5
};

//+------------------------------------------------------------------+
//| Money manager configuration structure                            |
//+------------------------------------------------------------------+
struct SMoneyManagerConfig {
    ENUM_MONEY_MANAGEMENT method;
    double riskPercent;
    double fixedLotSize;
    double maxRiskPerTrade;
    double maxPositionSizePercent;
    bool useEquityInsteadOfBalance;
    bool applyRiskMultiplier;
    bool validateWithSymbolInfo;
    bool roundToLotStep;
    
    // Method-specific parameters
    double kellyFraction;
    double volatilityPeriod;
    double volatilityMultiplier;
    double fixedRatioDelta;
    
    SMoneyManagerConfig() {
        method = MM_FIXED_FRACTIONAL;
        riskPercent = 1.0;
        fixedLotSize = 0.01;
        maxRiskPerTrade = 0.0;
        maxPositionSizePercent = 2.0;
        useEquityInsteadOfBalance = false;
        applyRiskMultiplier = true;
        validateWithSymbolInfo = true;
        roundToLotStep = true;
        kellyFraction = 0.25;
        volatilityPeriod = 14;
        volatilityMultiplier = 1.0;
        fixedRatioDelta = 1000.0;
    }
    
    // Validation method
    bool Validate() const {
        if(riskPercent < 0.01 || riskPercent > 10.0) {
            return false;
        }
        if(fixedLotSize < 0.01) {
            return false;
        }
        if(maxPositionSizePercent <= 0 || maxPositionSizePercent > 100.0) {
            return false;
        }
        if(kellyFraction <= 0 || kellyFraction > 1.0) {
            return false;
        }
        if(volatilityPeriod < 5 || volatilityPeriod > 100) {
            return false;
        }
        return true;
    }
    
    // Get method as string
    string GetMethodString() const {
        switch(method) {
            case MM_FIXED_FRACTIONAL: return "Fixed Fractional";
            case MM_FIXED_RATIO: return "Fixed Ratio";
            case MM_KELLY_CRITERION: return "Kelly Criterion";
            case MM_VOLATILITY_BASED: return "Volatility Based";
            case MM_FIXED_LOT: return "Fixed Lot";
            case MM_CUSTOM: return "Custom";
            default: return "Unknown";
        }
    }
};

//+------------------------------------------------------------------+
//| Strategy config wrapper class                                    |
//+------------------------------------------------------------------+
class CStrategyConfigWrapper {
private:
    SStrategyConfig m_config;
    bool m_hasConfig;
    
public:
    CStrategyConfigWrapper() : m_hasConfig(false) {}
    
    void SetConfig(const SStrategyConfig &config) {
        m_config = config;
        m_hasConfig = true;
    }
    
    bool HasConfig() const {
        return m_hasConfig;
    }
    
    SStrategyConfig GetConfig() const {
        return m_config;
    }
    
    double GetRiskPercent() const {
        return m_hasConfig ? m_config.riskPercent : 0.0;
    }
    
    string GetStrategyName() const {
        return m_hasConfig ? m_config.strategyName : "";
    }
    
    bool IsEnabled() const {
        return m_hasConfig ? m_config.enabled : false;
    }
};

//+------------------------------------------------------------------+
//| Calculation parameters structure                                 |
//+------------------------------------------------------------------+
struct SCalcParams {
    string symbol;
    double entryPrice;
    double stopLossPrice;
    double takeProfitPrice;
    ENUM_ORDER_TYPE orderType;
    double accountBalance;
    double accountEquity;
    string strategyName;
    int magicNumber;
    double volatility;
    double winRate;
    double avgWinLossRatio;
    
    SCalcParams() {
        symbol = "";
        entryPrice = 0.0;
        stopLossPrice = 0.0;
        takeProfitPrice = 0.0;
        orderType = ORDER_TYPE_BUY;
        accountBalance = 0.0;
        accountEquity = 0.0;
        strategyName = "";
        magicNumber = 0;
        volatility = 0.0;
        winRate = 0.5;
        avgWinLossRatio = 1.0;
    }
};

//+------------------------------------------------------------------+
//| Calculation result structure                                     |
//+------------------------------------------------------------------+
struct SCalcResult {
    bool success;
    double lotSize;
    double riskAmount;
    double riskPercent;
    double positionValue;
    double stopLossPips;
    double positionSizePercent;
    string errorMessage;
    datetime calculationTime;
    
    SCalcResult() {
        success = false;
        lotSize = 0.0;
        riskAmount = 0.0;
        riskPercent = 0.0;
        positionValue = 0.0;
        stopLossPips = 0.0;
        positionSizePercent = 0.0;
        errorMessage = "";
        calculationTime = 0;
    }
};

//+------------------------------------------------------------------+
//| CMoneyManagerBase - Abstract base class                          |
//+------------------------------------------------------------------+
class CMoneyManagerBase {
protected:
    // Configuration
    SMoneyManagerConfig m_config;
    CStrategyConfigWrapper m_strategyConfig;
    
    // Dependencies
    CSymbolInfo* m_symbolInfo;
    CRiskManager* m_riskManager;
    CLogger* m_logger;
    
    // State
    bool m_initialized;
    double m_lastAccountBalance;
    double m_lastAccountEquity;
    datetime m_lastUpdateTime;
    
    // Performance tracking
    int m_calculationCount;
    double m_totalRiskCalculated;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CMoneyManagerBase() :
        m_symbolInfo(NULL),
        m_riskManager(NULL),
        m_logger(NULL),
        m_initialized(false),
        m_lastAccountBalance(0.0),
        m_lastAccountEquity(0.0),
        m_lastUpdateTime(0),
        m_calculationCount(0),
        m_totalRiskCalculated(0.0)
    {
    }
    
    virtual ~CMoneyManagerBase() {
        Deinitialize();
    }
    
    //+------------------------------------------------------------------+
    //| Initialization methods                                           |
    //+------------------------------------------------------------------+
    virtual bool Initialize(CSymbolInfo* symbolInfo = NULL, 
                           CRiskManager* riskManager = NULL,
                           CLogger* logger = NULL) {
        if(m_initialized) {
            LogInfo("Money Manager already initialized");
            return true;
        }
        
        LogInfo("Initializing Money Manager Base...");
        
        // Set dependencies
        m_symbolInfo = symbolInfo;
        m_riskManager = riskManager;
        m_logger = logger;
        
        // Validate configuration
        if(!m_config.Validate()) {
            LogError("Invalid money manager configuration");
            return false;
        }
        
        // Update account information
        UpdateAccountInfo();
        
        m_initialized = true;
        LogInfo("Money Manager Base initialized successfully");
        LogInfo("Method: " + m_config.GetMethodString());
        
        return true;
    }
    
    virtual void Deinitialize() {
        if(!m_initialized) return;
        
        LogInfo("Deinitializing Money Manager...");
        
        m_symbolInfo = NULL;
        m_riskManager = NULL;
        m_logger = NULL;
        m_strategyConfig = CStrategyConfigWrapper(); // Reset wrapper
        
        m_initialized = false;
        
        LogInfo("Money Manager deinitialized");
    }
    
    //+------------------------------------------------------------------+
    //| Core calculation interface - Pure virtual functions              |
    //+------------------------------------------------------------------+
    virtual SCalcResult CalculatePositionSize(const SCalcParams &params) = 0;
    
    virtual double CalculateRiskAmount(const SCalcParams &params) = 0;
    
    virtual double CalculateOptimalLotSize(double riskAmount, const SCalcParams &params) = 0;
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetConfig(const SMoneyManagerConfig &config) {
        if(config.Validate()) {
            m_config = config;
            LogInfo("Money manager configuration updated");
        } else {
            LogError("Failed to set invalid configuration");
        }
    }
    
    SMoneyManagerConfig GetConfig() const {
        return m_config;
    }
    
    void SetStrategyConfig(const SStrategyConfig &strategyConfig) {
        m_strategyConfig.SetConfig(strategyConfig);
        
        // Override risk percent from strategy config if available
        if(m_strategyConfig.HasConfig() && m_strategyConfig.GetRiskPercent() > 0) {
            m_config.riskPercent = m_strategyConfig.GetRiskPercent();
            LogInfo("Updated risk percent from strategy config: " + 
                    DoubleToString(m_strategyConfig.GetRiskPercent(), 2) + "%");
        }
    }
    
    bool HasStrategyConfig() const {
        return m_strategyConfig.HasConfig();
    }
    
    SStrategyConfig GetStrategyConfig() const {
        return m_strategyConfig.GetConfig();
    }
    
    //+------------------------------------------------------------------+
    //| Utility methods                                                  |
    //+------------------------------------------------------------------+
    void UpdateAccountInfo() {
        m_lastAccountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
        m_lastAccountEquity = AccountInfoDouble(ACCOUNT_EQUITY);
        m_lastUpdateTime = TimeCurrent();
        
        LogDebug("Account info updated - Balance: " + DoubleToString(m_lastAccountBalance, 2) + 
                 ", Equity: " + DoubleToString(m_lastAccountEquity, 2));
    }
    
    double GetAccountBalance(bool useEquity = false) const {
        if(useEquity || m_config.useEquityInsteadOfBalance) {
            return m_lastAccountEquity;
        }
        return m_lastAccountBalance;
    }
    
    double GetRiskMultiplier() const {
        if(m_riskManager != NULL && m_config.applyRiskMultiplier) {
            return m_riskManager.GetRiskMultiplier();
        }
        return 1.0;
    }
    
    //+------------------------------------------------------------------+
    //| Validation methods                                               |
    //+------------------------------------------------------------------+
    bool ValidateCalculationParams(const SCalcParams &params) {
        if(params.symbol == "" || params.symbol == NULL) {
            LogError("Invalid calculation parameters: Symbol is empty");
            return false;
        }
        
        if(params.entryPrice <= 0) {
            LogError("Invalid calculation parameters: Entry price must be positive");
            return false;
        }
        
        if(params.stopLossPrice <= 0) {
            LogError("Invalid calculation parameters: Stop loss price must be positive");
            return false;
        }
        
        if(params.accountBalance <= 0) {
            LogError("Invalid calculation parameters: Account balance must be positive");
            return false;
        }
        
        if(params.accountEquity <= 0) {
            LogError("Invalid calculation parameters: Account equity must be positive");
            return false;
        }
        
        if(!m_initialized) {
            LogError("Money manager not initialized");
            return false;
        }
        
        return true;
    }
    
    bool ValidateLotSize(string symbol, double lotSize) {
        if(!m_config.validateWithSymbolInfo || m_symbolInfo == NULL) {
            return (lotSize > 0);
        }
        
        return m_symbolInfo.ValidateVolume(lotSize);
    }
    
    double ApplyLotSizeLimits(string symbol, double lotSize) {
        if(lotSize <= 0) return 0.0;
        
        double result = lotSize;
        
        // Apply SymbolInfo limits if available
        if(m_symbolInfo != NULL && m_config.validateWithSymbolInfo) {
            double minLot = (double)m_symbolInfo.GetVolumeMin();
            double maxLot = (double)m_symbolInfo.GetVolumeMax();
            double lotStep = (double)m_symbolInfo.GetVolumeStep();
            
            // Ensure within min/max
            result = MathMax(result, minLot);
            result = MathMin(result, maxLot);
            
            // Round to lot step
            if(m_config.roundToLotStep && lotStep > 0) {
                result = MathRound(result / lotStep) * lotStep;
            }
        }
        
        // Apply position size percentage limit
        double maxPositionByPercent = (m_config.maxPositionSizePercent / 100.0) * 
                                      GetAccountBalance(m_config.useEquityInsteadOfBalance);
        
        // Convert lot size to position value
        double contractSize = 1.0;
        double price = SymbolInfoDouble(symbol, SYMBOL_ASK);
        
        if(m_symbolInfo != NULL) {
            contractSize = m_symbolInfo.GetContractSize();
        } else {
            contractSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
        }
        
        double positionValue = result * contractSize * price;
        
        if(positionValue > maxPositionByPercent && maxPositionByPercent > 0) {
            result = maxPositionByPercent / (contractSize * price);
            
            // Re-apply rounding if needed
            if(m_symbolInfo != NULL && m_config.roundToLotStep) {
                double lotStep = (double)m_symbolInfo.GetVolumeStep();
                if(lotStep > 0) {
                    result = MathRound(result / lotStep) * lotStep;
                }
            }
        }
        
        return result;
    }
    
    //+------------------------------------------------------------------+
    //| Calculation helpers                                              |
    //+------------------------------------------------------------------+
    double CalculateStopLossPips(string symbol, double entryPrice, 
                                double stopLossPrice, ENUM_ORDER_TYPE orderType) {
        if(entryPrice == 0 || stopLossPrice == 0) return 0.0;
        
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        if(point <= 0) return 0.0;
        
        double stopDistance = MathAbs(entryPrice - stopLossPrice);
        return stopDistance / point;
    }
    
    double CalculateRiskPerPip(string symbol, double lotSize) {
        double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
        double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        
        if(tickValue <= 0 || tickSize <= 0 || point <= 0) return 0.0;
        
        // Calculate value per pip
        double valuePerTick = lotSize * tickValue;
        double ticksPerPoint = point / tickSize;
        double valuePerPoint = valuePerTick * ticksPerPoint;
        
        // For most pairs, 1 pip = 10 points
        double pipsPerPoint = (point == 0.00001) ? 10.0 : 1.0;
        
        return valuePerPoint * pipsPerPoint;
    }
    
    //+------------------------------------------------------------------+
    //| Performance tracking                                             |
    //+------------------------------------------------------------------+
    void RecordCalculation(const SCalcResult &result) {
        if(result.success) {
            m_calculationCount++;
            m_totalRiskCalculated += result.riskAmount;
        }
    }
    
    int GetCalculationCount() const {
        return m_calculationCount;
    }
    
    double GetTotalRiskCalculated() const {
        return m_totalRiskCalculated;
    }
    
    double GetAverageRiskPerTrade() const {
        if(m_calculationCount > 0) {
            return m_totalRiskCalculated / m_calculationCount;
        }
        return 0.0;
    }
    
    //+------------------------------------------------------------------+
    //| Information and debugging                                        |
    //+------------------------------------------------------------------+
    virtual string GetName() const {
        return "MoneyManagerBase";
    }
    
    virtual string GetDescription() const {
        return "Abstract base class for position sizing methods";
    }
    
    void PrintStatus() {
        string status = "=== Money Manager Status ===\n" +
                       "Name: " + GetName() + "\n" +
                       "Method: " + m_config.GetMethodString() + "\n" +
                       "Initialized: " + (m_initialized ? "Yes" : "No") + "\n" +
                       "Risk Percent: " + DoubleToString(m_config.riskPercent, 2) + "%\n" +
                       "Risk Multiplier: " + DoubleToString(GetRiskMultiplier(), 2) + "\n" +
                       "Account Balance: " + DoubleToString(m_lastAccountBalance, 2) + "\n" +
                       "Account Equity: " + DoubleToString(m_lastAccountEquity, 2) + "\n" +
                       "Has Strategy Config: " + (m_strategyConfig.HasConfig() ? "Yes" : "No") + "\n" +
                       "Calculations Performed: " + IntegerToString(m_calculationCount) + "\n" +
                       "Total Risk Calculated: " + DoubleToString(m_totalRiskCalculated, 2) + "\n" +
                       "===========================";
        
        LogInfo(status);
    }
    
protected:
    //+------------------------------------------------------------------+
    //| Protected helper methods                                         |
    //+------------------------------------------------------------------+
    double GetEffectiveRiskPercent() const {
        double baseRisk = m_config.riskPercent;
        
        // Apply risk multiplier from RiskManager
        double riskMultiplier = GetRiskMultiplier();
        
        // Apply strategy-specific risk if available
        if(m_strategyConfig.HasConfig() && m_strategyConfig.GetRiskPercent() > 0) {
            baseRisk = m_strategyConfig.GetRiskPercent();
        }
        
        return baseRisk * riskMultiplier;
    }
    
    double GetBaseRiskAmount() const {
        double accountValue = GetAccountBalance(m_config.useEquityInsteadOfBalance);
        double effectiveRiskPercent = GetEffectiveRiskPercent();
        
        return accountValue * (effectiveRiskPercent / 100.0);
    }
    
    //+------------------------------------------------------------------+
    //| Logging methods                                                  |
    //+------------------------------------------------------------------+
    void LogError(string message) {
        if(m_logger != NULL) {
            m_logger.Error(message, GetName());
        } else {
            Print("ERROR [" + GetName() + "]: " + message);
        }
    }
    
    void LogWarn(string message) {
        if(m_logger != NULL) {
            m_logger.Warn(message, GetName());
        }
    }
    
    void LogInfo(string message) {
        if(m_logger != NULL) {
            m_logger.Info(message, GetName());
        }
    }
    
    void LogDebug(string message) {
        if(m_logger != NULL) {
            m_logger.Debug(message, GetName());
        }
    }
};

#endif // MONEYMANAGERBASE_MQH