// Execution/OrderTypes.mqh
#ifndef ORDERTYPES_MQH
#define ORDERTYPES_MQH

//+------------------------------------------------------------------+
//| Execution modes                                                  |
//+------------------------------------------------------------------+
enum ENUM_EXECUTION_MODE {
    EXECUTION_INSTANT,      // Immediate market execution
    EXECUTION_RETRY_ON_FAIL // Retry if immediate fails
};

//+------------------------------------------------------------------+
//| Order priority                                                   |
//+------------------------------------------------------------------+
enum ENUM_ORDER_PRIORITY {
    PRIORITY_LOW = 0,       // Background orders
    PRIORITY_NORMAL = 1,    // Standard strategy orders
    PRIORITY_HIGH = 2,      // Risk management orders
    PRIORITY_CRITICAL = 3   // Emergency orders
};

//+------------------------------------------------------------------+
//| Execution event types                                            |
//+------------------------------------------------------------------+
enum ENUM_EXECUTION_EVENT {
    EVENT_ORDER_PLACED,        // Order placed successfully
    EVENT_ORDER_FILLED,        // Order filled (position opened)
    EVENT_ORDER_FAILED,        // Order placement failed
    EVENT_POSITION_MODIFIED,   // Position modified (SL/TP)
    EVENT_POSITION_CLOSED,     // Position closed
    EVENT_EXECUTION_TIMEOUT,   // Execution timeout
    EVENT_REQUOTE_RECEIVED,    // Requote received
    EVENT_SLIPPAGE_EXCEEDED,   // Slippage exceeded limit
    EVENT_RISK_VIOLATION,      // Risk violation detected
    EVENT_VALIDATION_FAILED    // Pre-trade validation failed
};

//+------------------------------------------------------------------+
//| Trade request structure                                          |
//+------------------------------------------------------------------+
struct STradeRequest {
    // Core parameters
    ENUM_ORDER_TYPE     orderType;      // ORDER_TYPE_BUY/SELL
    string              symbol;         // Trading symbol
    double              volume;         // Order volume
    double              price;          // Execution price (0 for market)
    double              stopLoss;       // Stop loss price
    double              takeProfit;     // Take profit price
    ulong               magic;          // Magic number (strategy ID)
    string              comment;        // Order comment
    string              strategyName;   // Originating strategy
    
    // Execution parameters
    int                 slippage;       // Max slippage in points
    ENUM_EXECUTION_MODE executionMode;  // Execution mode
    ENUM_ORDER_PRIORITY priority;       // Order priority
    datetime            expiration;     // Order expiration
    
    // Risk parameters
    double              maxRiskPercent; // Max risk percentage
    double              riskAmount;     // Calculated risk amount
    
    // Timestamps
    datetime            requestTime;    // When request was created
    string              requestId;      // Unique request identifier
    
    // Default constructor
    STradeRequest() :
        orderType(ORDER_TYPE_BUY),
        symbol(""),
        volume(0.01),
        price(0),
        stopLoss(0),
        takeProfit(0),
        magic(0),
        comment(""),
        strategyName(""),
        slippage(10),
        executionMode(EXECUTION_INSTANT),
        priority(PRIORITY_NORMAL),
        expiration(0),
        maxRiskPercent(1.0),
        riskAmount(0),
        requestTime(TimeCurrent()),
        requestId("")
    {}
};

//+------------------------------------------------------------------+
//| Trade result structure                                           |
//+------------------------------------------------------------------+
struct STradeResult {
    bool                success;        // Execution success
    ulong               ticket;         // Order/Position ticket
    double              price;          // Execution price
    double              volume;         // Executed volume
    double              commission;     // Commission charged
    double              swap;           // Swap value
    double              profit;         // Current profit
    int                 retcode;        // Return code
    string              comment;        // Result comment
    datetime            timestamp;      // Execution time
    double              slippage;       // Actual slippage
    int                 attemptCount;   // Number of attempts
    
    // Error information
    int                 errorCode;      // Error code if failed
    string              errorMessage;   // Error description
    bool                isRecoverable;  // Can be retried
    
    // Default constructor
    STradeResult() :
        success(false),
        ticket(0),
        price(0),
        volume(0),
        commission(0),
        swap(0),
        profit(0),
        retcode(0),
        comment(""),
        timestamp(0),
        slippage(0),
        attemptCount(0),
        errorCode(0),
        errorMessage(""),
        isRecoverable(true)
    {}
};

//+------------------------------------------------------------------+
//| Validation result structure                                      |
//+------------------------------------------------------------------+
struct SValidationResult {
    bool                isValid;        // Overall validation result
    int                 riskViolation;  // Risk violation level (from RiskManager)
    string              errorMessage;   // Validation error
    string              warningMessage; // Validation warning
    double              maxAllowedVolume; // Calculated max volume
    bool                isStrategyCompliant; // Strategy rules compliance
    bool                isRiskCompliant;     // Risk limits compliance
    bool                isPositionSizeValid; // Position size validation
    string              failureReason;  // Detailed failure reason
    
    // Default constructor
    SValidationResult() :
        isValid(false),
        riskViolation(0),
        errorMessage(""),
        warningMessage(""),
        maxAllowedVolume(0),
        isStrategyCompliant(false),
        isRiskCompliant(false),
        isPositionSizeValid(false),
        failureReason("")
    {}
};

//+------------------------------------------------------------------+
//| Execution metrics structure                                      |
//+------------------------------------------------------------------+
struct SExecutionMetrics {
    int                 totalOrders;        // Total orders attempted
    int                 successfulOrders;   // Successfully executed
    int                 failedOrders;       // Failed executions
    int                 requotes;           // Number of requotes
    double              avgSlippage;        // Average slippage
    double              maxSlippage;        // Maximum slippage
    double              minSlippage;        // Minimum slippage
    double              avgExecutionTime;   // Average execution time (ms)
    double              successRate;        // Success percentage
    double              totalCommission;    // Total commission paid
    double              totalSwap;          // Total swap charged
    datetime            firstExecution;     // First execution time
    datetime            lastExecution;      // Last execution time
    int                 peakOrdersPerMinute;// Peak order rate
    
    // Default constructor
    SExecutionMetrics() :
        totalOrders(0),
        successfulOrders(0),
        failedOrders(0),
        requotes(0),
        avgSlippage(0),
        maxSlippage(0),
        minSlippage(0),
        avgExecutionTime(0),
        successRate(0),
        totalCommission(0),
        totalSwap(0),
        firstExecution(0),
        lastExecution(0),
        peakOrdersPerMinute(0)
    {}
};

//+------------------------------------------------------------------+
//| Execution event structure                                        |
//+------------------------------------------------------------------+
struct SExecutionEvent {
    ENUM_EXECUTION_EVENT eventType;
    datetime            eventTime;
    string              symbol;
    ulong               ticket;
    double              price;
    double              volume;
    string              description;
    int                 errorCode;
    string              strategyName;
    
    // Default constructor
    SExecutionEvent() :
        eventType(EVENT_ORDER_PLACED),
        eventTime(0),
        symbol(""),
        ticket(0),
        price(0),
        volume(0),
        description(""),
        errorCode(0),
        strategyName("")
    {}
};

#endif