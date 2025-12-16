//+------------------------------------------------------------------+
//|                                                      Solara.mq5  |
//|                        Copyright 2024, Solara Trading Platform  |
//|                                          https://www.solara.com  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, Solara Trading Platform"
#property link      "https://www.solara.com"
#property version   "1.00"
#property description "Solara - Modular Multi-Strategy Expert Advisor Platform"
#property description "Manages and executes multiple trading strategies with different timeframes"
#property description "and execution requirements."
#property strict

//+------------------------------------------------------------------+
//| Includes                                                         |
//+------------------------------------------------------------------+
#include "SolaraCore.mqh"
#include "StrategyManager.mqh"
#include "PositionManager.mqh"
#include "RiskManager.mqh"
#include "PerformanceMonitor.mqh"
#include "CommonTypes.mqh"

#include "..\Configuration\ConfigManager.mqh"
#include "..\Utilities\Logger.mqh"
#include "..\Utilities\ErrorHandler.mqh"
#include "..\Utilities\DateTimeUtils.mqh"
#include "..\Utilities\MathUtils.mqh"
#include "..\Utilities\ArrayUtils.mqh"

#include "..\Execution\OrderExecutor.mqh"
#include "..\Execution\BrokerInterface.mqh"
#include "..\MoneyManagement\MoneyManagerFactory.mqh"
#include "..\Monitoring\Dashboard.mqh"
#include "..\Monitoring\AlertSystem.mqh"

//+------------------------------------------------------------------+
//| Global instances                                                 |
//+------------------------------------------------------------------+
CSolaraCore* g_solaraCore = NULL;
CStrategyManager* g_strategyManager = NULL;
CPositionManager* g_positionManager = NULL;
CRiskManager* g_riskManager = NULL;
CPerformanceMonitor* g_performanceMonitor = NULL;
CErrorHandler* g_errorHandler = NULL;
CDateTimeUtils* g_dateTimeUtils = NULL;
CMathUtils* g_mathUtils = NULL;
CArrayUtils* g_arrayUtils = NULL;
COrderExecutor* g_orderExecutor = NULL;
CBrokerInterface* g_brokerInterface = NULL;
CMoneyManagerFactory* g_moneyManagerFactory = NULL;
CDashboard* g_dashboard = NULL;
CAlertSystem* g_alertSystem = NULL;

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input group "Platform Configuration"
input bool EnableLiveTrading = true;           // Enable live trading
input bool EnableBacktesting = false;          // Enable backtesting mode
input bool EnableOptimization = false;         // Enable optimization mode
input int  MagicNumberBase = 10000;            // Base magic number for strategies
input bool EnableLogging = true;               // Enable logging system
input int  LogLevel = 2;                       // Log level (0=Error, 1=Warn, 2=Info, 3=Debug, 4=Trace)

input group "Strategy Configuration"
input bool EnableMAStrategy = true;            // Enable Moving Average Crossover
input int MAFastPeriod = 10;                   // MA Fast period
input int MASlowPeriod = 30;                   // MA Slow period
input ENUM_MA_METHOD MAMethod = MODE_SMA;      // MA Method

input bool EnableRSIStrategy = true;           // Enable RSI Strategy
input int RSIPeriod = 14;                      // RSI Period
input double RSIOverbought = 70.0;             // RSI Overbought level
input double RSIOversold = 30.0;               // RSI Oversold level

input bool EnableBBStrategy = false;           // Enable Bollinger Bands Strategy
input int BBPeriod = 20;                       // Bollinger Bands period
input double BBDeviation = 2.0;                // Bollinger Bands deviation

input group "Risk Management"
input double MaxDailyLossPercent = 5.0;        // Maximum daily loss percentage
input double MaxDrawdownPercent = 20.0;        // Maximum drawdown percentage
input double MaxPositionRiskPercent = 2.0;     // Maximum risk per position percentage
input bool EnableCircuitBreakers = true;       // Enable automatic circuit breakers
input double RiskPerTradePercent = 1.0;        // Risk per trade percentage

input group "Execution Settings"
input int MaxSlippagePoints = 10;              // Maximum slippage in points
input bool EnableECNMode = false;              // Enable ECN execution mode
input int MaxRetryAttempts = 3;                // Maximum order retry attempts
input int RetryDelayMs = 1000;                 // Delay between retries in milliseconds
input double MaxLotSize = 10.0;                // Maximum lot size per trade
input double MinLotSize = 0.01;                // Minimum lot size per trade

input group "Money Management"
input ENUM_MONEY_MANAGEMENT MoneyManagementType = MM_FIXED_FRACTIONAL; // Money management type
input double FixedLotSize = 0.1;               // Fixed lot size (if using fixed lots)
input double RiskPercentage = 2.0;             // Risk percentage (if using fixed fractional)

input group "Monitoring & Alerts"
input bool EnableDashboard = true;             // Enable trading dashboard
input int DashboardUpdateInterval = 5;         // Dashboard update interval in seconds
input bool EnableEmailAlerts = false;          // Enable email alerts
input string EmailAddress = "";                // Email address for alerts
input bool EnablePushNotifications = false;    // Enable push notifications
input bool EnableSoundAlerts = true;           // Enable sound alerts

input group "Trading Hours"
input bool RestrictTradingHours = false;       // Restrict trading to specific hours
input int TradingStartHour = 0;                // Trading start hour (0-23)
input int TradingEndHour = 23;                 // Trading end hour (0-23)
input bool SkipWeekends = true;                // Skip trading on weekends

input group "Symbol Configuration"
input string TradingSymbol = "";               // Trading symbol (empty = current chart)
input ENUM_TIMEFRAMES TradingTimeframe = PERIOD_CURRENT; // Trading timeframe

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    // Initialize random seed
    MathSrand(GetTickCount());
    
    // Set symbol and timeframe
    string symbol = (TradingSymbol == "") ? _Symbol : TradingSymbol;
    ENUM_TIMEFRAMES timeframe = (TradingTimeframe == PERIOD_CURRENT) ? _Period : TradingTimeframe;
    
    // Initialize global components
    if(!InitializeGlobalComponents())
    {
        Print("Failed to initialize global components");
        return INIT_FAILED;
    }
    
    // Initialize configuration manager
    CConfigManager* configManager = CConfigManager::Instance();
    if(configManager == NULL || !configManager.Initialize())
    {
        Print("Failed to initialize configuration manager");
        return INIT_FAILED;
    }
    
    // Load and apply configuration
    LoadAndApplyConfiguration();
    
    // Initialize Solara core
    g_solaraCore = new CSolaraCore();
    if(g_solaraCore == NULL)
    {
        Print("Failed to create Solara core instance");
        return INIT_FAILED;
    }
    
    if(!g_solaraCore.Initialize(symbol, timeframe))
    {
        Print("Failed to initialize Solara core");
        delete g_solaraCore;
        g_solaraCore = NULL;
        return INIT_FAILED;
    }
    
    // Initialize strategy manager
    g_strategyManager = g_solaraCore.GetStrategyManager();
    if(g_strategyManager == NULL)
    {
        Print("Failed to get strategy manager");
        return INIT_FAILED;
    }
    
    // Initialize position manager
    g_positionManager = g_solaraCore.GetPositionManager();
    if(g_positionManager == NULL)
    {
        Print("Failed to get position manager");
        return INIT_FAILED;
    }
    
    // Initialize risk manager
    g_riskManager = g_solaraCore.GetRiskManager();
    if(g_riskManager == NULL)
    {
        Print("Failed to get risk manager");
        return INIT_FAILED;
    }
    
    // Initialize performance monitor
    g_performanceMonitor = g_solaraCore.GetPerformanceMonitor();
    if(g_performanceMonitor == NULL)
    {
        Print("Failed to get performance monitor");
        return INIT_FAILED;
    }
    
    // Initialize execution components
    if(!InitializeExecutionComponents())
    {
        Print("Failed to initialize execution components");
        return INIT_FAILED;
    }
    
    // Initialize monitoring components
    if(!InitializeMonitoringComponents())
    {
        Print("Failed to initialize monitoring components");
        return INIT_FAILED;
    }
    
    // Create and register strategies
    if(!CreateAndRegisterStrategies())
    {
        Print("Warning: Some strategies failed to create or register");
    }
    
    // Start all enabled strategies
    if(!StartEnabledStrategies())
    {
        Print("Warning: Some strategies failed to start");
    }
    
    // Set timer for periodic updates
    EventSetTimer(1);
    
    Print("==========================================");
    Print("Solara Expert Advisor initialized successfully");
    Print("Platform version: 1.0");
    Print("Account: ", AccountInfoString(ACCOUNT_NAME));
    Print("Balance: ", AccountInfoDouble(ACCOUNT_BALANCE));
    Print("Equity: ", AccountInfoDouble(ACCOUNT_EQUITY));
    Print("Leverage: 1:", AccountInfoInteger(ACCOUNT_LEVERAGE));
    Print("Symbol: ", symbol);
    Print("Timeframe: ", TimeframeToStringLocal(timeframe));
    Print("==========================================");
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("Solara Expert Advisor deinitializing... Reason: ", GetDeinitReasonText(reason));
    
    // Stop timer
    EventKillTimer();
    
    // Stop all strategies
    StopAllStrategies();
    
    // Cleanup strategy instances
    CleanupStrategyInstances();
    
    // Deinitialize components in reverse order
    DeinitializeMonitoringComponents();
    DeinitializeExecutionComponents();
    
    // Deinitialize Solara core
    if(g_solaraCore != NULL)
    {
        g_solaraCore.Deinitialize();
        delete g_solaraCore;
        g_solaraCore = NULL;
    }
    
    // Deinitialize configuration manager
    CConfigManager* configManager = CConfigManager::Instance();
    if(configManager != NULL)
    {
        configManager.Deinitialize();
    }
    
    // Cleanup global components
    CleanupGlobalComponents();
    
    Print("Solara Expert Advisor deinitialized successfully");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // Check if trading is allowed
    if(!IsTradingAllowed())
    {
        return;
    }
    
    // Update market data
    UpdateMarketData();
    
    // Process strategy manager tick
    if(g_strategyManager != NULL)
    {
        g_strategyManager.OnTick();
    }
    
    // Update position manager
    if(g_positionManager != NULL)
    {
        g_positionManager.OnTick();
    }
    
    // Update risk manager
    if(g_riskManager != NULL)
    {
        g_riskManager.OnTick();
    }
    
    // Update performance monitor
    if(g_performanceMonitor != NULL)
    {
        g_performanceMonitor.OnTick();
    }
    
    // Update dashboard
    if(g_dashboard != NULL)
    {
        g_dashboard.OnTick();
    }
    
    // Process pending orders
    ProcessPendingOrders();
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
    // Process strategy manager timer events
    if(g_strategyManager != NULL)
    {
        g_strategyManager.OnTimer();
    }
    
    // Update dashboard periodically
    static datetime lastDashboardUpdate = 0;
    datetime currentTime = TimeCurrent();
    
    if(g_dashboard != NULL && (currentTime - lastDashboardUpdate) >= DashboardUpdateInterval)
    {
        g_dashboard.Update();
        lastDashboardUpdate = currentTime;
    }
    
    // Check for alerts
    if(g_alertSystem != NULL)
    {
        g_alertSystem.CheckAlerts();
    }
    
    // Update performance statistics
    if(g_performanceMonitor != NULL)
    {
        g_performanceMonitor.UpdateStatistics();
    }
    
    // Check risk limits
    if(g_riskManager != NULL)
    {
        g_riskManager.CheckRiskLimits();
    }
    
    // Generate periodic reports
    GeneratePeriodicReports();
}

//+------------------------------------------------------------------+
//| Trade transaction function                                        |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                       const MqlTradeRequest& request,
                       const MqlTradeResult& result)
{
    // Process transaction through strategy manager
    if(g_strategyManager != NULL)
    {
        g_strategyManager.OnTradeTransaction(trans, request, result);
    }
    
    // Update position manager
    if(g_positionManager != NULL)
    {
        g_positionManager.OnTradeTransaction(trans, request, result);
    }
    
    // Update risk manager
    if(g_riskManager != NULL)
    {
        g_riskManager.OnTradeTransaction(trans, request, result);
    }
    
    // Update performance monitor
    if(g_performanceMonitor != NULL)
    {
        g_performanceMonitor.OnTradeTransaction(trans, request, result);
    }
    
    // Send alert if needed
    if(g_alertSystem != NULL)
    {
        g_alertSystem.OnTradeTransaction(trans, request, result);
    }
    
    // Log trade transaction
    LogTradeTransaction(trans, request, result);
}

//+------------------------------------------------------------------+
//| Chart event function                                             |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long &lparam,
                  const double &dparam,
                  const string &sparam)
{
    // Pass chart events to dashboard
    if(g_dashboard != NULL)
    {
        g_dashboard.OnChartEvent(id, lparam, dparam, sparam);
    }
    
    // Handle custom chart events
    HandleCustomChartEvents(id, lparam, dparam, sparam);
}

//+------------------------------------------------------------------+
//| Helper functions                                                 |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Initialize global components                                     |
//+------------------------------------------------------------------+
bool InitializeGlobalComponents()
{
    // Initialize global logger
    InitializeGlobalLogger((ENUM_LOG_LEVEL)LogLevel);
    
    // Initialize global error handler
    g_errorHandler = new CErrorHandler();
    if(g_errorHandler == NULL)
    {
        Print("Failed to create error handler");
        return false;
    }
    
    if(!g_errorHandler.Initialize())
    {
        Print("Failed to initialize error handler");
        return false;
    }
    
    // Initialize global date time utils
    g_dateTimeUtils = new CDateTimeUtils();
    if(g_dateTimeUtils == NULL)
    {
        Print("Failed to create date time utils");
        return false;
    }
    
    if(!g_dateTimeUtils.Initialize())
    {
        Print("Failed to initialize date time utils");
        return false;
    }
    
    // Initialize global math utils
    g_mathUtils = new CMathUtils();
    if(g_mathUtils == NULL)
    {
        Print("Failed to create math utils");
        return false;
    }
    
    if(!g_mathUtils.Initialize())
    {
        Print("Failed to initialize math utils");
        return false;
    }
    
    // Initialize global array utils
    g_arrayUtils = new CArrayUtils();
    if(g_arrayUtils == NULL)
    {
        Print("Failed to create array utils");
        return false;
    }
    
    if(!g_arrayUtils.Initialize())
    {
        Print("Failed to initialize array utils");
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Cleanup global components                                        |
//+------------------------------------------------------------------+
void CleanupGlobalComponents()
{
    // Cleanup global array utils
    if(g_arrayUtils != NULL)
    {
        delete g_arrayUtils;
        g_arrayUtils = NULL;
    }
    
    // Cleanup global math utils
    if(g_mathUtils != NULL)
    {
        delete g_mathUtils;
        g_mathUtils = NULL;
    }
    
    // Cleanup global date time utils
    if(g_dateTimeUtils != NULL)
    {
        delete g_dateTimeUtils;
        g_dateTimeUtils = NULL;
    }
    
    // Cleanup global error handler
    if(g_errorHandler != NULL)
    {
        g_errorHandler.Deinitialize();
        delete g_errorHandler;
        g_errorHandler = NULL;
    }
    
    // Cleanup global logger
    CleanupGlobalLogger();
}

//+------------------------------------------------------------------+
//| Load and apply configuration                                     |
//+------------------------------------------------------------------+
void LoadAndApplyConfiguration()
{
    CConfigManager* configManager = CConfigManager::Instance();
    if(configManager == NULL) return;
    
    // Get global settings
    SGlobalSettings globalSettings = configManager.GetGlobalSettings();
    
    // Apply input parameters to configuration
    globalSettings.enableLogging = EnableLogging;
    globalSettings.logLevel = (ENUM_LOG_LEVEL)LogLevel;
    globalSettings.enableEmailAlerts = EnableEmailAlerts;
    globalSettings.emailAddress = EmailAddress;
    globalSettings.restrictTradingHours = RestrictTradingHours;
    globalSettings.tradingStartHour = TradingStartHour;
    globalSettings.tradingEndHour = TradingEndHour;
    globalSettings.skipWeekends = SkipWeekends;
    globalSettings.maxDailyLossPercent = MaxDailyLossPercent;
    globalSettings.maxPositionRiskPercent = MaxPositionRiskPercent;
    globalSettings.maxDrawdownPercent = MaxDrawdownPercent;
    globalSettings.maxLeverage = (double)AccountInfoInteger(ACCOUNT_LEVERAGE);
    globalSettings.enableCircuitBreakers = EnableCircuitBreakers;
    globalSettings.maxSlippagePoints = MaxSlippagePoints;
    globalSettings.magicNumberBase = MagicNumberBase;
    globalSettings.enableECNMode = EnableECNMode;
    globalSettings.maxRetryAttempts = MaxRetryAttempts;
    globalSettings.retryDelayMs = RetryDelayMs;
    globalSettings.enableDashboard = EnableDashboard;
    globalSettings.dashboardUpdateInterval = DashboardUpdateInterval;
    globalSettings.generateDailyReports = EnableEmailAlerts;
    globalSettings.reportEmail = EmailAddress;
    
    // Update configuration
    configManager.SetGlobalSettings(globalSettings);
    
    // Save configuration
    configManager.SaveGlobalSettings();

}

//+------------------------------------------------------------------+
//| Initialize execution components                                  |
//+------------------------------------------------------------------+
bool InitializeExecutionComponents()
{
    // Initialize broker interface
    g_brokerInterface = new CBrokerInterface();
    if(g_brokerInterface == NULL)
    {
        Print("Failed to create broker interface");
        return false;
    }
    
    if(!g_brokerInterface.Initialize())
    {
        Print("Failed to initialize broker interface");
        return false;
    }
    
    // Initialize order executor
    g_orderExecutor = new COrderExecutor();
    if(g_orderExecutor == NULL)
    {
        Print("Failed to create order executor");
        return false;
    }
    
    if(!g_orderExecutor.Initialize())
    {
        Print("Failed to initialize order executor");
        return false;
    }
    
    // Initialize money manager factory
    g_moneyManagerFactory = new CMoneyManagerFactory();
    if(g_moneyManagerFactory == NULL)
    {
        Print("Failed to create money manager factory");
        return false;
    }
    
    if(!g_moneyManagerFactory.Initialize())
    {
        Print("Failed to initialize money manager factory");
        return false;
    }
    
    // Configure money management
    SMoneyManagementConfig mmConfig;
    mmConfig.moneyManagementType = MoneyManagementType;
    mmConfig.fixedLotSize = FixedLotSize;
    mmConfig.riskPercentage = RiskPercentage;
    mmConfig.maxLotSize = MaxLotSize;
    mmConfig.minLotSize = MinLotSize;
    mmConfig.accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    
    g_moneyManagerFactory.Configure(mmConfig);
    
    return true;
}

//+------------------------------------------------------------------+
//| Initialize monitoring components                                 |
//+------------------------------------------------------------------+
bool InitializeMonitoringComponents()
{
    // Initialize alert system
    g_alertSystem = new CAlertSystem();
    if(g_alertSystem == NULL)
    {
        Print("Failed to create alert system");
        return false;
    }
    
    if(!g_alertSystem.Initialize())
    {
        Print("Failed to initialize alert system");
        return false;
    }
    
    // Configure alerts
    SAlertConfig alertConfig;
    alertConfig.enableEmailAlerts = EnableEmailAlerts;
    alertConfig.emailAddress = EmailAddress;
    alertConfig.enablePushNotifications = EnablePushNotifications;
    alertConfig.enableSoundAlerts = EnableSoundAlerts;
    
    g_alertSystem.Configure(alertConfig);
    
    // Initialize dashboard if enabled
    if(EnableDashboard)
    {
        g_dashboard = new CDashboard();
        if(g_dashboard == NULL)
        {
            Print("Failed to create dashboard");
            return false;
        }
        
        if(!g_dashboard.Initialize())
        {
            Print("Failed to initialize dashboard");
            return false;
        }
        
        // Configure dashboard
        SDashboardConfig dashboardConfig;
        dashboardConfig.updateInterval = DashboardUpdateInterval;
        dashboardConfig.showPositions = true;
        dashboardConfig.showPerformance = true;
        dashboardConfig.showRiskMetrics = true;
        
        g_dashboard.Configure(dashboardConfig);
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Create and register strategies                                   |
//+------------------------------------------------------------------+
bool CreateAndRegisterStrategies()
{
    if(g_strategyManager == NULL) return false;
    
    bool success = true;
    
    // Strategy creation placeholder
    // Actual strategy classes need to be implemented
    
    return success;
}

//+------------------------------------------------------------------+
//| Start enabled strategies                                         |
//+------------------------------------------------------------------+
bool StartEnabledStrategies()
{
    if(g_strategyManager == NULL) return false;
    
    // Initialize all strategies
    if(!g_strategyManager.InitializeAllStrategies())
    {
        Print("Warning: Some strategies failed to initialize");
    }
    
    // Start all strategies
    if(!g_strategyManager.StartAllStrategies())
    {
        Print("Warning: Some strategies failed to start");
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Stop all strategies                                              |
//+------------------------------------------------------------------+
void StopAllStrategies()
{
    if(g_strategyManager != NULL)
    {
        g_strategyManager.StopAllStrategies();
    }
}

//+------------------------------------------------------------------+
//| Cleanup strategy instances                                       |
//+------------------------------------------------------------------+
void CleanupStrategyInstances()
{
    // Strategy cleanup placeholder
}

//+------------------------------------------------------------------+
//| Deinitialize execution components                                |
//+------------------------------------------------------------------+
void DeinitializeExecutionComponents()
{
    if(g_orderExecutor != NULL)
    {
        g_orderExecutor.Deinitialize();
        delete g_orderExecutor;
        g_orderExecutor = NULL;
    }
    
    if(g_brokerInterface != NULL)
    {
        g_brokerInterface.Deinitialize();
        delete g_brokerInterface;
        g_brokerInterface = NULL;
    }
    
    if(g_moneyManagerFactory != NULL)
    {
        delete g_moneyManagerFactory;
        g_moneyManagerFactory = NULL;
    }
}

//+------------------------------------------------------------------+
//| Deinitialize monitoring components                               |
//+------------------------------------------------------------------+
void DeinitializeMonitoringComponents()
{
    if(g_dashboard != NULL)
    {
        g_dashboard.Deinitialize();
        delete g_dashboard;
        g_dashboard = NULL;
    }
    
    if(g_alertSystem != NULL)
    {
        g_alertSystem.Deinitialize();
        delete g_alertSystem;
        g_alertSystem = NULL;
    }
}

//+------------------------------------------------------------------+
//| Check if trading is allowed                                      |
//+------------------------------------------------------------------+
bool IsTradingAllowed()
{
    // Check if live trading is enabled
    if(!EnableLiveTrading)
    {
        return false;
    }
    
    // Check trading hours if restricted
    if(RestrictTradingHours)
    {
        MqlDateTime dt;
        TimeCurrent(dt);
        
        // Check if current time is within trading hours
        if(dt.hour < TradingStartHour || dt.hour >= TradingEndHour)
        {
            return false;
        }
    }
    
    // Skip weekends if enabled
    if(SkipWeekends)
    {
        MqlDateTime dt;
        TimeCurrent(dt);
        
        // 0=Sunday, 6=Saturday
        if(dt.day_of_week == 0 || dt.day_of_week == 6)
        {
            return false;
        }
    }
    
    // Check risk limits
    if(g_riskManager != NULL)
    {
        if(!g_riskManager.IsTradingAllowed())
        {
            return false;
        }
    }
    
    // Check if market is open
    if(!IsMarketOpen())
    {
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Check if market is open                                          |
//+------------------------------------------------------------------+
bool IsMarketOpen()
{
    // Check if symbol is selected
    if(!SymbolInfoInteger(_Symbol, SYMBOL_SELECT))
    {
        return false;
    }
    
    // Check if market is open (simplified check)
    datetime currentTime = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);
    
    // Basic market hours check
    if(dt.day_of_week == 5 && dt.hour >= 22) // Friday after 10 PM
    {
        return false;
    }
    
    if(dt.day_of_week == 6) // Saturday
    {
        return false;
    }
    
    if(dt.day_of_week == 0 && dt.hour < 22) // Sunday before 10 PM
    {
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Update market data                                               |
//+------------------------------------------------------------------+
void UpdateMarketData()
{
    // Placeholder for market data updates
    static datetime lastUpdate = 0;
    datetime currentTime = TimeCurrent();
    
    // Update every 5 seconds
    if((currentTime - lastUpdate) >= 5)
    {
        lastUpdate = currentTime;
    }
}

//+------------------------------------------------------------------+
//| Process pending orders                                           |
//+------------------------------------------------------------------+
void ProcessPendingOrders()
{
    if(g_orderExecutor == NULL) return;
    
    // Placeholder for pending order processing
}

//+------------------------------------------------------------------+
//| Log trade transaction                                            |
//+------------------------------------------------------------------+
void LogTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
    if(g_errorHandler == NULL) return;
    
    // Log trade transaction details
    string logMessage = StringFormat("Trade Transaction: Type=%d, Order=%d, Volume=%.2f, Price=%.5f, Result=%d",
                                    trans.type,
                                    trans.order,
                                    trans.volume,
                                    trans.price,
                                    result.retcode);
    
    g_errorHandler.LogInfo(logMessage);
}

//+------------------------------------------------------------------+
//| Generate periodic reports                                        |
//+------------------------------------------------------------------+
void GeneratePeriodicReports()
{
    static datetime lastReportTime = 0;
    datetime currentTime = TimeCurrent();
    
    // Generate daily report at midnight
    if((currentTime - lastReportTime) >= 86400) // 24 hours
    {
        if(g_performanceMonitor != NULL)
        {
            SPlatformPerformance perf = g_performanceMonitor.GetPerformance();
            
            string report = StringFormat("Daily Performance Report\n" +
                                        "Date: %s\n" +
                                        "Net Profit: %.2f\n" +
                                        "Total Trades: %d\n" +
                                        "Win Rate: %.1f%%\n" +
                                        "Max Drawdown: %.2f%%\n" +
                                        "Account Balance: %.2f\n" +
                                        "Account Equity: %.2f",
                                        TimeToString(currentTime),
                                        perf.netProfit,
                                        perf.totalTrades,
                                        perf.winRate,
                                        perf.maxDrawdownPercent,
                                        AccountInfoDouble(ACCOUNT_BALANCE),
                                        AccountInfoDouble(ACCOUNT_EQUITY));
            
            Print(report);
            
            // Send email report if enabled
            if(EnableEmailAlerts && EmailAddress != "")
            {
                SendMail("Solara Daily Report", report);
            }
        }
        
        lastReportTime = currentTime;
    }
}

//+------------------------------------------------------------------+
//| Handle custom chart events                                       |
//+------------------------------------------------------------------+
void HandleCustomChartEvents(const int id,
                            const long &lparam,
                            const double &dparam,
                            const string &sparam)
{
    // Handle custom chart events here
    switch(id)
    {
        case CHARTEVENT_OBJECT_CLICK:
            // Handle object click
            if(StringFind(sparam, "btn_") >= 0)
            {
                HandleButtonClick(sparam);
            }
            break;
    }
}

//+------------------------------------------------------------------+
//| Handle button click                                              |
//+------------------------------------------------------------------+
void HandleButtonClick(const string &sparam)
{
    if(StringFind(sparam, "btn_close_all") >= 0)
    {
        // Close all positions
        if(g_positionManager != NULL)
        {
            g_positionManager.CloseAllPositions();
        }
    }
}

//+------------------------------------------------------------------+
//| Get deinit reason text                                           |
//+------------------------------------------------------------------+
string GetDeinitReasonText(const int reason)
{
    switch(reason)
    {
        case REASON_ACCOUNT:    return "Account changed";
        case REASON_CHARTCHANGE: return "Chart changed";
        case REASON_CHARTCLOSE:  return "Chart closed";
        case REASON_CLOSE:       return "Terminal closed";
        case REASON_INITFAILED:  return "Initialization failed";
        case REASON_PARAMETERS:  return "Input parameters changed";
        case REASON_RECOMPILE:   return "Program recompiled";
        case REASON_REMOVE:      return "Expert removed from chart";
        case REASON_TEMPLATE:    return "Template changed";
        default:                 return "Unknown reason";
    }
}


// Rename to avoid conflict with MarketData.mqh
string TimeframeToStringLocal(ENUM_TIMEFRAMES tf)
{
    switch(tf)
    {
        case PERIOD_M1:  return "M1";
        case PERIOD_M5:  return "M5";
        case PERIOD_M15: return "M15";
        case PERIOD_M30: return "M30";
        case PERIOD_H1:  return "H1";
        case PERIOD_H4:  return "H4";
        case PERIOD_D1:  return "D1";
        case PERIOD_W1:  return "W1";
        case PERIOD_MN1: return "MN1";
        default:         return "Current";
    }
}




//+------------------------------------------------------------------+
//| Print to journal                                                 |
//+------------------------------------------------------------------+
void PrintToJournal(string message)
{
    // Placeholder for journal logging
    static string journalFile = "Solara_Journal_" + TimeToString(TimeCurrent(), TIME_DATE) + ".txt";
    int fileHandle = FileOpen(journalFile, FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI);
    
    if(fileHandle != INVALID_HANDLE)
    {
        FileSeek(fileHandle, 0, SEEK_END);
        FileWrite(fileHandle, GetCurrentTimeString(), message);
        FileClose(fileHandle);
    }
}

//+------------------------------------------------------------------+
//| Get current time as formatted string                             |
//+------------------------------------------------------------------+
string GetCurrentTimeString()
{
    MqlDateTime dt;
    TimeCurrent(dt);
    return StringFormat("%04d-%02d-%02d %02d:%02d:%02d",
                       dt.year, dt.mon, dt.day,
                       dt.hour, dt.min, dt.sec);
}

//+------------------------------------------------------------------+
//| Platform diagnostics                                             |
//+------------------------------------------------------------------+
string GetPlatformDiagnostics()
{
    string diag = "Platform Diagnostics:\n";
    diag += "=======================\n";
    
    // Check component status
    diag += StringFormat("Solara Core: %s\n", g_solaraCore != NULL ? "OK" : "NULL");
    diag += StringFormat("Strategy Manager: %s\n", g_strategyManager != NULL ? "OK" : "NULL");
    diag += StringFormat("Position Manager: %s\n", g_positionManager != NULL ? "OK" : "NULL");
    diag += StringFormat("Risk Manager: %s\n", g_riskManager != NULL ? "OK" : "NULL");
    diag += StringFormat("Performance Monitor: %s\n", g_performanceMonitor != NULL ? "OK" : "NULL");
    diag += StringFormat("Order Executor: %s\n", g_orderExecutor != NULL ? "OK" : "NULL");
    diag += StringFormat("Broker Interface: %s\n", g_brokerInterface != NULL ? "OK" : "NULL");
    diag += StringFormat("Money Manager Factory: %s\n", g_moneyManagerFactory != NULL ? "OK" : "NULL");
    diag += StringFormat("Dashboard: %s\n", g_dashboard != NULL ? "OK" : "NULL");
    diag += StringFormat("Alert System: %s\n", g_alertSystem != NULL ? "OK" : "NULL");
    
    // Check account status
    diag += StringFormat("\nAccount Status:\n");
    diag += StringFormat("Balance: %.2f\n", AccountInfoDouble(ACCOUNT_BALANCE));
    diag += StringFormat("Equity: %.2f\n", AccountInfoDouble(ACCOUNT_EQUITY));
    diag += StringFormat("Free Margin: %.2f\n", AccountInfoDouble(ACCOUNT_MARGIN_FREE));
    diag += StringFormat("Margin Level: %.1f%%\n", AccountInfoDouble(ACCOUNT_MARGIN_LEVEL));
    diag += StringFormat("Leverage: 1:%d\n", AccountInfoInteger(ACCOUNT_LEVERAGE));
    
    return diag;
}

//+------------------------------------------------------------------+
//| Reset platform statistics                                        |
//+------------------------------------------------------------------+
void ResetPlatformStatistics()
{
    if(g_performanceMonitor != NULL)
    {
        g_performanceMonitor.ResetStatistics();
        Print("Platform statistics reset");
    }
    
    if(g_riskManager != NULL)
    {
        g_riskManager.ResetRiskMetrics();
        Print("Risk metrics reset");
    }
    
    SendNotification("Platform statistics have been reset", ALERT_TYPE_INFO);
}

//+------------------------------------------------------------------+
//| Emergency shutdown                                               |
//+------------------------------------------------------------------+
void EmergencyShutdown()
{
    Print("EMERGENCY SHUTDOWN INITIATED");
    
    // Close all positions immediately
    if(g_positionManager != NULL)
    {
        g_positionManager.CloseAllPositionsImmediately();
    }
    
    // Stop all strategies
    if(g_strategyManager != NULL)
    {
        g_strategyManager.StopAllStrategiesImmediately();
    }
    
    // Disable trading
    EnableLiveTrading = false;
    
    // Send emergency alert
    if(g_alertSystem != NULL)
    {
        g_alertSystem.SendAlert("EMERGENCY SHUTDOWN ACTIVATED - All positions closed, trading disabled", ALERT_TYPE_CRITICAL);
    }
    
    Print("EMERGENCY SHUTDOWN COMPLETE");
}

//+------------------------------------------------------------------+
//| Validate platform configuration                                  |
//+------------------------------------------------------------------+
bool ValidatePlatformConfiguration()
{
    bool isValid = true;
    
    // Validate input parameters
    if(MaxDailyLossPercent <= 0 || MaxDailyLossPercent > 100)
    {
        Print("Error: MaxDailyLossPercent must be between 0.01 and 100");
        isValid = false;
    }
    
    if(MaxDrawdownPercent <= 0 || MaxDrawdownPercent > 100)
    {
        Print("Error: MaxDrawdownPercent must be between 0.01 and 100");
        isValid = false;
    }
    
    if(MaxPositionRiskPercent <= 0 || MaxPositionRiskPercent > 10)
    {
        Print("Error: MaxPositionRiskPercent must be between 0.01 and 10");
        isValid = false;
    }
    
    if(RiskPerTradePercent <= 0 || RiskPerTradePercent > 5)
    {
        Print("Error: RiskPerTradePercent must be between 0.01 and 5");
        isValid = false;
    }
    
    if(MaxLotSize <= 0 || MaxLotSize < MinLotSize)
    {
        Print("Error: MaxLotSize must be positive and greater than MinLotSize");
        isValid = false;
    }
    
    if(TradingStartHour < 0 || TradingStartHour > 23)
    {
        Print("Error: TradingStartHour must be 0-23");
        isValid = false;
    }
    
    if(TradingEndHour < 0 || TradingEndHour > 23)
    {
        Print("Error: TradingEndHour must be 0-23");
        isValid = false;
    }
    
    if(TradingStartHour >= TradingEndHour)
    {
        Print("Warning: TradingStartHour should be before TradingEndHour");
    }
    
    // Validate symbol
    string symbol = (TradingSymbol == "") ? _Symbol : TradingSymbol;
    if(!SymbolInfoInteger(symbol, SYMBOL_SELECT))
    {
        Print("Error: Symbol does not exist: ", symbol);
        isValid = false;
    }
    
    // Validate account
    if(AccountInfoDouble(ACCOUNT_BALANCE) <= 0)
    {
        Print("Error: Account balance must be positive");
        isValid = false;
    }
    
    if(AccountInfoDouble(ACCOUNT_MARGIN_FREE) <= 0)
    {
        Print("Warning: Free margin is low");
    }
    
    return isValid;
}

//+------------------------------------------------------------------+
//| Platform maintenance functions                                   |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Clean up old log files                                           |
//+------------------------------------------------------------------+
void CleanupOldLogFiles(int daysToKeep = 7)
{
    // Placeholder for log cleanup
    Print("Log cleanup would run here (keeping ", daysToKeep, " days of logs)");
}

//+------------------------------------------------------------------+
//| Backup configuration                                            |
//+------------------------------------------------------------------+
void BackupConfiguration()
{
    CConfigManager* configManager = CConfigManager::Instance();
    if(configManager == NULL) return;
    
    string backupPath = "Backup\\Solara\\";
    string timestamp = TimeToString(TimeCurrent(), TIME_DATE);
    string backupFile = backupPath + "Config_Backup_" + timestamp + ".json";
    
    if(configManager.BackupToFile(backupFile))
    {
        Print("Configuration backed up to: ", backupFile);
    }
    else
    {
        Print("Failed to backup configuration");
    }
}

//+------------------------------------------------------------------+
//| Restore configuration                                           |
//+------------------------------------------------------------------+
bool RestoreConfiguration(string backupFile)
{
    CConfigManager* configManager = CConfigManager::Instance();
    if(configManager == NULL) return false;
    
    if(configManager.RestoreFromFile(backupFile))
    {
        Print("Configuration restored from: ", backupFile);
        return true;
    }
    
    Print("Failed to restore configuration from: ", backupFile);
    return false;
}

//+------------------------------------------------------------------+
//| Platform information functions                                   |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Get platform version                                             |
//+------------------------------------------------------------------+
string GetPlatformVersion()
{
    return "Solara Platform v1.0";
}

//+------------------------------------------------------------------+
//| Get platform uptime                                              |
//+------------------------------------------------------------------+
string GetPlatformUptime()
{
    if(g_solaraCore == NULL) return "Not initialized";
    
    datetime uptimeSeconds = g_solaraCore.GetUptime();
    int days = (int)(uptimeSeconds / 86400);
    int hours = (int)((uptimeSeconds % 86400) / 3600);
    int minutes = (int)((uptimeSeconds % 3600) / 60);
    int seconds = (int)(uptimeSeconds % 60);
    
    return StringFormat("%d days, %02d:%02d:%02d", days, hours, minutes, seconds);
}

//+------------------------------------------------------------------+
//| Get platform summary                                             |
//+------------------------------------------------------------------+
string GetPlatformSummary()
{
    string summary = GetPlatformVersion() + "\n";
    summary += "Uptime: " + GetPlatformUptime() + "\n";
    summary += "Account: " + AccountInfoString(ACCOUNT_NAME) + "\n";
    summary += "Balance: " + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n";
    summary += "Strategies: ";
    
    if(g_strategyManager != NULL)
    {
        summary += StringFormat("%d active", g_strategyManager.GetActiveStrategyCount());
    }
    else
    {
        summary += "N/A";
    }
    
    summary += "\nStatus: ";
    if(g_solaraCore != NULL)
    {
        summary += GetStateString(g_solaraCore.GetState());
    }
    else
    {
        summary += "Not initialized";
    }
    
    return summary;
}

//+------------------------------------------------------------------+
//| Get state string                                                 |
//+------------------------------------------------------------------+
string GetStateString(ENUM_PLATFORM_STATE state)
{
    switch(state)
    {
        case PLATFORM_STATE_UNINITIALIZED: return "Uninitialized";
        case PLATFORM_STATE_INITIALIZING:  return "Initializing";
        case PLATFORM_STATE_RUNNING:       return "Running";
        case PLATFORM_STATE_PAUSED:        return "Paused";
        case PLATFORM_STATE_STOPPED:       return "Stopped";
        case PLATFORM_STATE_ERROR:         return "Error";
        case PLATFORM_STATE_SHUTDOWN:      return "Shutdown";
        default:                           return "Unknown";
    }
}

//+------------------------------------------------------------------+
//| Test trade execution                                             |
//+------------------------------------------------------------------+
bool TestTradeExecution(string symbol, ENUM_ORDER_TYPE orderType, double volume)
{
    if(g_orderExecutor == NULL) return false;
    
    Print("Testing trade execution...");
    
    // Create test order request
    MqlTradeRequest request;
    ZeroMemory(request);
    
    request.action = TRADE_ACTION_DEAL;
    request.symbol = symbol;
    request.volume = volume;
    request.type = orderType;
    request.price = (orderType == ORDER_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
    request.deviation = MaxSlippagePoints;
    request.magic = MagicNumberBase + 999; // Test magic number
    request.comment = "Test trade";
    request.type_filling = ORDER_FILLING_FOK;
    request.type_time = ORDER_TIME_GTC;
    
    // Execute test order
    MqlTradeResult result;
    bool success = g_orderExecutor.ExecuteOrder(request, result);
    
    if(success)
    {
        Print("Test trade executed successfully: Ticket ", result.order);
        
        // Close test position immediately
        if(result.order > 0)
        {
            MqlTradeRequest closeRequest;
            ZeroMemory(closeRequest);
            
            closeRequest.action = TRADE_ACTION_DEAL;
            closeRequest.symbol = symbol;
            closeRequest.volume = volume;
            closeRequest.type = (orderType == ORDER_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
            closeRequest.position = result.order;
            closeRequest.price = (closeRequest.type == ORDER_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
            closeRequest.deviation = MaxSlippagePoints;
            closeRequest.magic = MagicNumberBase + 999;
            closeRequest.comment = "Close test trade";
            
            MqlTradeResult closeResult;
            g_orderExecutor.ExecuteOrder(closeRequest, closeResult);
            
            if(closeResult.retcode == TRADE_RETCODE_DONE)
            {
                Print("Test trade closed successfully");
            }
            else
            {
                Print("Failed to close test trade: ", closeResult.retcode);
            }
        }
    }
    else
    {
        Print("Test trade failed: ", result.retcode);
    }
    
    return success;
}

//+------------------------------------------------------------------+
//| Symbol exists check                                              |
//+------------------------------------------------------------------+
bool SymbolExists(string symbol)
{
    return SymbolInfoInteger(symbol, SYMBOL_SELECT);
}

//+------------------------------------------------------------------+
//| Format money value                                               |
//+------------------------------------------------------------------+
string FormatMoney(double value)
{
    return DoubleToString(value, 2);
}

//+------------------------------------------------------------------+
//| Format percentage                                                |
//+------------------------------------------------------------------+
string FormatPercent(double value)
{
    return DoubleToString(value, 2) + "%";
}

//+------------------------------------------------------------------+
//| Get symbol information                                           |
//+------------------------------------------------------------------+
string GetSymbolInfoString(string symbol)
{
    if(!SymbolExists(symbol)) return "Symbol not found: " + symbol;
    
    string info = StringFormat("Symbol: %s\n", symbol);
    info += StringFormat("Bid: %.5f\n", SymbolInfoDouble(symbol, SYMBOL_BID));
    info += StringFormat("Ask: %.5f\n", SymbolInfoDouble(symbol, SYMBOL_ASK));
    info += StringFormat("Spread: %.1f points\n", SymbolInfoInteger(symbol, SYMBOL_SPREAD));
    info += StringFormat("Digits: %d\n", (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS));
    info += StringFormat("Lot Size: %.2f\n", SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE));
    info += StringFormat("Min Lot: %.2f\n", SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN));
    info += StringFormat("Max Lot: %.2f\n", SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX));
    info += StringFormat("Tick Size: %.5f\n", SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE));
    info += StringFormat("Tick Value: %.5f\n", SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE));
    
    return info;
}

//+------------------------------------------------------------------+
//| Calculate position size                                          |
//+------------------------------------------------------------------+
double CalculatePositionSize(string symbol, double riskPercent, double stopLossPoints)
{
    if(g_moneyManagerFactory == NULL) return 0.0;
    
    double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
    double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
    
    if(tickValue <= 0 || tickSize <= 0) return 0.0;
    
    // Calculate risk amount
    double riskAmount = accountBalance * riskPercent / 100.0;
    
    // Calculate position size
    double positionSize = riskAmount / (stopLossPoints * tickSize * tickValue);
    
    // Apply lot size constraints
    double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
    double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
    double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
    
    // Round to nearest lot step
    positionSize = MathRound(positionSize / lotStep) * lotStep;
    
    // Apply min/max constraints
    positionSize = MathMax(positionSize, minLot);
    positionSize = MathMin(positionSize, maxLot);
    
    return positionSize;
}

//+------------------------------------------------------------------+
//| Calculate stop loss distance                                     |
//+------------------------------------------------------------------+
double CalculateStopLossDistance(string symbol, ENUM_ORDER_TYPE orderType, double entryPrice, double stopLossPercent)
{
    double currentPrice = 0;
    
    if(orderType == ORDER_TYPE_BUY || orderType == ORDER_TYPE_BUY_LIMIT || orderType == ORDER_TYPE_BUY_STOP)
    {
        currentPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
    }
    else
    {
        currentPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
    }
    
    double priceDistance = MathAbs(entryPrice - currentPrice);
    double stopLossDistance = priceDistance * stopLossPercent / 100.0;
    
    // Convert to points
    double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
    return stopLossDistance / point;
}

//+------------------------------------------------------------------+
//| Calculate take profit distance                                   |
//+------------------------------------------------------------------+
double CalculateTakeProfitDistance(string symbol, ENUM_ORDER_TYPE orderType, double entryPrice, double takeProfitRatio)
{
    // Calculate TP based on risk:reward ratio
    double stopLossDistance = CalculateStopLossDistance(symbol, orderType, entryPrice, 1.0); // 1% SL
    return stopLossDistance * takeProfitRatio;
}

//+------------------------------------------------------------------+
//| Platform control functions                                       |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Enable/disable trading                                           |
//+------------------------------------------------------------------+
void EnableTrading(bool enable)
{
    EnableLiveTrading = enable;
    Print("Live trading ", enable ? "enabled" : "disabled");
    
    // Update all strategies
    if(g_strategyManager != NULL)
    {
        g_strategyManager.EnableTrading(enable);
    }
}

//+------------------------------------------------------------------+
//| Pause/resume all strategies                                      |
//+------------------------------------------------------------------+
void PauseAllStrategies(bool pause)
{
    if(g_strategyManager == NULL) return;
    
    if(pause)
    {
        g_strategyManager.PauseAllStrategies();
        Print("All strategies paused");
    }
    else
    {
        g_strategyManager.ResumeAllStrategies();
        Print("All strategies resumed");
    }
}

//+------------------------------------------------------------------+
//| Close all positions                                              |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
    if(g_positionManager == NULL) return;
    
    int closed = g_positionManager.CloseAllPositions();
    Print("Closed ", closed, " positions");
    
    // Send alert
    if(g_alertSystem != NULL)
    {
        g_alertSystem.SendAlert(StringFormat("Closed %d positions", closed), ALERT_TYPE_INFO);
    }
}

//+------------------------------------------------------------------+
//| End of Solara.mq5                                                |
//+------------------------------------------------------------------+