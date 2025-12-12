//+------------------------------------------------------------------+
//| CommonTypes.mqh - Shared data structures for Solara Platform     |
//+------------------------------------------------------------------+
#ifndef COMMONTYPES_MQH
#define COMMONTYPES_MQH

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Trade record structure (shared between components)               |
//+------------------------------------------------------------------+
struct STradeRecord {
    ulong           ticket;            // Trade ticket number
    ulong           magic;             // Magic number (strategy ID)
    string          symbol;            // Symbol traded
    ENUM_ORDER_TYPE type;              // Trade type (buy/sell)
    double          volume;            // Trade volume
    double          openPrice;         // Open price
    double          closePrice;        // Close price
    double          profit;            // Profit/loss amount
    double          commission;        // Commission paid
    double          swap;              // Swap paid/received
    datetime        openTime;          // Trade open time
    datetime        closeTime;         // Trade close time
    double          duration;          // Trade duration in hours
    string          strategyName;      // Strategy that executed trade
    string          comment;           // Trade comment
    
    // Constructor
    STradeRecord() {
        ticket = 0;
        magic = 0;
        symbol = "";
        type = ORDER_TYPE_BUY;
        volume = 0;
        openPrice = 0;
        closePrice = 0;
        profit = 0;
        commission = 0;
        swap = 0;
        openTime = 0;
        closeTime = 0;
        duration = 0;
        strategyName = "";
        comment = "";
    }
    
    // Methods
    bool IsWin() const { return profit > 0; }
    bool IsLoss() const { return profit < 0; }
    bool IsClosed() const { return closeTime > 0; }
    
    double GetDurationHours() const {
        if(closeTime > 0 && openTime > 0) {
            return (closeTime - openTime) / 3600.0;
        }
        return 0;
    }
};

//+------------------------------------------------------------------+
//| Trade statistics structure                                        |
//+------------------------------------------------------------------+
struct STradeStats {
    int totalTrades;
    int winningTrades;
    int losingTrades;
    double totalProfit;
    double totalLoss;
    double netProfit;
    double winRate;
    double profitFactor;
    double averageWin;
    double averageLoss;
    double largestWin;
    double largestLoss;
    
    STradeStats() {
        totalTrades = 0;
        winningTrades = 0;
        losingTrades = 0;
        totalProfit = 0;
        totalLoss = 0;
        netProfit = 0;
        winRate = 0;
        profitFactor = 0;
        averageWin = 0;
        averageLoss = 0;
        largestWin = 0;
        largestLoss = 0;
    }
};

//+------------------------------------------------------------------+
//| Strategy performance metrics                                      |
//+------------------------------------------------------------------+
struct SStrategyMetrics {
    string strategyName;
    double equity;
    double balance;
    double drawdown;
    double drawdownPercent;
    double profitToday;
    double profitWeek;
    double profitMonth;
    double profitYear;
    int tradesToday;
    int tradesWeek;
    int tradesMonth;
    int tradesYear;
    STradeStats tradeStats;
    
    SStrategyMetrics() {
        strategyName = "";
        equity = 0;
        balance = 0;
        drawdown = 0;
        drawdownPercent = 0;
        profitToday = 0;
        profitWeek = 0;
        profitMonth = 0;
        profitYear = 0;
        tradesToday = 0;
        tradesWeek = 0;
        tradesMonth = 0;
        tradesYear = 0;
    }
};

//+------------------------------------------------------------------+
//| Risk parameters                                                   |
//+------------------------------------------------------------------+
struct SRiskParameters {
    double maxDrawdownPercent;
    double dailyLossLimit;
    double positionSizePercent;
    double riskPerTradePercent;
    bool enableStopLoss;
    bool enableTakeProfit;
    bool enableTrailingStop;
    double trailingStopDistance;
    
    SRiskParameters() {
        maxDrawdownPercent = 20.0;
        dailyLossLimit = 5.0;
        positionSizePercent = 2.0;
        riskPerTradePercent = 1.0;
        enableStopLoss = true;
        enableTakeProfit = true;
        enableTrailingStop = false;
        trailingStopDistance = 50.0;
    }
};

//+------------------------------------------------------------------+
//| Platform settings                                                 |
//+------------------------------------------------------------------+
struct SPlatformSettings {
    bool enableLiveTrading;
    bool enableBacktesting;
    bool enableOptimization;
    bool enableLogging;
    int logLevel;
    bool enableEmailAlerts;
    bool enablePushNotifications;
    string emailAddress;
    
    SPlatformSettings() {
        enableLiveTrading = true;
        enableBacktesting = false;
        enableOptimization = false;
        enableLogging = true;
        logLevel = 1; // 1=Info, 2=Debug, 3=Error
        enableEmailAlerts = false;
        enablePushNotifications = false;
        emailAddress = "";
    }
};

#endif // COMMONTYPES_MQH