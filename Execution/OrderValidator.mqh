// Execution/OrderValidator.mqh
#ifndef ORDERVALIDATOR_MQH
#define ORDERVALIDATOR_MQH

#include "..\Utilities\Logger.mqh"
#include "..\Utilities\ErrorHandler.mqh"
#include "..\Core\RiskManager.mqh"
#include "..\Data\SymbolInfo.mqh"
#include "..\Core\PositionManager.mqh"
#include "OrderTypes.mqh"

//+------------------------------------------------------------------+
//| Validation rule types                                            |
//+------------------------------------------------------------------+
enum ENUM_VALIDATION_RULE {
    RULE_STRATEGY_COMPLIANCE,   // Strategy-specific rules
    RULE_RISK_LIMITS,           // Risk manager limits
    RULE_POSITION_SIZE,         // Position size validation
    RULE_MARKET_CONDITIONS,     // Market state validation
    RULE_TRADING_HOURS,         // Trading session validation
    RULE_MARGIN_REQUIREMENTS,   // Margin availability
    RULE_BROKER_RESTRICTIONS,   // Broker-specific rules
    RULE_VOLUME_VALIDATION,     // Volume step/min/max
    RULE_PRICE_VALIDATION,      // Price validity
    RULE_STOPS_VALIDATION       // Stop loss/take profit validation
};

//+------------------------------------------------------------------+
//| COrderValidator - Main validation class                         |
//+------------------------------------------------------------------+
class COrderValidator {
private:
    // Component references
    CLogger*            m_logger;
    CErrorHandler*      m_errorHandler;
    CRiskManager*       m_riskManager;
    CSymbolInfo*        m_symbolInfo;
    CPositionManager*   m_positionManager;
    
    // Configuration
    bool                m_enabled;
    bool                m_strictValidation;  // Reject on any warning
    int                 m_validationTimeout; // ms to wait for validation
    
    // Statistics
    int                 m_totalValidations;
    int                 m_passedValidations;
    int                 m_failedValidations;
    datetime            m_lastValidationTime;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    COrderValidator(void) : 
        m_logger(NULL),
        m_errorHandler(NULL),
        m_riskManager(NULL),
        m_symbolInfo(NULL),
        m_positionManager(NULL),
        m_enabled(true),
        m_strictValidation(true),
        m_validationTimeout(5000),
        m_totalValidations(0),
        m_passedValidations(0),
        m_failedValidations(0),
        m_lastValidationTime(0)
    {}
    
    ~COrderValidator(void) {
        Deinitialize();
    }
    
    //+------------------------------------------------------------------+
    //| Initialization                                                   |
    //+------------------------------------------------------------------+
    bool Initialize(CRiskManager* riskMgr = NULL, 
                    CPositionManager* posMgr = NULL,
                    CSymbolInfo* symInfo = NULL) {
        
        // Get global instances
        m_logger = GlobalLogger;
        m_errorHandler = GlobalErrorHandler;
        
        // Store component references
        m_riskManager = riskMgr;
        m_positionManager = posMgr;
        m_symbolInfo = symInfo;
        
        if(m_logger == NULL) {
            Print("ERROR: Global logger not initialized");
            return false;
        }
        
        if(m_riskManager == NULL) {
            m_logger.Warn("RiskManager not provided - risk validation will be limited", "OrderValidator");
        }
        
        if(m_positionManager == NULL) {
            m_logger.Warn("PositionManager not provided - position validation will be limited", "OrderValidator");
        }
        
        if(m_symbolInfo == NULL) {
            m_logger.Warn("SymbolInfo not provided - symbol validation will be limited", "OrderValidator");
        }
        
        m_logger.Info("OrderValidator initialized successfully", "OrderValidator");
        return true;
    }
    
    void Deinitialize() {
        m_logger = NULL;
        m_errorHandler = NULL;
        m_riskManager = NULL;
        m_symbolInfo = NULL;
        m_positionManager = NULL;
    }
    
    //+------------------------------------------------------------------+
    //| Core validation methods                                          |
    //+------------------------------------------------------------------+
    SValidationResult ValidateTradeRequest(const STradeRequest &request) {
        SValidationResult result;
        result.isValid = true;
        m_totalValidations++;
        
        if(!m_enabled) {
            result.isValid = true;
            result.warningMessage = "Validator is disabled - skipping validation";
            return result;
        }
        
        // Perform all validation checks
        bool strategyOk = ValidateStrategyCompliance(request, result);
        bool riskOk = ValidateRiskLimits(request, result);
        bool positionOk = ValidatePositionSize(request, result);
        bool marketOk = ValidateMarketConditions(request, result);
        
        // Overall validation result
        result.isValid = strategyOk && riskOk && positionOk && marketOk;
        
        if(result.isValid) {
            m_passedValidations++;
            m_logger.Debug(StringFormat("Validation PASSED for %s %.2f %s", 
                request.symbol, request.volume, 
                request.orderType == ORDER_TYPE_BUY ? "BUY" : "SELL"), "OrderValidator");
        } else {
            m_failedValidations++;
            m_logger.Warn(StringFormat("Validation FAILED for %s: %s", 
                request.symbol, result.errorMessage), "OrderValidator");
        }
        
        m_lastValidationTime = TimeCurrent();
        return result;
    }
    
    SValidationResult ValidatePositionClose(ulong ticket, double volume = 0) {
        SValidationResult result;
        result.isValid = true;
        
        // For position close, we mainly check if position exists
        // and if we have permission to close it
        
        if(m_positionManager != NULL) {
            SPositionData position = m_positionManager.GetPosition(ticket);
            if(position.ticket == 0) {
                result.isValid = false;
                result.errorMessage = StringFormat("Position not found: %I64u", ticket);
            }
        }
        
        return result;
    }
    
    //+------------------------------------------------------------------+
    //| Individual validation checks                                     |
    //+------------------------------------------------------------------+
    bool ValidateStrategyCompliance(const STradeRequest &request, SValidationResult &result) {
        // Strategy compliance validation
        // This would check strategy-specific rules
        // For now, we'll implement basic checks
        
        if(request.strategyName == "") {
            result.isStrategyCompliant = false;
            result.errorMessage = "Strategy name is required";
            return false;
        }
        
        if(request.magic == 0) {
            result.isStrategyCompliant = false;
            result.errorMessage = "Magic number must be non-zero";
            return false;
        }
        
        result.isStrategyCompliant = true;
        return true;
    }
    
    bool ValidateRiskLimits(const STradeRequest &request, SValidationResult &result) {
        if(m_riskManager == NULL) {
            result.isRiskCompliant = true; // Skip if no risk manager
            return true;
        }
        
        // Use risk manager to check trade risk
        int riskViolation = (int)m_riskManager.CheckTradeRisk(
            request.orderType, 
            request.symbol, 
            request.volume, 
            request.price, 
            request.stopLoss, 
            request.strategyName
        );
        
        result.riskViolation = riskViolation;
        
        switch(riskViolation) {
            case 0: // RISK_VIOLATION_NONE
                result.isRiskCompliant = true;
                return true;
            case 1: // RISK_VIOLATION_WARNING
                result.isRiskCompliant = !m_strictValidation; // Allow if not strict
                result.warningMessage = "Risk warning detected";
                return !m_strictValidation;
            case 2: // RISK_VIOLATION_SEVERE
            case 3: // RISK_VIOLATION_CRITICAL
                result.isRiskCompliant = false;
                result.errorMessage = "Risk limit violated";
                return false;
        }
        
        return true;
    }
    
    bool ValidatePositionSize(const STradeRequest &request, SValidationResult &result) {
        result.isPositionSizeValid = false;
        
        // 1. Check basic volume validity
        if(request.volume <= 0) {
            result.errorMessage = "Volume must be greater than 0";
            return false;
        }
        
        // 2. Check symbol-specific volume limits (if SymbolInfo available)
        if(m_symbolInfo != NULL) {
            // Validate against symbol minimum volume
            double minVolume = (double)m_symbolInfo.GetVolumeMin();  // FIXED: Explicit cast
            if(request.volume < minVolume) {
                result.errorMessage = StringFormat("Volume %.2f is below minimum %.2f", 
                    request.volume, minVolume);
                return false;
            }
            
            // Validate against symbol maximum volume
            double maxVolume = (double)m_symbolInfo.GetVolumeMax();  // FIXED: Explicit cast
            if(request.volume > maxVolume) {
                result.errorMessage = StringFormat("Volume %.2f exceeds maximum %.2f", 
                    request.volume, maxVolume);
                return false;
            }
            
            // Check volume step
            double volumeStep = (double)m_symbolInfo.GetVolumeStep();  // FIXED: Explicit cast
            if(volumeStep > 0) {
                double remainder = MathMod(request.volume, volumeStep);
                if(MathAbs(remainder) > 0.00001) { // Allow for floating point error
                    result.errorMessage = StringFormat("Volume %.2f must be multiple of step %.2f", 
                        request.volume, volumeStep);
                    return false;
                }
            }
        }
        
        // 3. Check position count limits (if PositionManager available)
        if(m_positionManager != NULL) {
            int openPositions = m_positionManager.GetOpenPositionCountByMagic(request.magic);
            // Simple limit: max 5 positions per strategy
            if(openPositions >= 5) {
                result.errorMessage = StringFormat("Maximum positions (%d) reached for strategy", openPositions);
                return false;
            }
        }
        
        // 4. Calculate max allowed volume based on risk
        result.maxAllowedVolume = CalculateMaxAllowedVolume(request);
        if(request.volume > result.maxAllowedVolume && result.maxAllowedVolume > 0) {
            result.errorMessage = StringFormat("Volume %.2f exceeds maximum allowed %.2f", 
                request.volume, result.maxAllowedVolume);
            return false;
        }
        
        result.isPositionSizeValid = true;
        return true;
    }
    
    bool ValidateMarketConditions(const STradeRequest &request, SValidationResult &result) {
        // Check if market is open
        if(m_symbolInfo != NULL) {
            if(!m_symbolInfo.IsMarketOpen()) {
                result.errorMessage = "Market is closed";
                return false;
            }
            
            if(!m_symbolInfo.IsSessionActive()) {
                result.warningMessage = "Outside regular trading session";
                // Continue anyway, just warn
            }
        }
        
        // Check if spread is reasonable (simplified)
        if(request.slippage < 0) {
            result.errorMessage = "Slippage must be non-negative";
            return false;
        }
        
        return true;
    }
    
    bool ValidateTradingHours(const STradeRequest &request, SValidationResult &result) {
        // Trading hours validation
        // This would check if we're within allowed trading hours
        // For now, return true (always allow)
        return true;
    }
    
    bool ValidateMarginRequirements(const STradeRequest &request, SValidationResult &result) {
        // Margin requirement validation
        if(m_symbolInfo != NULL) {
            double requiredMargin = m_symbolInfo.CalculateMargin(request.orderType, request.volume);
            double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
            
            if(requiredMargin > freeMargin) {
                result.errorMessage = StringFormat("Insufficient margin. Required: %.2f, Available: %.2f", 
                    requiredMargin, freeMargin);
                return false;
            }
        }
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetEnabled(bool enabled) { 
        m_enabled = enabled; 
        if(m_logger != NULL) {
            m_logger.Info("OrderValidator " + (enabled ? "enabled" : "disabled"), "OrderValidator");
        }
    }
    
    void SetStrictValidation(bool strict) { 
        m_strictValidation = strict; 
        if(m_logger != NULL) {
            m_logger.Info("Strict validation " + (strict ? "enabled" : "disabled"), "OrderValidator");
        }
    }
    
    void SetValidationTimeout(int milliseconds) { 
        m_validationTimeout = milliseconds; 
    }
    
    //+------------------------------------------------------------------+
    //| Information methods                                              |
    //+------------------------------------------------------------------+
    bool IsEnabled() const { return m_enabled; }
    
    int GetSuccessRate() const {
        if(m_totalValidations == 0) return 0;
        return (int)((double)m_passedValidations / m_totalValidations * 100);
    }
    
    void PrintValidationStats() {
        if(m_logger == NULL) return;
        
        string stats = StringFormat(
            "Validation Statistics:\n" +
            "Total Validations: %d\n" +
            "Passed: %d | Failed: %d\n" +
            "Success Rate: %d%%\n" +
            "Last Validation: %s",
            m_totalValidations,
            m_passedValidations,
            m_failedValidations,
            GetSuccessRate(),
            TimeToString(m_lastValidationTime)
        );
        
        m_logger.Info(stats, "OrderValidator");
    }
    
private:
    //+------------------------------------------------------------------+
    //| Internal helper methods                                          |
    //+------------------------------------------------------------------+
    double CalculateMaxAllowedVolume(const STradeRequest &request) {
        // Calculate maximum volume based on risk parameters
        double maxVolume = 0;
        
        // Method 1: Based on risk percentage
        if(request.maxRiskPercent > 0) {
            double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
            double riskAmount = accountBalance * (request.maxRiskPercent / 100.0);
            
            if(request.riskAmount > 0) {
                // Calculate volume based on risk per unit
                maxVolume = riskAmount / request.riskAmount;
            }
        }
        
        // Method 2: Based on available margin
        if(m_symbolInfo != NULL) {
            double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
            double marginPerLot = m_symbolInfo.CalculateMargin(request.orderType, 1.0);
            
            if(marginPerLot > 0) {
                double marginBasedVolume = freeMargin / marginPerLot;
                if(maxVolume == 0 || marginBasedVolume < maxVolume) {
                    maxVolume = marginBasedVolume;
                }
            }
        }
        
        // Apply symbol volume limits
        if(m_symbolInfo != NULL) {
            double maxSymbolVolume = (double)m_symbolInfo.GetVolumeMax();  // FIXED: Explicit cast
            if(maxVolume > maxSymbolVolume) {
                maxVolume = maxSymbolVolume;
            }
        }
        
        return maxVolume;
    }
    
    //+------------------------------------------------------------------+
    //| Logging methods                                                  |
    //+------------------------------------------------------------------+
    void LogValidationResult(const STradeRequest &request, const SValidationResult &result) {
        if(m_logger == NULL) return;
        
        string logMessage = StringFormat("Validation %s for %s %.2f: %s",
            result.isValid ? "PASSED" : "FAILED",
            request.symbol,
            request.volume,
            result.errorMessage != "" ? result.errorMessage : result.warningMessage
        );
        
        if(result.isValid) {
            m_logger.Info(logMessage, "OrderValidator");
        } else {
            m_logger.Error(logMessage, "OrderValidator");
        }
    }
};

#endif