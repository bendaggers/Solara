// PerformanceMonitor.mqh - Comprehensive Performance Monitoring for Solara Platform
//+------------------------------------------------------------------+
//| Description: Tracks and analyzes performance across all          |
//|              strategies, provides detailed analytics, and        |
//|              generates performance reports                       |
//+------------------------------------------------------------------+
#ifndef PERFORMANCEMONITOR_MQH
#define PERFORMANCEMONITOR_MQH

#include "..\Utilities\Logger.mqh"
#include "..\Utilities\DateTimeUtils.mqh"
#include "..\Utilities\MathUtils.mqh"
#include "..\Utilities\ArrayUtils.mqh"
#include "..\Core\StrategyBase.mqh"
#include "..\Core\PositionManager.mqh"
#include "..\Core\RiskManager.mqh"
#include "..\Core\CommonTypes.mqh"  // STradeRecord is defined here

//+------------------------------------------------------------------+
//| Performance period enumeration                                   |
//+------------------------------------------------------------------+
enum ENUM_PERFORMANCE_PERIOD {
    PERFORMANCE_PERIOD_DAILY = 0,     // Daily performance
    PERFORMANCE_PERIOD_WEEKLY = 1,    // Weekly performance  
    PERFORMANCE_PERIOD_MONTHLY = 2,   // Monthly performance
    PERFORMANCE_PERIOD_QUARTERLY = 3, // Quarterly performance
    PERFORMANCE_PERIOD_YEARLY = 4,    // Yearly performance
    PERFORMANCE_PERIOD_ALLTIME = 5    // All-time performance
};

//+------------------------------------------------------------------+
//| Performance metric structure                                     |
//+------------------------------------------------------------------+
struct SPerformanceMetric {
    // Basic metrics
    int         totalTrades;            // Total number of trades
    int         winningTrades;          // Number of winning trades
    int         losingTrades;           // Number of losing trades
    double      winRate;                // Win rate percentage
    int         consecutiveLosses;      // Consecutive losses
    
    // Profit/Loss metrics
    double      totalProfit;            // Total profit
    double      totalLoss;              // Total loss
    double      netProfit;              // Net profit/loss
    double      profitFactor;           // Profit factor (profit/loss)
    
    // Trade statistics
    double      averageWin;             // Average winning trade
    double      averageLoss;            // Average losing trade
    double      averageTrade;           // Average trade P/L
    double      largestWin;             // Largest winning trade
    double      largestLoss;            // Largest losing trade
    
    // Risk metrics
    double      maxDrawdown;            // Maximum drawdown amount
    double      maxDrawdownPercent;     // Maximum drawdown percentage
    double      sharpeRatio;            // Sharpe ratio (risk-adjusted return)
    double      sortinoRatio;           // Sortino ratio (downside risk)
    double      recoveryFactor;         // Recovery factor (net profit / max drawdown)
    
    // Time-based metrics
    double      averageTradeDuration;   // Average trade duration in hours
    double      longestTradeDuration;   // Longest trade duration
    double      shortestTradeDuration;  // Shortest trade duration
    
    // Consistency metrics
    double      standardDeviation;      // Standard deviation of returns
    double      expectancy;             // Expected value per trade
    double      kellyPercentage;        // Kelly criterion percentage
    
    // Performance ratings
    double      performanceScore;       // Overall performance score (0-100)
    string      performanceGrade;       // Performance grade (A-F)
    
    // Time frame
    ENUM_PERFORMANCE_PERIOD period;     // Performance period
    datetime    startDate;              // Start date of period
    datetime    endDate;                // End date of period
    datetime    lastUpdate;             // Last update timestamp
    
    SPerformanceMetric() {
        Reset();
    }
    
    void Reset() {
        totalTrades = 0;
        winningTrades = 0;
        losingTrades = 0;
        winRate = 0;
        totalProfit = 0;
        totalLoss = 0;
        netProfit = 0;
        profitFactor = 0;
        averageWin = 0;
        averageLoss = 0;
        averageTrade = 0;
        largestWin = 0;
        largestLoss = 0;
        maxDrawdown = 0;
        maxDrawdownPercent = 0;
        sharpeRatio = 0;
        sortinoRatio = 0;
        recoveryFactor = 0;
        averageTradeDuration = 0;
        longestTradeDuration = 0;
        shortestTradeDuration = 0;
        standardDeviation = 0;
        expectancy = 0;
        kellyPercentage = 0;
        performanceScore = 0;
        performanceGrade = "F";
        period = PERFORMANCE_PERIOD_DAILY;
        startDate = 0;
        endDate = 0;
        lastUpdate = 0;
        consecutiveLosses = 0;
    }
    
    // Calculate derived metrics
    void CalculateDerivedMetrics() {
        // Win rate
        if(totalTrades > 0) {
            winRate = (double)winningTrades / totalTrades * 100.0;
        }
        
        // Profit factor
        if(totalLoss > 0) {
            profitFactor = totalProfit / totalLoss;
        } else if(totalProfit > 0) {
            profitFactor = 1000.0; // High number for no losses
        }
        
        // Average win/loss
        if(winningTrades > 0) {
            averageWin = totalProfit / winningTrades;
        }
        if(losingTrades > 0) {
            averageLoss = totalLoss / losingTrades;
        }
        
        // Average trade
        if(totalTrades > 0) {
            averageTrade = netProfit / totalTrades;
        }
        
        // Expectancy
        expectancy = (winRate/100.0 * averageWin) - ((100-winRate)/100.0 * MathAbs(averageLoss));
        
        // Kelly percentage
        if(averageWin > 0 && MathAbs(averageLoss) > 0) {
            double winProb = winRate / 100.0;
            double winLossRatio = averageWin / MathAbs(averageLoss);
            kellyPercentage = winProb - ((1 - winProb) / winLossRatio);
            kellyPercentage = MathMax(0, MathMin(kellyPercentage, 0.25)); // Limit to 25%
        }
        
        // Recovery factor
        if(maxDrawdown > 0) {
            recoveryFactor = netProfit / maxDrawdown;
        }
        
        // Performance score (simplified calculation)
        performanceScore = CalculatePerformanceScore();
        
        // Performance grade
        performanceGrade = CalculatePerformanceGrade();
        
        lastUpdate = TimeCurrent();
    }
    
    double CalculatePerformanceScore() {
        double score = 0;
        
        // Win rate component (30%)
        score += MathMin(winRate / 100.0 * 30, 30);
        
        // Profit factor component (30%)
        score += MathMin(profitFactor / 10.0 * 30, 30);
        
        // Recovery factor component (20%)
        score += MathMin(recoveryFactor / 5.0 * 20, 20);
        
        // Expectancy component (20%)
        score += MathMin((expectancy + 10) / 20.0 * 20, 20);
        
        return MathMin(score, 100);
    }
    
    string CalculatePerformanceGrade() {
        if(performanceScore >= 90) return "A";
        if(performanceScore >= 80) return "B";
        if(performanceScore >= 70) return "C";
        if(performanceScore >= 60) return "D";
        return "F";
    }
};

//+------------------------------------------------------------------+
//| Strategy performance structure                                   |
//+------------------------------------------------------------------+
struct SStrategyPerformance {
    string              strategyName;      // Strategy name
    SPerformanceMetric  currentMetrics;    // Current performance metrics
    SPerformanceMetric  dailyMetrics;      // Daily metrics
    SPerformanceMetric  weeklyMetrics;     // Weekly metrics
    SPerformanceMetric  monthlyMetrics;    // Monthly metrics
    SPerformanceMetric  allTimeMetrics;    // All-time metrics
    STradeRecord        tradeHistory[1000]; // Trade history (circular buffer)
    int                 tradeIndex;        // Current trade index
    datetime            lastTradeTime;     // Last trade time
    double              currentEquity;     // Current strategy equity
    
    SStrategyPerformance() : 
        strategyName(""),
        tradeIndex(0),
        lastTradeTime(0),
        currentEquity(0)
    {
        // Initialize trade history
        for(int i = 0; i < 1000; i++) {
            tradeHistory[i] = STradeRecord();
        }
    }
    
    void AddTrade(const STradeRecord &trade) {
        tradeHistory[tradeIndex] = trade;
        tradeIndex = (tradeIndex + 1) % 1000;
        lastTradeTime = trade.closeTime > 0 ? trade.closeTime : trade.openTime;
    }
    
    void UpdateMetrics() {
        // Update all metric periods
        UpdatePeriodMetrics(currentMetrics, 0, 0);          // Current session
        UpdatePeriodMetrics(dailyMetrics, TimeCurrent() - 86400, TimeCurrent());
        UpdatePeriodMetrics(weeklyMetrics, TimeCurrent() - 604800, TimeCurrent());
        UpdatePeriodMetrics(monthlyMetrics, TimeCurrent() - 2592000, TimeCurrent());
        UpdatePeriodMetrics(allTimeMetrics, 0, 0);          // All time
    }
    
private:
    void UpdatePeriodMetrics(SPerformanceMetric &metrics, datetime startTime, datetime endTime) {
        metrics.Reset();
        
        for(int i = 0; i < 1000; i++) {
            if(tradeHistory[i].ticket > 0 && tradeHistory[i].IsClosed()) {
                // Check if trade is within time period
                if((startTime == 0 && endTime == 0) || 
                   (tradeHistory[i].closeTime >= startTime && tradeHistory[i].closeTime <= endTime)) {
                    
                    metrics.totalTrades++;
                    
                    if(tradeHistory[i].IsWin()) {
                        metrics.winningTrades++;
                        metrics.totalProfit += tradeHistory[i].profit;
                        metrics.largestWin = MathMax(metrics.largestWin, tradeHistory[i].profit);
                    } else {
                        metrics.losingTrades++;
                        metrics.totalLoss += MathAbs(tradeHistory[i].profit);
                        metrics.largestLoss = MathMin(metrics.largestLoss, tradeHistory[i].profit);
                    }
                    
                    metrics.netProfit += tradeHistory[i].profit;
                    
                    // Update duration metrics
                    double duration = tradeHistory[i].GetDurationHours();
                    if(duration > 0) {
                        if(metrics.shortestTradeDuration == 0 || duration < metrics.shortestTradeDuration) {
                            metrics.shortestTradeDuration = duration;
                        }
                        metrics.longestTradeDuration = MathMax(metrics.longestTradeDuration, duration);
                        metrics.averageTradeDuration = (metrics.averageTradeDuration * (metrics.totalTrades - 1) + duration) / metrics.totalTrades;
                    }
                }
            }
        }
        
        metrics.CalculateDerivedMetrics();
        metrics.startDate = startTime;
        metrics.endDate = endTime;
        metrics.lastUpdate = TimeCurrent();
    }
};

//+------------------------------------------------------------------+
//| Performance report structure                                     |
//+------------------------------------------------------------------+
struct SPerformanceReport {
    string              reportId;           // Report identifier
    datetime            reportDate;         // Report generation date
    SPerformanceMetric  overallMetrics;     // Overall performance metrics
    SPerformanceMetric  periodMetrics;      // Period-specific metrics
    string              strategies[];       // List of strategies in report
    double              strategyReturns[];  // Returns by strategy
    string              analysis;           // Performance analysis text
    string              recommendations;    // Recommendations for improvement
    bool                hasImprovements;    // Whether improvements are needed
    
    SPerformanceReport() : 
        reportId(""),
        reportDate(0),
        hasImprovements(false)
    {
        ArrayResize(strategies, 0);
        ArrayResize(strategyReturns, 0);
    }
};

//+------------------------------------------------------------------+
//| CPerformanceMonitor - Main performance monitoring class          |
//+------------------------------------------------------------------+
class CPerformanceMonitor {
private:
    // Performance tracking
    SPerformanceMetric      m_overallMetrics;          // Overall platform metrics
    SStrategyPerformance    m_strategies[50];          // Strategy performance tracking
    int                     m_strategyCount;           // Number of strategies tracked
    
    // Trade history
    STradeRecord            m_tradeHistory[5000];      // Global trade history
    int                     m_tradeIndex;              // Current trade index
    
    // Configuration
    bool                    m_enabled;                 // Monitor enabled flag
    bool                    m_initialized;             // Initialization flag
    bool                    m_autoUpdate;              // Auto-update metrics
    int                     m_updateInterval;          // Update interval in seconds
    datetime                m_lastUpdate;              // Last update time
    
    // Components
    CLogger*                m_logger;
    CDateTimeUtils*         m_dateTimeUtils;
    CArrayUtils*            m_arrayUtils;
    CMathUtils*             m_mathUtils;
    CPositionManager*       m_positionManager;
    CRiskManager*           m_riskManager;
    
    // Performance storage
    SPerformanceMetric      m_dailyHistory[365];       // Daily history (1 year)
    SPerformanceMetric      m_weeklyHistory[52];       // Weekly history (1 year)
    int                     m_dailyIndex;
    int                     m_weeklyIndex;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CPerformanceMonitor() :
        m_strategyCount(0),
        m_enabled(true),
        m_initialized(false),
        m_autoUpdate(true),
        m_updateInterval(60),
        m_lastUpdate(0),
        m_logger(NULL),
        m_dateTimeUtils(NULL),
        m_arrayUtils(NULL),
        m_mathUtils(NULL),
        m_positionManager(NULL),
        m_riskManager(NULL),
        m_dailyIndex(0),
        m_weeklyIndex(0)
    {
        // Initialize trade history
        for(int i = 0; i < 5000; i++) {
            m_tradeHistory[i] = STradeRecord();
        }
        
        // Initialize daily/weekly history
        for(int i = 0; i < 365; i++) {
            m_dailyHistory[i] = SPerformanceMetric();
        }
        for(int i = 0; i < 52; i++) {
            m_weeklyHistory[i] = SPerformanceMetric();
        }
        
        m_overallMetrics.Reset();
    }
    
    ~CPerformanceMonitor() {
        Deinitialize();
    }
    
    //+------------------------------------------------------------------+
    //| Initialization methods                                           |
    //+------------------------------------------------------------------+
    bool Initialize(CPositionManager* positionManager = NULL, CRiskManager* riskManager = NULL) {
        if(m_initialized) {
            LogInfo("Performance Monitor already initialized");
            return true;
        }
        
        LogInfo("Initializing Performance Monitor...");
        
        // Initialize components
        m_logger = GlobalLogger;
        m_dateTimeUtils = GlobalDateTimeUtils;
        m_arrayUtils = GlobalArrayUtils;
        m_mathUtils = GlobalMathUtils;
        m_positionManager = positionManager;
        m_riskManager = riskManager;
        
        if(m_logger == NULL) {
            Print("ERROR: Logger not initialized");
            return false;
        }
        
        // Load historical data if available
        LoadHistoricalData();
        
        m_initialized = true;
        LogInfo("Performance Monitor initialized successfully");
        
        return true;
    }
    
    void Deinitialize() {
        if(!m_initialized) return;
        
        LogInfo("Deinitializing Performance Monitor...");
        
        // Save historical data
        SaveHistoricalData();
        
        m_positionManager = NULL;
        m_riskManager = NULL;
        m_initialized = false;
        
        LogInfo("Performance Monitor deinitialized");
    }
    
    //+------------------------------------------------------------------+
    //| Strategy registration and tracking                               |
    //+------------------------------------------------------------------+
    bool RegisterStrategy(string strategyName) {
        if(m_strategyCount >= 50) {
            LogError("Cannot register strategy - maximum limit reached (50)");
            return false;
        }
        
        // Check if strategy already registered
        for(int i = 0; i < m_strategyCount; i++) {
            if(m_strategies[i].strategyName == strategyName) {
                LogWarn("Strategy already registered: " + strategyName);
                return true;
            }
        }
        
        // Register new strategy
        m_strategies[m_strategyCount].strategyName = strategyName;
        m_strategies[m_strategyCount].currentEquity = AccountInfoDouble(ACCOUNT_BALANCE);
        m_strategyCount++;
        
        LogInfo("Strategy registered: " + strategyName);
        return true;
    }
    
    bool UnregisterStrategy(string strategyName) {
        int index = -1;
        
        // Find strategy
        for(int i = 0; i < m_strategyCount; i++) {
            if(m_strategies[i].strategyName == strategyName) {
                index = i;
                break;
            }
        }
        
        if(index < 0) {
            LogWarn("Strategy not found for unregistering: " + strategyName);
            return false;
        }
        
        // Shift remaining strategies
        for(int i = index; i < m_strategyCount - 1; i++) {
            m_strategies[i] = m_strategies[i + 1];
        }
        
        m_strategyCount--;
        LogInfo("Strategy unregistered: " + strategyName);
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Trade recording methods                                          |
    //+------------------------------------------------------------------+
    void RecordTrade(ulong ticket, ulong magic, string symbol, ENUM_ORDER_TYPE type,
                    double volume, double openPrice, double closePrice, double profit,
                    datetime openTime, datetime closeTime, string strategyName, string comment = "") {
        if(!m_enabled || !m_initialized) return;
        
        STradeRecord trade;
        trade.ticket = ticket;
        trade.magic = magic;
        trade.symbol = symbol;
        trade.type = type;
        trade.volume = volume;
        trade.openPrice = openPrice;
        trade.closePrice = closePrice;
        trade.profit = profit;
        trade.openTime = openTime;
        trade.closeTime = closeTime;
        trade.duration = (closeTime - openTime) / 3600.0;
        trade.strategyName = strategyName;
        trade.comment = comment;
        
        // Calculate commission and swap (simplified)
        trade.commission = MathAbs(profit) * 0.0001;
        trade.swap = 0;
        
        // Add to global history
        m_tradeHistory[m_tradeIndex] = trade;
        m_tradeIndex = (m_tradeIndex + 1) % 5000;
        
        // Add to strategy history
        int strategyIndex = FindStrategyIndex(strategyName);
        if(strategyIndex >= 0) {
            m_strategies[strategyIndex].AddTrade(trade);
        }
        
        // Update metrics
        UpdateMetrics();
        
        LogDebug(StringFormat("Trade recorded: %I64u %s %.2f P/L: %.2f", 
                             ticket, symbol, volume, profit));
    }
    
    void RecordPositionClosed(ulong ticket, double profit, datetime closeTime) {
        if(!m_enabled || !m_initialized) return;
        
        // Find trade in history and update close information
        for(int i = 0; i < 5000; i++) {
            if(m_tradeHistory[i].ticket == ticket && m_tradeHistory[i].closeTime == 0) {
                m_tradeHistory[i].closeTime = closeTime;
                m_tradeHistory[i].profit = profit;
                m_tradeHistory[i].duration = (closeTime - m_tradeHistory[i].openTime) / 3600.0;
                break;
            }
        }
        
        UpdateMetrics();
    }
    
    //+------------------------------------------------------------------+
    //| Performance update methods                                       |
    //+------------------------------------------------------------------+
    void Update() {
        if(!m_enabled || !m_initialized) return;
        
        datetime currentTime = TimeCurrent();
        if(m_autoUpdate && (currentTime - m_lastUpdate) >= m_updateInterval) {
            UpdateMetrics();
            m_lastUpdate = currentTime;
        }
    }
    
    void UpdateMetrics() {
        // Update overall metrics
        UpdateOverallMetrics();
        
        // Update strategy metrics
        for(int i = 0; i < m_strategyCount; i++) {
            m_strategies[i].UpdateMetrics();
        }
        
        // Update historical metrics at appropriate intervals
        UpdateHistoricalMetrics();
        
        LogDebug("Performance metrics updated");
    }
    
    //+------------------------------------------------------------------+
    //| Performance query methods                                        |
    //+------------------------------------------------------------------+
    SPerformanceMetric GetOverallMetrics(ENUM_PERFORMANCE_PERIOD period = PERFORMANCE_PERIOD_ALLTIME) {
        if(!m_initialized) {
            SPerformanceMetric empty;
            return empty;
        }
        
        switch(period) {
            case PERFORMANCE_PERIOD_DAILY:
                return GetDailyMetrics();
            case PERFORMANCE_PERIOD_WEEKLY:
                return GetWeeklyMetrics();
            case PERFORMANCE_PERIOD_MONTHLY:
                return GetMonthlyMetrics();
            case PERFORMANCE_PERIOD_QUARTERLY:
                return GetQuarterlyMetrics();
            case PERFORMANCE_PERIOD_YEARLY:
                return GetYearlyMetrics();
            default:
                return m_overallMetrics;
        }
    }
    
    SPerformanceMetric GetStrategyMetrics(string strategyName, ENUM_PERFORMANCE_PERIOD period = PERFORMANCE_PERIOD_ALLTIME) {
        SPerformanceMetric empty;
        if(!m_initialized) return empty;
        
        int index = FindStrategyIndex(strategyName);
        if(index < 0) return empty;
        
        switch(period) {
            case PERFORMANCE_PERIOD_DAILY:
                return m_strategies[index].dailyMetrics;
            case PERFORMANCE_PERIOD_WEEKLY:
                return m_strategies[index].weeklyMetrics;
            case PERFORMANCE_PERIOD_MONTHLY:
                return m_strategies[index].monthlyMetrics;
            default:
                return m_strategies[index].allTimeMetrics;
        }
    }
    
    bool GetStrategyList(string &strategies[]) {
        if(!m_initialized) return false;
        
        ArrayResize(strategies, m_strategyCount);
        for(int i = 0; i < m_strategyCount; i++) {
            strategies[i] = m_strategies[i].strategyName;
        }
        
        return m_strategyCount > 0;
    }
    
    SPerformanceMetric GetBestPerformingStrategy(ENUM_PERFORMANCE_PERIOD period = PERFORMANCE_PERIOD_ALLTIME) {
        SPerformanceMetric best;
        best.performanceScore = -1;
        
        if(!m_initialized) return best;
        
        for(int i = 0; i < m_strategyCount; i++) {
                        SPerformanceMetric metrics = GetStrategyMetrics(m_strategies[i].strategyName, period);
            if(metrics.performanceScore > best.performanceScore) {
                best = metrics;
            }
        }
        
        return best;
    }
    
    SPerformanceMetric GetWorstPerformingStrategy(ENUM_PERFORMANCE_PERIOD period = PERFORMANCE_PERIOD_ALLTIME) {
        SPerformanceMetric worst;
        worst.performanceScore = 101; // Higher than max
        
        if(!m_initialized) return worst;
        
        for(int i = 0; i < m_strategyCount; i++) {
            SPerformanceMetric metrics = GetStrategyMetrics(m_strategies[i].strategyName, period);
            if(metrics.performanceScore < worst.performanceScore) {
                worst = metrics;
            }
        }
        
        return worst;
    }
    
    //+------------------------------------------------------------------+
    //| Report generation methods                                        |
    //+------------------------------------------------------------------+
    SPerformanceReport GenerateDailyReport() {
        SPerformanceReport report;
        report.reportId = "DAILY_" + TimeToString(TimeCurrent(), TIME_DATE);
        report.reportDate = TimeCurrent();
        report.overallMetrics = GetDailyMetrics();
        report.periodMetrics = GetDailyMetrics();
        report.analysis = GenerateDailyAnalysis();
        report.recommendations = GenerateDailyRecommendations();
        report.hasImprovements = (report.overallMetrics.performanceScore < 70);
        
        // Add strategy performance
        ArrayResize(report.strategies, m_strategyCount);
        ArrayResize(report.strategyReturns, m_strategyCount);
        
        for(int i = 0; i < m_strategyCount; i++) {
            report.strategies[i] = m_strategies[i].strategyName;
            report.strategyReturns[i] = m_strategies[i].dailyMetrics.netProfit;
        }
        
        LogInfo("Daily performance report generated");
        return report;
    }
    
    SPerformanceReport GenerateWeeklyReport() {
        SPerformanceReport report;
        report.reportId = "WEEKLY_" + TimeToString(TimeCurrent(), TIME_DATE);
        report.reportDate = TimeCurrent();
        report.overallMetrics = GetWeeklyMetrics();
        report.periodMetrics = GetWeeklyMetrics();
        report.analysis = GenerateWeeklyAnalysis();
        report.recommendations = GenerateWeeklyRecommendations();
        report.hasImprovements = (report.overallMetrics.performanceScore < 70);
        
        LogInfo("Weekly performance report generated");
        return report;
    }
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetEnabled(bool enabled) {
        if(m_enabled != enabled) {
            m_enabled = enabled;
            LogInfo("Performance Monitor " + (enabled ? "enabled" : "disabled"));
        }
    }
    
    bool IsEnabled() const {
        return m_enabled;
    }
    
    void SetAutoUpdate(bool autoUpdate) {
        if(m_autoUpdate != autoUpdate) {
            m_autoUpdate = autoUpdate;
            LogInfo("Auto-update " + (autoUpdate ? "enabled" : "disabled"));
        }
    }
    
    void SetUpdateInterval(int seconds) {
        if(seconds > 0 && seconds != m_updateInterval) {
            m_updateInterval = seconds;
            LogInfo("Update interval set to " + IntegerToString(seconds) + " seconds");
        }
    }
    
    //+------------------------------------------------------------------+
    //| Information and reporting methods                                |
    //+------------------------------------------------------------------+
    void PrintPerformanceSummary() const {
        if(m_logger == NULL) return;
        
        string summary = StringFormat(
            "=== PERFORMANCE SUMMARY ===\n" +
            "Overall Score: %.1f (%s)\n" +
            "Total Trades: %d | Win Rate: %.1f%%\n" +
            "Net Profit: %.2f | Profit Factor: %.2f\n" +
            "Max Drawdown: %.2f (%.1f%%)\n" +
            "Active Strategies: %d\n" +
            "Last Update: %s",
            m_overallMetrics.performanceScore,
            m_overallMetrics.performanceGrade,
            m_overallMetrics.totalTrades,
            m_overallMetrics.winRate,
            m_overallMetrics.netProfit,
            m_overallMetrics.profitFactor,
            m_overallMetrics.maxDrawdown,
            m_overallMetrics.maxDrawdownPercent,
            m_strategyCount,
            TimeToString(m_overallMetrics.lastUpdate)
        );
        
        m_logger.Info(summary, "PerformanceMonitor");
    }
    
    void PrintStrategyPerformance() const {
        if(m_logger == NULL) return;
        
        m_logger.Info("=== STRATEGY PERFORMANCE ===", "PerformanceMonitor");
        
        for(int i = 0; i < m_strategyCount; i++) {
            string strategyInfo = StringFormat(
                "%s: Score %.1f (%s) | Trades: %d | Win Rate: %.1f%% | P/L: %.2f",
                m_strategies[i].strategyName,
                m_strategies[i].allTimeMetrics.performanceScore,
                m_strategies[i].allTimeMetrics.performanceGrade,
                m_strategies[i].allTimeMetrics.totalTrades,
                m_strategies[i].allTimeMetrics.winRate,
                m_strategies[i].allTimeMetrics.netProfit
            );
            m_logger.Info(strategyInfo, "PerformanceMonitor");
        }
        
        if(m_strategyCount == 0) {
            m_logger.Info("No strategies registered", "PerformanceMonitor");
        }
    }
    
    void SaveReportToFile(string filename, const SPerformanceReport &report) {
        int file_handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
        
        if(file_handle == INVALID_HANDLE) {
            LogError("Cannot open file for writing: " + filename);
            return;
        }
        
        // Write report header
        FileWrite(file_handle, "Performance Report", report.reportId);
        FileWrite(file_handle, "Report Date", TimeToString(report.reportDate, TIME_DATE|TIME_SECONDS));
        FileWrite(file_handle, "", "");
        
        // Write overall metrics
        FileWrite(file_handle, "=== OVERALL PERFORMANCE ===", "");
        FileWrite(file_handle, "Performance Score", DoubleToString(report.overallMetrics.performanceScore, 1));
        FileWrite(file_handle, "Performance Grade", report.overallMetrics.performanceGrade);
        FileWrite(file_handle, "Total Trades", IntegerToString(report.overallMetrics.totalTrades));
        FileWrite(file_handle, "Win Rate", DoubleToString(report.overallMetrics.winRate, 1) + "%");
        FileWrite(file_handle, "Net Profit", DoubleToString(report.overallMetrics.netProfit, 2));
        FileWrite(file_handle, "Profit Factor", DoubleToString(report.overallMetrics.profitFactor, 2));
        FileWrite(file_handle, "Max Drawdown", DoubleToString(report.overallMetrics.maxDrawdown, 2));
        FileWrite(file_handle, "Max Drawdown %", DoubleToString(report.overallMetrics.maxDrawdownPercent, 1) + "%");
        FileWrite(file_handle, "Sharpe Ratio", DoubleToString(report.overallMetrics.sharpeRatio, 2));
        FileWrite(file_handle, "Recovery Factor", DoubleToString(report.overallMetrics.recoveryFactor, 2));
        FileWrite(file_handle, "", "");
        
        // Write strategy performance
        if(ArraySize(report.strategies) > 0) {
            FileWrite(file_handle, "=== STRATEGY PERFORMANCE ===", "");
            for(int i = 0; i < ArraySize(report.strategies); i++) {
                FileWrite(file_handle, report.strategies[i], DoubleToString(report.strategyReturns[i], 2));
            }
            FileWrite(file_handle, "", "");
        }
        
        // Write analysis and recommendations
        FileWrite(file_handle, "=== ANALYSIS ===", "");
        FileWrite(file_handle, report.analysis, "");
        FileWrite(file_handle, "", "");
        
        if(report.hasImprovements) {
            FileWrite(file_handle, "=== RECOMMENDATIONS ===", "");
            FileWrite(file_handle, report.recommendations, "");
        }
        
        FileClose(file_handle);
        LogInfo("Performance report saved to: " + filename);
    }
    
private:
    //+------------------------------------------------------------------+
    //| Internal helper methods                                          |
    //+------------------------------------------------------------------+
    int FindStrategyIndex(string strategyName) {
        for(int i = 0; i < m_strategyCount; i++) {
            if(m_strategies[i].strategyName == strategyName) {
                return i;
            }
        }
        return -1;
    }
    
    void UpdateOverallMetrics() {
        SPerformanceMetric metrics;
        metrics.Reset();
        
        // Aggregate all trades
        int totalTrades = 0;
        for(int i = 0; i < 5000; i++) {
            if(m_tradeHistory[i].ticket > 0 && m_tradeHistory[i].IsClosed()) {
                totalTrades++;
                
                if(m_tradeHistory[i].IsWin()) {
                    metrics.winningTrades++;
                    metrics.totalProfit += m_tradeHistory[i].profit;
                    metrics.largestWin = MathMax(metrics.largestWin, m_tradeHistory[i].profit);
                } else {
                    metrics.losingTrades++;
                    metrics.totalLoss += MathAbs(m_tradeHistory[i].profit);
                    metrics.largestLoss = MathMin(metrics.largestLoss, m_tradeHistory[i].profit);
                }
                
                metrics.netProfit += m_tradeHistory[i].profit;
                
                // Update duration metrics
                double duration = m_tradeHistory[i].GetDurationHours();
                if(duration > 0) {
                    if(metrics.shortestTradeDuration == 0 || duration < metrics.shortestTradeDuration) {
                        metrics.shortestTradeDuration = duration;
                    }
                    metrics.longestTradeDuration = MathMax(metrics.longestTradeDuration, duration);
                    metrics.averageTradeDuration = (metrics.averageTradeDuration * (totalTrades - 1) + duration) / totalTrades;
                }
            }
        }
        
        metrics.totalTrades = totalTrades;
        metrics.CalculateDerivedMetrics();
        
        // Update max drawdown from risk manager if available
        if(m_riskManager != NULL) {
            SRiskMetrics riskMetrics = m_riskManager.GetRiskMetrics();
            metrics.maxDrawdown = riskMetrics.maxDrawdown;
            metrics.maxDrawdownPercent = riskMetrics.maxDrawdownPercent;
        }
        
        // Calculate Sharpe ratio (simplified)
        if(metrics.standardDeviation > 0) {
            metrics.sharpeRatio = (metrics.averageTrade / metrics.standardDeviation) * MathSqrt(252);
        }
        
        m_overallMetrics = metrics;
    }
    
    void UpdateHistoricalMetrics() {
        datetime currentTime = TimeCurrent();
        MqlDateTime currentDt;
        TimeToStruct(currentTime, currentDt);
        
        // Update daily metrics at end of day
        static datetime lastDailyUpdate = 0;
        if(currentDt.hour == 23 && currentDt.min >= 55 && 
           (currentTime - lastDailyUpdate) > 3600) {
            m_dailyHistory[m_dailyIndex] = m_overallMetrics;
            m_dailyIndex = (m_dailyIndex + 1) % 365;
            lastDailyUpdate = currentTime;
        }
        
        // Update weekly metrics on Sunday
        static datetime lastWeeklyUpdate = 0;
        if(currentDt.day_of_week == 0 && currentDt.hour == 23 && 
           (currentTime - lastWeeklyUpdate) > 86400) {
            m_weeklyHistory[m_weeklyIndex] = m_overallMetrics;
            m_weeklyIndex = (m_weeklyIndex + 1) % 52;
            lastWeeklyUpdate = currentTime;
        }
    }
    
    SPerformanceMetric GetDailyMetrics() {
        // Aggregate trades from last 24 hours
        SPerformanceMetric metrics;
        metrics.Reset();
        
        datetime dayStart = TimeCurrent() - 86400;
        
        for(int i = 0; i < 5000; i++) {
            if(m_tradeHistory[i].ticket > 0 && m_tradeHistory[i].IsClosed() &&
               m_tradeHistory[i].closeTime >= dayStart) {
                
                metrics.totalTrades++;
                
                if(m_tradeHistory[i].IsWin()) {
                    metrics.winningTrades++;
                    metrics.totalProfit += m_tradeHistory[i].profit;
                } else {
                    metrics.losingTrades++;
                    metrics.totalLoss += MathAbs(m_tradeHistory[i].profit);
                }
                
                metrics.netProfit += m_tradeHistory[i].profit;
            }
        }
        
        metrics.CalculateDerivedMetrics();
        metrics.period = PERFORMANCE_PERIOD_DAILY;
        metrics.startDate = dayStart;
        metrics.endDate = TimeCurrent();
        
        return metrics;
    }
    
    SPerformanceMetric GetWeeklyMetrics() {
        // Aggregate trades from last 7 days
        SPerformanceMetric metrics;
        metrics.Reset();
        
        datetime weekStart = TimeCurrent() - 604800;
        
        for(int i = 0; i < 5000; i++) {
            if(m_tradeHistory[i].ticket > 0 && m_tradeHistory[i].IsClosed() &&
               m_tradeHistory[i].closeTime >= weekStart) {
                
                metrics.totalTrades++;
                
                if(m_tradeHistory[i].IsWin()) {
                    metrics.winningTrades++;
                    metrics.totalProfit += m_tradeHistory[i].profit;
                } else {
                    metrics.losingTrades++;
                    metrics.totalLoss += MathAbs(m_tradeHistory[i].profit);
                }
                
                metrics.netProfit += m_tradeHistory[i].profit;
            }
        }
        
        metrics.CalculateDerivedMetrics();
        metrics.period = PERFORMANCE_PERIOD_WEEKLY;
        metrics.startDate = weekStart;
        metrics.endDate = TimeCurrent();
        
        return metrics;
    }
    
    SPerformanceMetric GetMonthlyMetrics() {
        // Aggregate trades from last 30 days
        SPerformanceMetric metrics;
        metrics.Reset();
        
        datetime monthStart = TimeCurrent() - 2592000;
        
        for(int i = 0; i < 5000; i++) {
            if(m_tradeHistory[i].ticket > 0 && m_tradeHistory[i].IsClosed() &&
               m_tradeHistory[i].closeTime >= monthStart) {
                
                metrics.totalTrades++;
                
                if(m_tradeHistory[i].IsWin()) {
                    metrics.winningTrades++;
                    metrics.totalProfit += m_tradeHistory[i].profit;
                } else {
                    metrics.losingTrades++;
                    metrics.totalLoss += MathAbs(m_tradeHistory[i].profit);
                }
                
                metrics.netProfit += m_tradeHistory[i].profit;
            }
        }
        
        metrics.CalculateDerivedMetrics();
        metrics.period = PERFORMANCE_PERIOD_MONTHLY;
        metrics.startDate = monthStart;
        metrics.endDate = TimeCurrent();
        
        return metrics;
    }
    
    SPerformanceMetric GetQuarterlyMetrics() {
        // Aggregate trades from last 90 days
        SPerformanceMetric metrics;
        metrics.Reset();
        
        datetime quarterStart = TimeCurrent() - 7776000; // 90 days
        
        for(int i = 0; i < 5000; i++) {
            if(m_tradeHistory[i].ticket > 0 && m_tradeHistory[i].IsClosed() &&
               m_tradeHistory[i].closeTime >= quarterStart) {
                
                metrics.totalTrades++;
                
                if(m_tradeHistory[i].IsWin()) {
                    metrics.winningTrades++;
                    metrics.totalProfit += m_tradeHistory[i].profit;
                } else {
                    metrics.losingTrades++;
                    metrics.totalLoss += MathAbs(m_tradeHistory[i].profit);
                }
                
                metrics.netProfit += m_tradeHistory[i].profit;
            }
        }
        
        metrics.CalculateDerivedMetrics();
        metrics.period = PERFORMANCE_PERIOD_QUARTERLY;
        metrics.startDate = quarterStart;
        metrics.endDate = TimeCurrent();
        
        return metrics;
    }
    
    SPerformanceMetric GetYearlyMetrics() {
        // Aggregate trades from last 365 days
        SPerformanceMetric metrics;
        metrics.Reset();
        
        datetime yearStart = TimeCurrent() - 31536000; // 365 days
        
        for(int i = 0; i < 5000; i++) {
            if(m_tradeHistory[i].ticket > 0 && m_tradeHistory[i].IsClosed() &&
               m_tradeHistory[i].closeTime >= yearStart) {
                
                metrics.totalTrades++;
                
                if(m_tradeHistory[i].IsWin()) {
                    metrics.winningTrades++;
                    metrics.totalProfit += m_tradeHistory[i].profit;
                } else {
                    metrics.losingTrades++;
                    metrics.totalLoss += MathAbs(m_tradeHistory[i].profit);
                }
                
                metrics.netProfit += m_tradeHistory[i].profit;
            }
        }
        
        metrics.CalculateDerivedMetrics();
        metrics.period = PERFORMANCE_PERIOD_YEARLY;
        metrics.startDate = yearStart;
        metrics.endDate = TimeCurrent();
        
        return metrics;
    }
    
    string GenerateDailyAnalysis() {
        string analysis = "";
        SPerformanceMetric daily = GetDailyMetrics();
        
        if(daily.totalTrades == 0) {
            analysis = "No trades executed today.";
        } else if(daily.netProfit > 0) {
            analysis = StringFormat("Profitable day with %.2f net profit. Win rate was %.1f%%. ", 
                                  daily.netProfit, daily.winRate);
            
            if(daily.profitFactor > 3.0) {
                analysis += "Excellent profit factor indicates strong trade management.";
            } else if(daily.profitFactor > 2.0) {
                analysis += "Good profit factor shows effective risk/reward management.";
            } else {
                analysis += "Consider improving risk/reward ratios for better performance.";
            }
        } else {
            analysis = StringFormat("Loss of %.2f today. Win rate was %.1f%%. ", 
                                  MathAbs(daily.netProfit), daily.winRate);
            
            if(daily.winRate < 40.0) {
                analysis += "Low win rate suggests entry timing or strategy needs review.";
            } else {
                analysis += "Good win rate but losses too large - review stop loss placement.";
            }
        }
        
        return analysis;
    }
    
    string GenerateWeeklyAnalysis() {
        string analysis = "";
        SPerformanceMetric weekly = GetWeeklyMetrics();
        
        if(weekly.totalTrades == 0) {
            analysis = "No trades executed this week.";
        } else if(weekly.netProfit > 0) {
            analysis = StringFormat("Profitable week with %.2f net profit. ", weekly.netProfit);
            
            if(weekly.maxDrawdownPercent < 5.0) {
                analysis += "Excellent risk control with low drawdown.";
            } else if(weekly.maxDrawdownPercent < 10.0) {
                analysis += "Good risk management with acceptable drawdown.";
            } else {
                analysis += "High drawdown suggests need for better risk management.";
            }
        } else {
            analysis = StringFormat("Weekly loss of %.2f. ", MathAbs(weekly.netProfit));
            
            if(weekly.consecutiveLosses > 3) {
                analysis += "Multiple consecutive losses detected - consider strategy adjustment.";
            } else {
                analysis += "Review trade entries and exits to identify issues.";
            }
        }
        
        return analysis;
    }
    
    string GenerateDailyRecommendations() {
        string recommendations = "";
        SPerformanceMetric daily = GetDailyMetrics();
        
        if(daily.totalTrades == 0) {
            recommendations = "1. Consider increasing trading activity\n";
            recommendations += "2. Review market conditions for opportunities\n";
        } else if(daily.netProfit < 0) {
            recommendations = "1. Reduce position sizes until profitability returns\n";
            recommendations += "2. Review stop loss placement for recent losses\n";
            recommendations += "3. Consider taking a break if emotional trading is suspected\n";
            
            if(daily.winRate < 40.0) {
                recommendations += "4. Focus on improving entry accuracy\n";
                recommendations += "5. Consider using additional confirmation indicators\n";
            }
        } else {
            if(daily.profitFactor < 2.0) {
                recommendations = "1. Work on improving risk/reward ratios\n";
                recommendations += "2. Consider letting profits run longer\n";
            }
            
            if(daily.averageTradeDuration < 1.0) {
                recommendations += "3. Consider longer timeframes for better risk management\n";
            }
        }
        
        return recommendations;
    }
    
    string GenerateWeeklyRecommendations() {
        string recommendations = "";
        SPerformanceMetric weekly = GetWeeklyMetrics();
        
        if(weekly.netProfit < 0) {
            recommendations = "WEEKLY LOSS DETECTED:\n";
            recommendations += "1. Reduce trading size by 50% next week\n";
            recommendations += "2. Review all losing trades for patterns\n";
            recommendations += "3. Consider strategy pause if drawdown > 10%\n";
            recommendations += "4. Focus on highest probability setups only\n";
        } else if(weekly.maxDrawdownPercent > 15.0) {
            recommendations = "HIGH DRAWDOWN DETECTED:\n";
            recommendations += "1. Implement stricter risk management rules\n";
            recommendations += "2. Reduce position sizes by 30%\n";
            recommendations += "3. Add trailing stops to protect profits\n";
            recommendations += "4. Consider correlation between positions\n";
        } else if(weekly.profitFactor > 3.0) {
            recommendations = "EXCELLENT PERFORMANCE:\n";
            recommendations += "1. Consider gradual position size increase (max +20%)\n";
            recommendations += "2. Maintain current strategy discipline\n";
            recommendations += "3. Document successful trade patterns\n";
        }
        
        return recommendations;
    }
    
    void LoadHistoricalData() {
        // Placeholder for historical data loading
        LogDebug("Historical data loading not implemented");
    }
    
    void SaveHistoricalData() {
        // Placeholder for historical data saving
        LogDebug("Historical data saving not implemented");
    }
    
    //+------------------------------------------------------------------+
    //| Logging methods                                                  |
    //+------------------------------------------------------------------+
    void LogError(string message) {
        if(m_logger != NULL) {
            m_logger.Error(message, "PerformanceMonitor");
        } else {
            Print("ERROR [PerformanceMonitor]: " + message);
        }
    }
    
    void LogWarn(string message) {
        if(m_logger != NULL) {
            m_logger.Warn(message, "PerformanceMonitor");
        }
    }
    
    void LogInfo(string message) {
        if(m_logger != NULL) {
            m_logger.Info(message, "PerformanceMonitor");
        } else {
            Print("INFO [PerformanceMonitor]: " + message);
        }
    }
    
    void LogDebug(string message) {
        if(m_logger != NULL) {
            m_logger.Debug(message, "PerformanceMonitor");
        }
    }
};

#endif // PERFORMANCEMONITOR_MQH