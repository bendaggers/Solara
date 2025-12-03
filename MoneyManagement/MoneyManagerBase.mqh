//+------------------------------------------------------------------+
//| MoneyManagerBase.mqh                                             |
//| Description: Abstract base class for all position sizing methods |
//|              Integrates with StrategyConfig, SymbolInfo, and     |
//|              RiskManager                                         |
//+------------------------------------------------------------------+
#ifndef MONEYMANAGERBASE_MQH
#define MONEYMANAGERBASE_MQH

// Include required dependencies from your existing files
#include "..\Configuration\StrategyConfig.mqh"
#include "..\Data\SymbolInfo.mqh"
#include "..\Core\RiskManager.mqh"
#include "..\Utilities\Logger.mqh"

// Forward declarations to avoid circular dependencies
class CSymbolInfo;
class CRiskManager;

//+------------------------------------------------------------------+
//| Money management method enumeration                              |
//+------------------------------------------------------------------+
enum ENUM_MONEY_MANAGEMENT {
    MM_FIXED_FRACTIONAL = 0,    // Fixed % of account per trade
    MM_FIXED_RATIO = 1,         // Fixed ratio position sizing
    MM_KELLY_CRITERION = 2,     // Kelly criterion optimization
    MM_VOLATILITY_BASED = 3,    // ATR/volatility based sizing
    MM_FIXED_LOT = 4,           // Fixed lot size (for testing)
    MM_CUSTOM = 5               // Custom implementation
};

//+------------------------------------------------------------------+
//| Money manager configuration structure                            |
//+------------------------------------------------------------------+
struct SMoneyManagerConfig {
    ENUM_MONEY_MANAGEMENT method;           // Money management method
    double riskPercent;                     // Risk % per trade (0.1-5.0)
    double fixedLotSize;                    // Fixed lot size (if using fixed lots)
    double maxRiskPerTrade;                 // Maximum risk amount in account currency
    double maxPositionSizePercent;          // Max position size as % of balance
    bool useEquityInsteadOfBalance;         // Use equity instead of balance for calculations
    bool applyRiskMultiplier;               // Apply risk multiplier from RiskManager
    bool validateWithSymbolInfo;            // Validate lot sizes with SymbolInfo
    bool roundToLotStep;                    // Round to symbol's lot step
    
    // Method-specific parameters
    double kellyFraction;                   // Fraction of full Kelly (0.1-1.0)
    double volatilityPeriod;                // Period for volatility calculation
    double volatilityMultiplier;            // Multiplier for volatility sizing
    double fixedRatioDelta;                 // Delta for fixed ratio method
    
    SMoneyManagerConfig() {
        method = MM_FIXED_FRACTIONAL;
        riskPercent = 1.0;
        fixedLotSize = 0.01;
        maxRiskPerTrade = 0.0;              // 0 = no limit
        maxPositionSizePercent = 2.0;
        useEquityInsteadOfBalance = false;
        applyRiskMultiplier = true;
        validateWithSymbolInfo = true;
        roundToLotStep = true;
        kellyFraction = 0.25;               // 25% of full Kelly (conservative)
        volatilityPeriod = 14;
        volatilityMultiplier = 1.0;
        fixedRatioDelta = 1000.0;
    }
    
    // Validation method
    bool Validate() const {
        if(riskPercent < 0.01 || riskPercent > 10.0) {
            Print("Error: riskPercent must be between 0.01 and 10.0");
            return false;
        }
        
        if(fixedLotSize < 0.01) {
            Print("Error: fixedLotSize must be at least 0.01");
            return false;
        }
        
        if(maxPositionSizePercent <= 0 || maxPositionSizePercent > 100.0) {
            Print("Error: maxPositionSizePercent must be between 0.1 and 100.0");
            return false;
        }
        
        if(kellyFraction <= 0 || kellyFraction > 1.0) {
            Print("Error: kellyFraction must be between 0.01 and 1.0");
            return false;
        }
        
        if(volatilityPeriod < 5 || volatilityPeriod > 100) {
            Print("Error: volatilityPeriod must be between 5 and 100");
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
    
    // Print configuration
    void PrintConfig() const {
        Print("=== Money Manager Configuration ===");
        Print("Method: ", GetMethodString());
        Print("Risk Percent: ", riskPercent, "%");
        Print("Max Position Size: ", maxPositionSizePercent, "%");
        Print("Use Equity: ", useEquityInsteadOfBalance ? "Yes" : "No");
        Print("Apply Risk Multiplier: ", applyRiskMultiplier ? "Yes" : "No");
        Print("Validate with SymbolInfo: ", validateWithSymbolInfo ? "Yes" : "No");
        
        if(method == MM_FIXED_LOT) {
            Print("Fixed Lot Size: ", fixedLotSize);
        }
        
        if(method == MM_KELLY_CRITERION) {
            Print("Kelly Fraction: ", kellyFraction);
        }
        
        if(method == MM_VOLATILITY_BASED) {
            Print("Volatility Period: ", volatilityPeriod);
            Print("Volatility Multiplier: ", volatilityMultiplier);
        }
        
        if(method == MM_FIXED_RATIO) {
            Print("Fixed Ratio Delta: ", fixedRatioDelta);
        }
        
        Print("================================");
    }
};

//+------------------------------------------------------------------+
//| Calculation parameters structure                                 |
//+------------------------------------------------------------------+
struct SCalcParams {
    string symbol;                          // Trading symbol
    double entryPrice;                      // Entry price
    double stopLossPrice;                   // Stop loss price
    double takeProfitPrice;                 // Take profit price (optional)
    ENUM_ORDER_TYPE orderType;              // Order type
    double accountBalance;                  // Current account balance
    double accountEquity;                   // Current account equity
    string strategyName;                    // Strategy name (for strategy-specific config)
    int magicNumber;                        // Magic number
    double volatility;                      // Current volatility (ATR)
    double winRate;                         // Strategy win rate (for Kelly)
    double avgWinLossRatio;                 // Average win/loss ratio (for Kelly)
    
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
        winRate = 0.5;                      // Default 50% win rate
        avgWinLossRatio = 1.0;              // Default 1:1 win/loss ratio
    }
    
    // Validation
    bool Validate() const {
        if(StringLen(symbol) == 0) {
            Print("Error: Symbol cannot be empty");
            return false;
        }
        
        if(entryPrice <= 0) {
            Print("Error: Entry price must be positive");
            return false;
        }
        
        if(stopLossPrice <= 0) {
            Print("Error: Stop loss price must be positive");
            return false;
        }
        
        if(accountBalance <= 0) {
            Print("Error: Account balance must be positive");
            return false;
        }
        
        if(accountEquity <= 0) {
            Print("Error: Account equity must be positive");
            return false;
        }
        
        // Check that stop loss is on correct side of entry
        if(orderType == ORDER_TYPE_BUY || orderType == ORDER_TYPE_BUY_LIMIT || 
           orderType == ORDER_TYPE_BUY_STOP) {
            if(stopLossPrice >= entryPrice) {
                Print("Error: For buy orders, stop loss must be below entry price");
                return false;
            }
        } else {
            if(stopLossPrice <= entryPrice) {
                Print("Error: For sell orders, stop loss must be above entry price");
                return false;
            }
        }
        
        return true;
    }
};

//+------------------------------------------------------------------+
//| Calculation result structure                                     |
//+------------------------------------------------------------------+
struct SCalcResult {
    bool success;                           // Calculation success flag
    double lotSize;                         // Calculated lot size
    double riskAmount;                      // Risk amount in account currency
    double riskPercent;                     // Risk as % of account
    double positionValue;                   // Position value in account currency
    double stopLossPips;                    // Stop loss in pips
    double positionSizePercent;             // Position size as % of account
    string errorMessage;                    // Error message if calculation failed
    datetime calculationTime;               // Time of calculation
    
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
    
    // Print result
    void PrintResult() const {
        if(success) {
            Print("=== Money Manager Calculation Result ===");
            Print("Success: Yes");
            Print("Lot Size: ", lotSize);
            Print("Risk Amount: ", DoubleToString(riskAmount, 2));
            Print("Risk Percent: ", DoubleToString(riskPercent, 2), "%");
            Print("Position Value: ", DoubleToString(positionValue, 2));
            Print("Stop Loss Pips: ", DoubleToString(stopLossPips, 1));
            Print("Position Size %: ", DoubleToString(positionSizePercent, 2), "%");
            Print("Calculation Time: ", TimeToString(calculationTime));
        } else {
            Print("=== Money Manager Calculation Failed ===");
            Print("Error: ", errorMessage);
        }
        Print("=======================================");
    }
};

//+------------------------------------------------------------------+
//| CMoneyManagerBase - Abstract base class                          |
//+------------------------------------------------------------------+
class CMoneyManagerBase {
protected:
    // Configuration
    SMoneyManagerConfig m_config;           // Money manager configuration
    SStrategyConfig* m_strategyConfig;      // Strategy-specific configuration (optional)
    
    // Dependencies
    CSymbolInfo* m_symbolInfo;              // Symbol information manager
    CRiskManager* m_riskManager;            // Risk manager (for risk multiplier)
    CLogger* m_logger;                      // Logger instance
    
    // State
    bool m_initialized;                     // Initialization flag
    double m_lastAccountBalance;            // Last known account balance
    double m_lastAccountEquity;             // Last known account equity
    datetime m_lastUpdateTime;              // Last update time
    
    // Performance tracking
    int m_calculationCount;                 // Number of calculations performed
    double m_totalRiskCalculated;           // Total risk amount calculated
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CMoneyManagerBase() :
        m_symbolInfo(NULL),
        m_riskManager(NULL),
        m_logger(NULL),
        m_strategyConfig(NULL),
        m_initialized(false),
        m_lastAccountBalance(0.0),
        m_lastAccountEquity(0.0),
        m_lastUpdateTime(0),
        m_calculationCount(0),
        m_totalRiskCalculated(0.0)
    {
        // Default configuration
        m_config = SMoneyManagerConfig();
    }
    
    virtual ~CMoneyManagerBase() {
        Deinitialize();
    }
    
    //+------------------------------------------------------------------+
    //| Initialization methods                                           |
    //+------------------------------------------------------------------+
    virtual bool Initialize(CSymbolInfo* symbolInfo = NULL, 
                           CRiskManager* riskManager = NULL,
                           CLogger* logger = NULL,
                           SStrategyConfig* strategyConfig = NULL) {
        if(m_initialized) {
            LogInfo("Money Manager already initialized");
            return true;
        }
        
        LogInfo("Initializing Money Manager Base...");
        
        // Set dependencies
        m_symbolInfo = symbolInfo;
        m_riskManager = riskManager;
        m_logger = logger;
        m_strategyConfig = strategyConfig;
        
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
        
        // Reset dependencies
        m_symbolInfo = NULL;
        m_riskManager = NULL;
        m_logger = NULL;
        m_strategyConfig = NULL;
        
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
            m_config.PrintConfig();
        } else {
            LogError("Failed to set invalid configuration");
        }
    }
    
    SMoneyManagerConfig GetConfig() const {
        return m_config;
    }
    
    void SetStrategyConfig(SStrategyConfig* strategyConfig) {
        m_strategyConfig = strategyConfig;
        if(strategyConfig != NULL) {
            // Override risk percent from strategy config if available
            if(strategyConfig->riskPercent > 0) {
                m_config.riskPercent = strategyConfig->riskPercent;
                LogInfo("Updated risk percent from strategy config: " + 
                        DoubleToString(strategyConfig->riskPercent, 2) + "%");
            }
        }
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
        if(!params.Validate()) {
            LogError("Invalid calculation parameters");
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
            // Basic validation if SymbolInfo is not available
            return (lotSize > 0);
        }
        
        return m_symbolInfo.ValidateVolume(lotSize);
    }
    
    double ApplyLotSizeLimits(string symbol, double lotSize) {
        if(lotSize <= 0) return 0.0;
        
        double result = lotSize;
        
        // Apply SymbolInfo limits if available
        if(m_symbolInfo != NULL && m_config.validateWithSymbolInfo) {
            // Get symbol limits
            double minLot = m_symbolInfo.GetVolumeMin();
            double maxLot = m_symbolInfo.GetVolumeMax();
            double lotStep = m_symbolInfo.GetVolumeStep();
            
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
                double lotStep = m_symbolInfo.GetVolumeStep();
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
    
    void PrintStatus() const {
        LogInfo("=== Money Manager Status ===");
        LogInfo("Name: " + GetName());
        LogInfo("Method: " + m_config.GetMethodString());
        LogInfo("Initialized: " + string(m_initialized ? "Yes" : "No"));
        LogInfo("Risk Percent: " + DoubleToString(m_config.riskPercent, 2) + "%");
        LogInfo("Risk Multiplier: " + DoubleToString(GetRiskMultiplier(), 2));
        LogInfo("Account Balance: " + DoubleToString(m_lastAccountBalance, 2));
        LogInfo("Account Equity: " + DoubleToString(m_lastAccountEquity, 2));
        LogInfo("Calculations Performed: " + IntegerToString(m_calculationCount));
        LogInfo("Total Risk Calculated: " + DoubleToString(m_totalRiskCalculated, 2));
        LogInfo("===========================");
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
        if(m_strategyConfig != NULL && m_strategyConfig->riskPercent > 0) {
            baseRisk = m_strategyConfig->riskPercent;
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
    
    void LogTrace(string message) {
        if(m_logger != NULL) {
            m_logger.Trace(message, GetName());
        }
    }
};

#endif // MONEYMANAGERBASE_MQH