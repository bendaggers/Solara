// RiskManager.mqh - Comprehensive Risk Management for Solara Platform
//+------------------------------------------------------------------+
//| Description: Manages all risk parameters across strategies,      |
//|              enforces risk limits, provides risk analytics,      |
//|              and implements circuit breakers                     |
//+------------------------------------------------------------------+
#ifndef RISKMANAGER_MQH
#define RISKMANAGER_MQH

#include "..\Utilities\Logger.mqh"
#include "..\Utilities\DateTimeUtils.mqh"
#include "..\Utilities\MathUtils.mqh"
#include "..\Utilities\ArrayUtils.mqh"
#include "PositionManager.mqh"

//+------------------------------------------------------------------+
//| Risk violation severity levels                                   |
//+------------------------------------------------------------------+
enum ENUM_RISK_VIOLATION {
    RISK_VIOLATION_NONE = 0,        // No violation
    RISK_VIOLATION_WARNING = 1,     // Warning level violation
    RISK_VIOLATION_SEVERE = 2,      // Severe violation
    RISK_VIOLATION_CRITICAL = 3     // Critical violation - requires immediate action
};

//+------------------------------------------------------------------+
//| Risk limits structure                                            |
//+------------------------------------------------------------------+
struct SRiskLimits {
    // Account-level limits
    double          maxDailyLossPercent;     // Maximum daily loss as % of balance
    double          maxDailyLossAbsolute;    // Maximum daily loss in absolute terms
    double          maxDrawdownPercent;      // Maximum drawdown as % of equity peak
    double          maxPositionSizePercent;  // Maximum position size as % of balance
    double          maxTotalExposurePercent; // Maximum total exposure as % of balance
    
    // Strategy-level limits
    int             maxPositionsPerSymbol;   // Maximum positions per symbol
    int             maxTotalPositions;       // Maximum total positions
    double          maxRiskPerTradePercent;  // Maximum risk per trade as % of balance
    double          maxRiskPerStrategyPercent; // Maximum risk per strategy
    
    // Session limits
    double          maxLossPerSessionPercent; // Maximum loss per trading session
    int             maxTradesPerDay;         // Maximum trades per day
    int             maxConsecutiveLosses;    // Maximum consecutive losses
    
    // Time-based limits
    bool            enableTimeBasedLimits;   // Enable time-based restrictions
    int             tradingStartHour;        // Trading start hour (0-23)
    int             tradingEndHour;          // Trading end hour (0-23)
    bool            disableWeekendTrading;   // Disable trading on weekends
    
    // Volatility limits
    double          maxVolatilityMultiplier; // Maximum volatility multiplier
    bool            enableVolatilityFilter;  // Enable volatility-based filters
    double          minSpreadRatio;          // Minimum acceptable spread ratio
    
    SRiskLimits() {
        // Default conservative settings
        maxDailyLossPercent = 5.0;
        maxDailyLossAbsolute = 1000.0;
        maxDrawdownPercent = 20.0;
        maxPositionSizePercent = 2.0;
        maxTotalExposurePercent = 10.0;
        maxPositionsPerSymbol = 3;
        maxTotalPositions = 10;
        maxRiskPerTradePercent = 1.0;
        maxRiskPerStrategyPercent = 5.0;
        maxLossPerSessionPercent = 3.0;
        maxTradesPerDay = 20;
        maxConsecutiveLosses = 5;
        enableTimeBasedLimits = false;
        tradingStartHour = 0;
        tradingEndHour = 23;
        disableWeekendTrading = true;
        maxVolatilityMultiplier = 2.0;
        enableVolatilityFilter = true;
        minSpreadRatio = 1.5;
    }
};

//+------------------------------------------------------------------+
//| Risk metrics structure                                           |
//+------------------------------------------------------------------+
struct SRiskMetrics {
    // Account metrics
    double          currentBalance;          // Current account balance
    double          currentEquity;           // Current account equity
    double          currentMargin;           // Current margin used
    double          freeMargin;              // Free margin available
    double          marginLevel;             // Margin level percentage
    
    // Profit/Loss metrics
    double          dailyProfit;             // Profit/Loss for current day
    double          dailyLoss;               // Loss for current day
    double          dailyNet;                // Net daily P/L
    double          sessionProfit;           // Current session profit/loss
    
    // Drawdown metrics
    double          currentDrawdown;         // Current drawdown from equity peak
    double          currentDrawdownPercent;  // Current drawdown as percentage
    double          maxDrawdown;             // Maximum drawdown reached
    double          maxDrawdownPercent;      // Maximum drawdown percentage
    
    // Exposure metrics
    double          totalExposure;           // Total exposure across all positions
    double          exposurePercent;         // Exposure as percentage of balance
    int             totalPositions;          // Total open positions
    int             positionsPerSymbol[20];  // Positions per symbol (max 20 symbols)
    
    // Risk metrics
    double          totalRiskAmount;         // Total risk amount in open positions
    double          riskPercent;             // Total risk as percentage of balance
    double          avgPositionRisk;         // Average risk per position
    
    // Trading activity
    int             tradesToday;             // Trades executed today
    int             consecutiveLosses;       // Current consecutive losses
    int             maxConsecutiveLosses;    // Maximum consecutive losses reached
    
    // Volatility metrics
    double          currentVolatility;       // Current market volatility
    double          avgVolatility;           // Average volatility
    double          spreadRatio;             // Current spread to average ratio
    
    // Time tracking
    datetime        metricsTime;             // Time of last metrics update
    datetime        sessionStart;            // Current session start time
    
    SRiskMetrics() {
        Reset();
    }
    
    void Reset() {
        currentBalance = 0;
        currentEquity = 0;
        currentMargin = 0;
        freeMargin = 0;
        marginLevel = 0;
        dailyProfit = 0;
        dailyLoss = 0;
        dailyNet = 0;
        sessionProfit = 0;
        currentDrawdown = 0;
        currentDrawdownPercent = 0;
        maxDrawdown = 0;
        maxDrawdownPercent = 0;
        totalExposure = 0;
        exposurePercent = 0;
        totalPositions = 0;
        ArrayInitialize(positionsPerSymbol, 0);
        totalRiskAmount = 0;
        riskPercent = 0;
        avgPositionRisk = 0;
        tradesToday = 0;
        consecutiveLosses = 0;
        maxConsecutiveLosses = 0;
        currentVolatility = 0;
        avgVolatility = 0;
        spreadRatio = 1.0;
        metricsTime = TimeCurrent();
        sessionStart = TimeCurrent();
    }
};

//+------------------------------------------------------------------+
//| Risk violation event structure                                   |
//+------------------------------------------------------------------+
struct SRiskViolation {
    ENUM_RISK_VIOLATION severity;            // Violation severity
    string          ruleName;                // Name of violated rule
    string          description;             // Description of violation
    double          currentValue;            // Current value that caused violation
    double          limitValue;              // Limit value that was exceeded
    datetime        violationTime;           // Time of violation
    
    SRiskViolation() : 
        severity(RISK_VIOLATION_NONE),
        ruleName(""),
        description(""),
        currentValue(0),
        limitValue(0),
        violationTime(0)
    {}
};

//+------------------------------------------------------------------+
//| Circuit breaker action                                           |
//+------------------------------------------------------------------+
enum ENUM_CIRCUIT_BREAKER_ACTION {
    CIRCUIT_BREAKER_NONE = 0,               // No action
    CIRCUIT_BREAKER_WARNING = 1,            // Issue warning only
    CIRCUIT_BREAKER_REDUCE_RISK = 2,        // Reduce risk exposure
    CIRCUIT_BREAKER_CLOSE_POSITIONS = 3,    // Close some positions
    CIRCUIT_BREAKER_STOP_TRADING = 4,       // Stop all trading
    CIRCUIT_BREAKER_SHUTDOWN = 5            // Complete shutdown
};

//+------------------------------------------------------------------+
//| CRiskManager - Main risk management class                        |
//+------------------------------------------------------------------+
class CRiskManager {
private:
    // Configuration
    SRiskLimits     m_limits;               // Risk limits configuration
    SRiskMetrics    m_metrics;              // Current risk metrics
    bool            m_enabled;              // Risk manager enabled flag
    bool            m_initialized;          // Initialization flag
    
    // State tracking
    double          m_equityPeak;           // Equity peak for drawdown calculation
    double          m_dailyStartingBalance; // Starting balance for the day
    datetime        m_lastMetricsUpdate;    // Last metrics update time
    int             m_dailyTradeCount;      // Trades executed today
    
    // Violation tracking
    SRiskViolation  m_currentViolation;     // Current active violation
    SRiskViolation  m_violationHistory[20]; // History of violations
    int             m_violationIndex;       // Current violation index
    
    // Circuit breaker state
    ENUM_CIRCUIT_BREAKER_ACTION m_circuitBreaker;
    bool            m_tradingEnabled;       // Trading enabled flag
    double          m_riskMultiplier;       // Current risk multiplier (0-1)
    
    // Components
    CLogger*        m_logger;
    CDateTimeUtils* m_dateTimeUtils;
    CArrayUtils*    m_arrayUtils;
    CMathUtils*     m_mathUtils;
    CPositionManager* m_positionManager;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CRiskManager() :
        m_enabled(true),
        m_initialized(false),
        m_equityPeak(0),
        m_dailyStartingBalance(0),
        m_lastMetricsUpdate(0),
        m_dailyTradeCount(0),
        m_violationIndex(0),
        m_circuitBreaker(CIRCUIT_BREAKER_NONE),
        m_tradingEnabled(true),
        m_riskMultiplier(1.0),
        m_logger(NULL),
        m_dateTimeUtils(NULL),
        m_arrayUtils(NULL),
        m_mathUtils(NULL),
        m_positionManager(NULL)
    {
        m_currentViolation = SRiskViolation();
        // ArrayInitialize(m_violationHistory, 0);
       for(int i = 0; i < 20; i++) {
           m_violationHistory[i] = SRiskViolation();
       }
    }
    
    ~CRiskManager() {
        Deinitialize();
    }
    
    //+------------------------------------------------------------------+
    //| Initialization methods                                           |
    //+------------------------------------------------------------------+
    bool Initialize(CPositionManager* positionManager = NULL) {
        if(m_initialized) {
            LogInfo("Risk Manager already initialized");
            return true;
        }
        
        LogInfo("Initializing Risk Manager...");
        
        // Initialize components
        m_logger = GlobalLogger;
        m_dateTimeUtils = GlobalDateTimeUtils;
        m_arrayUtils = GlobalArrayUtils;
        m_mathUtils = GlobalMathUtils;
        m_positionManager = positionManager;
        
        if(m_logger == NULL) {
            Print("ERROR: Logger not initialized");
            return false;
        }
        
        // Reset metrics
        m_metrics.Reset();
        
        // Initialize tracking values
        m_equityPeak = AccountInfoDouble(ACCOUNT_EQUITY);
        m_dailyStartingBalance = AccountInfoDouble(ACCOUNT_BALANCE);
        m_dailyTradeCount = 0;
        m_lastMetricsUpdate = TimeCurrent();
        
        m_initialized = true;
        m_tradingEnabled = true;
        m_riskMultiplier = 1.0;
        m_circuitBreaker = CIRCUIT_BREAKER_NONE;
        
        LogInfo("Risk Manager initialized successfully");
        LogInfo("Default limits: Max Daily Loss=" + DoubleToString(m_limits.maxDailyLossPercent, 1) + "%, " +
                "Max Drawdown=" + DoubleToString(m_limits.maxDrawdownPercent, 1) + "%, " +
                "Max Risk/Trade=" + DoubleToString(m_limits.maxRiskPerTradePercent, 1) + "%");
        
        return true;
    }
    
    void Deinitialize() {
        if(!m_initialized) return;
        
        LogInfo("Deinitializing Risk Manager...");
        
        m_positionManager = NULL;
        m_initialized = false;
        
        LogInfo("Risk Manager deinitialized");
    }
    
    //+------------------------------------------------------------------+
    //| Core risk assessment methods                                     |
    //+------------------------------------------------------------------+
    ENUM_RISK_VIOLATION CheckTradeRisk(ENUM_ORDER_TYPE orderType, string symbol, 
                                      double volume, double price, double sl, 
                                      string strategyName = "") {
        if(!m_enabled || !m_initialized) {
            return RISK_VIOLATION_NONE;
        }
        
        // Update metrics first
        UpdateRiskMetrics();
        
        ENUM_RISK_VIOLATION violation = RISK_VIOLATION_NONE;
        
        // Check each risk rule
        violation = MathMax(violation, CheckDailyLossLimit());
        violation = MathMax(violation, CheckDrawdownLimit());
        violation = MathMax(violation, CheckTotalPositionsLimit());
        violation = MathMax(violation, CheckSymbolPositionsLimit(symbol));
        violation = MathMax(violation, CheckTradeRiskLimit(orderType, symbol, volume, price, sl));
        violation = MathMax(violation, CheckTotalExposureLimit(symbol, volume, price));
        violation = MathMax(violation, CheckDailyTradeLimit());
        violation = MathMax(violation, CheckConsecutiveLosses());
        violation = MathMax(violation, CheckTimeBasedRestrictions());
        violation = MathMax(violation, CheckVolatilityFilter(symbol));
        violation = MathMax(violation, CheckMarginRequirements(symbol, volume, price));
        violation = MathMax(violation, CheckCircuitBreaker());
        
        return violation;
    }
    
    ENUM_RISK_VIOLATION CheckPositionRisk(ulong ticket) {
        if(!m_enabled || !m_initialized) {
            return RISK_VIOLATION_NONE;
        }
        
        UpdateRiskMetrics();
        
        ENUM_RISK_VIOLATION violation = RISK_VIOLATION_NONE;
        
        violation = MathMax(violation, CheckDailyLossLimit());
        violation = MathMax(violation, CheckDrawdownLimit());
        violation = MathMax(violation, CheckCircuitBreaker());
        
        return violation;
    }
    
    //+------------------------------------------------------------------+
    //| Individual risk rule checks                                      |
    //+------------------------------------------------------------------+
    ENUM_RISK_VIOLATION CheckDailyLossLimit() {
        double dailyLossPercent = (m_dailyStartingBalance > 0) ? 
            (MathAbs(m_metrics.dailyNet) / m_dailyStartingBalance) * 100 : 0;
        
        if(m_metrics.dailyNet < 0) {
            // Check percentage limit
            if(dailyLossPercent > m_limits.maxDailyLossPercent) {
                RecordViolation(RISK_VIOLATION_CRITICAL,
                    "DailyLossPercent",
                    "Daily loss percentage limit exceeded",
                    dailyLossPercent,
                    m_limits.maxDailyLossPercent);
                return RISK_VIOLATION_CRITICAL;
            }
            
            // Check absolute limit
            if(MathAbs(m_metrics.dailyNet) > m_limits.maxDailyLossAbsolute) {
                RecordViolation(RISK_VIOLATION_CRITICAL,
                    "DailyLossAbsolute",
                    "Daily absolute loss limit exceeded",
                    MathAbs(m_metrics.dailyNet),
                    m_limits.maxDailyLossAbsolute);
                return RISK_VIOLATION_CRITICAL;
            }
            
            // Check warning threshold (80% of limit)
            if(dailyLossPercent > m_limits.maxDailyLossPercent * 0.8) {
                RecordViolation(RISK_VIOLATION_WARNING,
                    "DailyLossWarning",
                    "Approaching daily loss limit",
                    dailyLossPercent,
                    m_limits.maxDailyLossPercent * 0.8);
                return RISK_VIOLATION_WARNING;
            }
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckDrawdownLimit() {
        if(m_metrics.currentDrawdownPercent > m_limits.maxDrawdownPercent) {
            RecordViolation(RISK_VIOLATION_CRITICAL,
                "MaxDrawdown",
                "Maximum drawdown limit exceeded",
                m_metrics.currentDrawdownPercent,
                m_limits.maxDrawdownPercent);
            return RISK_VIOLATION_CRITICAL;
        }
        
        // Check warning threshold (80% of limit)
        if(m_metrics.currentDrawdownPercent > m_limits.maxDrawdownPercent * 0.8) {
            RecordViolation(RISK_VIOLATION_WARNING,
                "DrawdownWarning",
                "Approaching maximum drawdown limit",
                m_metrics.currentDrawdownPercent,
                m_limits.maxDrawdownPercent * 0.8);
            return RISK_VIOLATION_WARNING;
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckTotalPositionsLimit() {
        if(m_metrics.totalPositions >= m_limits.maxTotalPositions) {
            RecordViolation(RISK_VIOLATION_SEVERE,
                "TotalPositions",
                "Maximum total positions limit reached",
                (double)m_metrics.totalPositions,
                (double)m_limits.maxTotalPositions);
            return RISK_VIOLATION_SEVERE;
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckSymbolPositionsLimit(string symbol) {
        // Count positions for this symbol
        int symbolPositions = 0;
        if(m_positionManager != NULL) {
            SPositionData positions[];
            if(m_positionManager.GetPositionsBySymbol(symbol, positions)) {
                symbolPositions = ArraySize(positions);
            }
        }
        
        if(symbolPositions >= m_limits.maxPositionsPerSymbol) {
            RecordViolation(RISK_VIOLATION_SEVERE,
                "SymbolPositions",
                "Maximum positions per symbol limit reached",
                (double)symbolPositions,
                (double)m_limits.maxPositionsPerSymbol);
            return RISK_VIOLATION_SEVERE;
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckTradeRiskLimit(ENUM_ORDER_TYPE orderType, string symbol, 
                                           double volume, double price, double sl) {
        // Calculate risk amount for this trade
        double riskAmount = CalculateTradeRisk(orderType, symbol, volume, price, sl);
        double riskPercent = (m_metrics.currentBalance > 0) ? 
            (riskAmount / m_metrics.currentBalance) * 100 : 0;
        
        if(riskPercent > m_limits.maxRiskPerTradePercent) {
            RecordViolation(RISK_VIOLATION_SEVERE,
                "TradeRisk",
                "Maximum risk per trade exceeded",
                riskPercent,
                m_limits.maxRiskPerTradePercent);
            return RISK_VIOLATION_SEVERE;
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckTotalExposureLimit(string symbol, double volume, double price) {
        double newExposure = m_metrics.totalExposure + (volume * price);
        double exposurePercent = (m_metrics.currentBalance > 0) ? 
            (newExposure / m_metrics.currentBalance) * 100 : 0;
        
        if(exposurePercent > m_limits.maxTotalExposurePercent) {
            RecordViolation(RISK_VIOLATION_SEVERE,
                "TotalExposure",
                "Maximum total exposure limit exceeded",
                exposurePercent,
                m_limits.maxTotalExposurePercent);
            return RISK_VIOLATION_SEVERE;
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckDailyTradeLimit() {
        if(m_dailyTradeCount >= m_limits.maxTradesPerDay) {
            RecordViolation(RISK_VIOLATION_SEVERE,
                "DailyTrades",
                "Maximum daily trades limit reached",
                (double)m_dailyTradeCount,
                (double)m_limits.maxTradesPerDay);
            return RISK_VIOLATION_SEVERE;
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckConsecutiveLosses() {
        if(m_metrics.consecutiveLosses >= m_limits.maxConsecutiveLosses) {
            RecordViolation(RISK_VIOLATION_SEVERE,
                "ConsecutiveLosses",
                "Maximum consecutive losses reached",
                (double)m_metrics.consecutiveLosses,
                (double)m_limits.maxConsecutiveLosses);
            return RISK_VIOLATION_SEVERE;
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckTimeBasedRestrictions() {
        if(!m_limits.enableTimeBasedLimits) {
            return RISK_VIOLATION_NONE;
        }
        
        MqlDateTime currentTime;
        TimeCurrent(currentTime);
        
        // Check weekend trading
        if(m_limits.disableWeekendTrading && 
           (currentTime.day_of_week == 0 || currentTime.day_of_week == 6)) {
            RecordViolation(RISK_VIOLATION_SEVERE,
                "WeekendTrading",
                "Weekend trading is disabled",
                (double)currentTime.day_of_week,
                5.0); // Friday is last trading day
            return RISK_VIOLATION_SEVERE;
        }
        
        // Check trading hours
        if(currentTime.hour < m_limits.tradingStartHour || 
           currentTime.hour >= m_limits.tradingEndHour) {
            RecordViolation(RISK_VIOLATION_SEVERE,
                "TradingHours",
                "Outside allowed trading hours",
                (double)currentTime.hour,
                (double)m_limits.tradingStartHour);
            return RISK_VIOLATION_SEVERE;
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckVolatilityFilter(string symbol) {
        if(!m_limits.enableVolatilityFilter) {
            return RISK_VIOLATION_NONE;
        }
        
        // Calculate current spread ratio
        double currentSpread = SymbolInfoDouble(symbol, SYMBOL_ASK) - 
                               SymbolInfoDouble(symbol, SYMBOL_BID);
        double avgSpread = GetAverageSpread(symbol);
        
        if(avgSpread > 0) {
            double spreadRatio = currentSpread / avgSpread;
            
            if(spreadRatio > m_limits.maxVolatilityMultiplier) {
                RecordViolation(RISK_VIOLATION_WARNING,
                    "VolatilityFilter",
                    "High volatility detected - spread above normal",
                    spreadRatio,
                    m_limits.maxVolatilityMultiplier);
                return RISK_VIOLATION_WARNING;
            }
            
            if(spreadRatio < m_limits.minSpreadRatio) {
                RecordViolation(RISK_VIOLATION_WARNING,
                    "SpreadRatio",
                    "Spread ratio below minimum threshold",
                    spreadRatio,
                    m_limits.minSpreadRatio);
                return RISK_VIOLATION_WARNING;
            }
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckMarginRequirements(string symbol, double volume, double price) {
        double requiredMargin = 0;
        ENUM_ORDER_TYPE order_type = (volume > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
        
        if(OrderCalcMargin(order_type, symbol, MathAbs(volume), price, requiredMargin)) {
            if(requiredMargin > m_metrics.freeMargin) {
                RecordViolation(RISK_VIOLATION_CRITICAL,
                    "MarginRequirement",
                    "Insufficient margin for trade",
                    requiredMargin,
                    m_metrics.freeMargin);
                return RISK_VIOLATION_CRITICAL;
            }
            
            // Check margin level (warning if below 200%)
            if(m_metrics.marginLevel > 0 && m_metrics.marginLevel < 200.0) {
                RecordViolation(RISK_VIOLATION_WARNING,
                    "MarginLevel",
                    "Margin level below 200%",
                    m_metrics.marginLevel,
                    200.0);
                return RISK_VIOLATION_WARNING;
            }
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    ENUM_RISK_VIOLATION CheckCircuitBreaker() {
        switch(m_circuitBreaker) {
            case CIRCUIT_BREAKER_STOP_TRADING:
            case CIRCUIT_BREAKER_SHUTDOWN:
                RecordViolation(RISK_VIOLATION_CRITICAL,
                    "CircuitBreaker",
                    "Circuit breaker active - trading disabled",
                    (double)m_circuitBreaker,
                    0);
                return RISK_VIOLATION_CRITICAL;
            case CIRCUIT_BREAKER_CLOSE_POSITIONS:
                RecordViolation(RISK_VIOLATION_SEVERE,
                    "CircuitBreaker",
                    "Circuit breaker active - closing positions",
                    (double)m_circuitBreaker,
                    0);
                return RISK_VIOLATION_SEVERE;
            case CIRCUIT_BREAKER_REDUCE_RISK:
                RecordViolation(RISK_VIOLATION_WARNING,
                    "CircuitBreaker",
                    "Circuit breaker active - risk reduced",
                    (double)m_circuitBreaker,
                    0);
                return RISK_VIOLATION_WARNING;
        }
        
        return RISK_VIOLATION_NONE;
    }
    
    //+------------------------------------------------------------------+
    //| Circuit breaker management                                       |
    //+------------------------------------------------------------------+
    void ActivateCircuitBreaker(ENUM_CIRCUIT_BREAKER_ACTION action) {
        if(m_circuitBreaker != action) {
            m_circuitBreaker = action;
            
            switch(action) {
                case CIRCUIT_BREAKER_WARNING:
                    LogWarn("Circuit breaker: Warning issued");
                    break;
                case CIRCUIT_BREAKER_REDUCE_RISK:
                    m_riskMultiplier = 0.5;
                    LogWarn("Circuit breaker: Risk reduced by 50%");
                    break;
                case CIRCUIT_BREAKER_CLOSE_POSITIONS:
                    LogWarn("Circuit breaker: Closing positions");
                    // This would trigger position closing logic
                    break;
                case CIRCUIT_BREAKER_STOP_TRADING:
                    m_tradingEnabled = false;
                    LogError("Circuit breaker: Trading stopped");
                    break;
                case CIRCUIT_BREAKER_SHUTDOWN:
                    m_tradingEnabled = false;
                    LogError("Circuit breaker: System shutdown");
                    // This would trigger complete shutdown
                    break;
            }
        }
    }
    
    void DeactivateCircuitBreaker() {
        if(m_circuitBreaker != CIRCUIT_BREAKER_NONE) {
            LogInfo("Circuit breaker deactivated");
            m_circuitBreaker = CIRCUIT_BREAKER_NONE;
            m_riskMultiplier = 1.0;
            
            // Only re-enable trading if we weren't shut down
            if(m_tradingEnabled == false && m_circuitBreaker != CIRCUIT_BREAKER_SHUTDOWN) {
                m_tradingEnabled = true;
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Risk calculation methods                                         |
    //+------------------------------------------------------------------+
    double CalculateTradeRisk(ENUM_ORDER_TYPE orderType, string symbol, 
                             double volume, double price, double sl) {
        if(sl == 0) return 0;
        
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
        
        if(point <= 0 || tickValue <= 0) return 0;
        
        double stopDistance = 0;
        
        if(orderType == ORDER_TYPE_BUY || orderType == ORDER_TYPE_BUY_LIMIT || 
           orderType == ORDER_TYPE_BUY_STOP) {
            stopDistance = (price - sl) / point;
        } else {
            stopDistance = (sl - price) / point;
        }
        
        return MathAbs(volume) * stopDistance * tickValue * m_riskMultiplier;
    }
    
    double CalculatePositionSize(double riskAmount, string symbol, 
                                double entryPrice, double stopLoss) {
        if(stopLoss == 0 || riskAmount <= 0) return 0;
        
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
        
        if(point <= 0 || tickValue <= 0) return 0;
        
        double stopDistance = MathAbs(entryPrice - stopLoss) / point;
        if(stopDistance <= 0) return 0;
        
        double positionSize = riskAmount / (stopDistance * tickValue);
        
        // Apply position size limits
        positionSize = ApplyPositionSizeLimits(positionSize, symbol);
        
        return positionSize;
    }
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetLimits(const SRiskLimits &limits) {
        m_limits = limits;
        LogInfo("Risk limits updated");
    }
    
    SRiskLimits GetLimits() const {
        return m_limits;
    }
    
    void SetEnabled(bool enabled) {
        if(m_enabled != enabled) {
            m_enabled = enabled;
            LogInfo("Risk Manager " + (enabled ? "enabled" : "disabled"));
        }
    }
    
    bool IsEnabled() const {
        return m_enabled;
    }
    
    bool IsTradingEnabled() const {
        return m_tradingEnabled;
    }
    
    double GetRiskMultiplier() const {
        return m_riskMultiplier;
    }
    
    void SetRiskMultiplier(double multiplier) {
        if(multiplier >= 0 && multiplier <= 1.0) {
            m_riskMultiplier = multiplier;
            LogInfo("Risk multiplier set to: " + DoubleToString(multiplier, 2));
        }
    }
    
    //+------------------------------------------------------------------+
    //| Metrics and reporting methods                                    |
    //+------------------------------------------------------------------+
   void UpdateRiskMetrics() {
       if(!m_initialized) return;
       
       datetime currentTime = TimeCurrent();
       
       // Check if we need to reset daily metrics
       if(!IsSameDay(currentTime, m_metrics.metricsTime)) {
           ResetDailyMetrics();
       }
       
       // Update account metrics
       m_metrics.currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
       m_metrics.currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
       m_metrics.currentMargin = AccountInfoDouble(ACCOUNT_MARGIN);
       // REPLACE THIS LINE:
       // m_metrics.freeMargin = AccountInfoDouble(ACCOUNT_FREEMARGIN);
       // WITH THIS:
       m_metrics.freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
       m_metrics.marginLevel = (m_metrics.currentMargin > 0) ? 
           (m_metrics.currentEquity / m_metrics.currentMargin) * 100 : 0;
        
        // Update equity peak for drawdown calculation
        if(m_metrics.currentEquity > m_equityPeak) {
            m_equityPeak = m_metrics.currentEquity;
        }
        
        // Calculate drawdown
        m_metrics.currentDrawdown = m_equityPeak - m_metrics.currentEquity;
        m_metrics.currentDrawdownPercent = (m_equityPeak > 0) ? 
            (m_metrics.currentDrawdown / m_equityPeak) * 100 : 0;
        
        // Update maximum drawdown
        if(m_metrics.currentDrawdownPercent > m_metrics.maxDrawdownPercent) {
            m_metrics.maxDrawdownPercent = m_metrics.currentDrawdownPercent;
            m_metrics.maxDrawdown = m_metrics.currentDrawdown;
        }
        
        // Update daily P/L
        m_metrics.dailyNet = m_metrics.currentBalance - m_dailyStartingBalance;
        if(m_metrics.dailyNet > 0) {
            m_metrics.dailyProfit = m_metrics.dailyNet;
            m_metrics.dailyLoss = 0;
        } else {
            m_metrics.dailyProfit = 0;
            m_metrics.dailyLoss = MathAbs(m_metrics.dailyNet);
        }
        
        // Update exposure metrics if position manager is available
        if(m_positionManager != NULL) {
            m_metrics.totalPositions = m_positionManager.GetOpenPositionCount();
            m_metrics.totalExposure = m_positionManager.GetTotalExposure();
            m_metrics.exposurePercent = (m_metrics.currentBalance > 0) ? 
                (m_metrics.totalExposure / m_metrics.currentBalance) * 100 : 0;
            
            // Get total risk amount
            m_metrics.totalRiskAmount = m_positionManager.GetRiskExposure();
            m_metrics.riskPercent = (m_metrics.currentBalance > 0) ? 
                (m_metrics.totalRiskAmount / m_metrics.currentBalance) * 100 : 0;
            
            if(m_metrics.totalPositions > 0) {
                m_metrics.avgPositionRisk = m_metrics.totalRiskAmount / m_metrics.totalPositions;
            }
        }
        
        m_metrics.metricsTime = currentTime;
        m_lastMetricsUpdate = currentTime;
    }
    
    SRiskMetrics GetRiskMetrics() const {
        return m_metrics;
    }
    
    void PrintRiskMetrics() const {
        if(m_logger == NULL) return;
        
        string metrics = StringFormat(
            "Risk Metrics:\n" +
            "Balance: %.2f | Equity: %.2f | Margin: %.2f (%.1f%%)\n" +
            "Daily P/L: %.2f (%.2f%%) | Drawdown: %.2f (%.2f%%)\n" +
            "Exposure: %.2f (%.2f%%) | Positions: %d\n" +
            "Total Risk: %.2f (%.2f%%) | Avg Pos Risk: %.2f\n" +
            "Trades Today: %d | Consecutive Losses: %d\n" +
            "Risk Multiplier: %.2f | Trading Enabled: %s",
            m_metrics.currentBalance,
            m_metrics.currentEquity,
            m_metrics.currentMargin,
            m_metrics.marginLevel,
            m_metrics.dailyNet,
            (m_dailyStartingBalance > 0 ? (m_metrics.dailyNet / m_dailyStartingBalance) * 100 : 0),
            m_metrics.currentDrawdown,
            m_metrics.currentDrawdownPercent,
            m_metrics.totalExposure,
            m_metrics.exposurePercent,
            m_metrics.totalPositions,
            m_metrics.totalRiskAmount,
            m_metrics.riskPercent,
            m_metrics.avgPositionRisk,
            m_dailyTradeCount,
            m_metrics.consecutiveLosses,
            m_riskMultiplier,
            m_tradingEnabled ? "Yes" : "No"
        );
        
        m_logger.Info(metrics, "RiskManager");
    }
    
    void PrintViolationHistory() const {
        if(m_logger == NULL) return;
        
        m_logger.Info("=== RISK VIOLATION HISTORY ===", "RiskManager");
        
        int count = 0;
        for(int i = 0; i < 20; i++) {
            if(m_violationHistory[i].severity != RISK_VIOLATION_NONE) {
                count++;
                string violation = StringFormat(
                    "#%d: [%s] %s - Current: %.2f, Limit: %.2f at %s",
                    count,
                    GetViolationSeverityString(m_violationHistory[i].severity),
                    m_violationHistory[i].ruleName,
                    m_violationHistory[i].currentValue,
                    m_violationHistory[i].limitValue,
                    TimeToString(m_violationHistory[i].violationTime)
                );
                m_logger.Info(violation, "RiskManager");
            }
        }
        
        if(count == 0) {
            m_logger.Info("No violations recorded", "RiskManager");
        }
    }
    
    //+------------------------------------------------------------------+
    //| Trade tracking methods                                           |
    //+------------------------------------------------------------------+
    void RecordTrade(bool isWin, double profit) {
        m_dailyTradeCount++;
        
        if(isWin) {
            m_metrics.consecutiveLosses = 0;
        } else {
            m_metrics.consecutiveLosses++;
            if(m_metrics.consecutiveLosses > m_metrics.maxConsecutiveLosses) {
                m_metrics.maxConsecutiveLosses = m_metrics.consecutiveLosses;
            }
        }
        
        // Check if we need to activate circuit breaker due to consecutive losses
        if(m_metrics.consecutiveLosses >= m_limits.maxConsecutiveLosses) {
            ActivateCircuitBreaker(CIRCUIT_BREAKER_REDUCE_RISK);
        }
    }
    
private:
    //+------------------------------------------------------------------+
    //| Internal helper methods                                          |
    //+------------------------------------------------------------------+
    void ResetDailyMetrics() {
        m_dailyStartingBalance = AccountInfoDouble(ACCOUNT_BALANCE);
        m_dailyTradeCount = 0;
        m_metrics.consecutiveLosses = 0;
        m_metrics.sessionStart = TimeCurrent();
        m_metrics.sessionProfit = 0;
        
        LogInfo("Daily metrics reset");
    }
    
    bool IsSameDay(datetime time1, datetime time2) {
        MqlDateTime dt1, dt2;
        TimeToStruct(time1, dt1);
        TimeToStruct(time2, dt2);
        
        return (dt1.year == dt2.year && dt1.mon == dt2.mon && dt1.day == dt2.day);
    }
    
    double GetAverageSpread(string symbol, int period = 20) {
        // Simple average spread calculation
        double sumSpread = 0;
        int count = 0;
        
        for(int i = 0; i < period; i++) {
            double ask = iHigh(symbol, PERIOD_M1, i);
            double bid = iLow(symbol, PERIOD_M1, i);
            
            if(ask > 0 && bid > 0) {
                sumSpread += (ask - bid);
                count++;
            }
        }
        
        return (count > 0) ? sumSpread / count : 0;
    }
    
    double ApplyPositionSizeLimits(double positionSize, string symbol) {
        if(positionSize <= 0) return 0;
        
        // Apply symbol-specific volume limits
        double minVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
        double maxVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
        double stepVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
        
        // Ensure within min/max limits
        positionSize = MathMax(positionSize, minVolume);
        positionSize = MathMin(positionSize, maxVolume);
        
        // Round to nearest step
        if(stepVolume > 0) {
            positionSize = MathRound(positionSize / stepVolume) * stepVolume;
        }
        
        // Apply position size percentage limit
        double maxPositionByPercent = (m_limits.maxPositionSizePercent / 100.0) * m_metrics.currentBalance;
        double positionValue = positionSize * SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
        
        if(positionValue > maxPositionByPercent) {
            positionSize = maxPositionByPercent / SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
            
            // Re-apply step rounding
            if(stepVolume > 0) {
                positionSize = MathRound(positionSize / stepVolume) * stepVolume;
            }
        }
        
        return positionSize;
    }
    
    void RecordViolation(ENUM_RISK_VIOLATION severity, string ruleName, 
                        string description, double currentValue, double limitValue) {
        m_currentViolation.severity = severity;
        m_currentViolation.ruleName = ruleName;
        m_currentViolation.description = description;
        m_currentViolation.currentValue = currentValue;
        m_currentViolation.limitValue = limitValue;
        m_currentViolation.violationTime = TimeCurrent();
        
        // Add to history
        m_violationIndex = (m_violationIndex + 1) % 20;
        m_violationHistory[m_violationIndex] = m_currentViolation;
        
        // Log the violation
        string logMessage = StringFormat("Risk Violation [%s]: %s (Current: %.2f, Limit: %.2f)",
            GetViolationSeverityString(severity),
            description,
            currentValue,
            limitValue);
        
        switch(severity) {
            case RISK_VIOLATION_WARNING:
                LogWarn(logMessage);
                break;
            case RISK_VIOLATION_SEVERE:
                LogWarn(logMessage);
                // Consider activating circuit breaker
                if(m_circuitBreaker == CIRCUIT_BREAKER_NONE) {
                    ActivateCircuitBreaker(CIRCUIT_BREAKER_REDUCE_RISK);
                }
                break;
            case RISK_VIOLATION_CRITICAL:
                LogError(logMessage);
                // Activate circuit breaker
                if(m_circuitBreaker < CIRCUIT_BREAKER_STOP_TRADING) {
                    ActivateCircuitBreaker(CIRCUIT_BREAKER_STOP_TRADING);
                }
                break;
        }
    }
    
    string GetViolationSeverityString(ENUM_RISK_VIOLATION severity) const {
        switch(severity) {
            case RISK_VIOLATION_NONE: return "NONE";
            case RISK_VIOLATION_WARNING: return "WARNING";
            case RISK_VIOLATION_SEVERE: return "SEVERE";
            case RISK_VIOLATION_CRITICAL: return "CRITICAL";
            default: return "UNKNOWN";
        }
    }
    
    //+------------------------------------------------------------------+
    //| Logging methods                                                  |
    //+------------------------------------------------------------------+
    void LogError(string message) {
        if(m_logger != NULL) {
            m_logger.Error(message, "RiskManager");
        } else {
            Print("ERROR [RiskManager]: " + message);
        }
    }
    
    void LogWarn(string message) {
        if(m_logger != NULL) {
            m_logger.Warn(message, "RiskManager");
        }
    }
    
    void LogInfo(string message) {
        if(m_logger != NULL) {
            m_logger.Info(message, "RiskManager");
        } else {
            Print("INFO [RiskManager]: " + message);
        }
    }
};

#endif // RISKMANAGER_MQH