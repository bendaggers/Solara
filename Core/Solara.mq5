//+------------------------------------------------------------------+
//|                                                      Solara.mq5  |
//|                                                Solara Platform   |
//|                                       https://www.solara-trading.com |
//+------------------------------------------------------------------+
#property copyright "Solara Trading Platform"
#property link      "https://www.solara-trading.com"
#property version   "1.00"
#property description "Enterprise-grade multi-strategy trading platform"
#property description "Supports multiple independent trading strategies"
#property description "with comprehensive risk management and monitoring"

//--- Includes
#include <Trade/Trade.mqh>
#include "..\Core\SolaraCore.mqh"
#include "..\Configuration\ConfigManager.mqh"
#include "..\Data\MarketData.mqh"
#include "..\Execution\OrderExecutor.mqh"
#include "..\MoneyManagement\MoneyManagerFactory.mqh"
#include "..\Monitoring\Dashboard.mqh"
#include "..\Monitoring\AlertSystem.mqh"
#include "..\Monitoring\ReportGenerator.mqh"
#include "..\Utilities\Logger.mqh"
#include "..\Utilities\ErrorHandler.mqh"

//--- Input parameters
input string   CONFIG_SECTION      = "===== CONFIGURATION ====="; // Configuration Section
input string   ConfigFile          = "SolaraConfig.ini";          // Configuration file name
input bool     EnableLogging       = true;                        // Enable system logging
input int      LogLevel            = 2;                           // Log level (0=Error,1=Warn,2=Info,3=Debug)

input string   TRADING_SECTION     = "===== TRADING SETTINGS ====="; // Trading Settings
input bool     EnableTrading       = true;                        // Enable actual trading
input bool     EnableDemoMode      = true;                        // Demo mode (no real trades)
input int      MaxOpenPositions    = 5;                           // Maximum open positions
input double   MaxDailyLossPercent = 5.0;                         // Maximum daily loss (%)

input string   RISK_SECTION        = "===== RISK MANAGEMENT ====="; // Risk Management
input bool     EnableRiskManager   = true;                        // Enable risk management
input double   MaxPositionSizePercent = 2.0;                      // Max position size (% of account)
input double   MaxDrawdownPercent  = 10.0;                        // Maximum drawdown (%)

input string   MONITORING_SECTION  = "===== MONITORING =====";    // Monitoring Settings
input bool     EnableDashboard     = true;                        // Enable dashboard
input bool     EnableAlerts        = true;                        // Enable alert system
input bool     EnableReports       = true;                        // Enable reporting

//--- Global object pointers
CSolaraCore*      g_solaraCore      = NULL;
CConfigManager*   g_configManager   = NULL;
CLogger*          g_logger          = NULL;
CErrorHandler*    g_errorHandler    = NULL;
CDashboard*       g_dashboard       = NULL;
CAlertSystem*     g_alertSystem     = NULL;
CReportGenerator* g_reportGenerator = NULL;

//--- Global variables
bool              g_initialized     = false;
datetime          g_lastTickTime    = 0;
int               g_tickCount       = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit() {
    // Initialize random seed
    MathSrand((int)TimeCurrent());
    
    // Create and initialize logger first
    g_logger = new CLogger();
    if(CheckPointer(g_logger) == POINTER_INVALID) {
        Print("ERROR: Failed to create logger");
        return INIT_FAILED;
    }
    
    // Call the correct Initialize method
    if(!g_logger.Initialize(EnableLogging, LogLevel)) {
        Print("ERROR: Failed to initialize logger");
        delete g_logger;
        g_logger = NULL;
        return INIT_FAILED;
    }
    
    g_logger.Info("=== Solara Platform Initialization ===", "Solara");
    g_logger.Info("Version: 1.0", "Solara");
    g_logger.Info("Build Date: " + __DATE__ + " " + __TIME__, "Solara");
    
    // Create error handler
    g_errorHandler = new CErrorHandler();
    if(CheckPointer(g_errorHandler) == POINTER_INVALID) {
        g_logger.Error("Failed to create ErrorHandler", "Solara");
        delete g_logger;
        g_logger = NULL;
        return INIT_FAILED;
    }
    
    // Call the correct Initialize method for ErrorHandler
    if(!g_errorHandler.Initialize(g_logger)) {
        g_logger.Error("Failed to initialize ErrorHandler", "Solara");
        delete g_errorHandler;
        g_errorHandler = NULL;
        delete g_logger;
        g_logger = NULL;
        return INIT_FAILED;
    }
    
    // Load configuration
    if(!InitializeConfiguration()) {
        g_logger.Error("Failed to initialize configuration", "Solara");
        return INIT_FAILED;
    }
    
    // Initialize core platform components
    if(!InitializeCorePlatform()) {
        g_logger.Error("Failed to initialize core platform", "Solara");
        return INIT_FAILED;
    }
    
    // Initialize monitoring systems
    if(!InitializeMonitoring()) {
        g_logger.Warn("Some monitoring components failed to initialize", "Solara");
        // Continue anyway - monitoring is not critical
    }
    
    // Final initialization
    g_initialized = true;
    
    // Print platform status
    PrintPlatformStatus();
    
    g_logger.Info("=== Solara Platform Initialized Successfully ===", "Solara");
    g_logger.Info("Trading Enabled: " + (EnableTrading ? "Yes" : "No"), "Solara");
    g_logger.Info("Demo Mode: " + (EnableDemoMode ? "Yes" : "No"), "Solara");
    g_logger.Info("Dashboard: " + (EnableDashboard ? "Enabled" : "Disabled"), "Solara");
    
    // Set up timer for periodic updates (every 1 second)
    EventSetTimer(1);
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
    // Kill timer
    EventKillTimer();
    
    if(g_logger != NULL) {
        g_logger.Info("=== Solara Platform Shutdown ===", "Solara");
        g_logger.Info("Deinit reason: " + GetDeinitReasonString(reason), "Solara");
    }
    
    // Deinitialize in reverse order
    DeinitializeMonitoring();
    DeinitializeCorePlatform();
    DeinitializeConfiguration();
    
    // Cleanup global objects
    if(CheckPointer(g_reportGenerator) == POINTER_DYNAMIC) {
        delete g_reportGenerator;
    }
    g_reportGenerator = NULL;
    
    if(CheckPointer(g_alertSystem) == POINTER_DYNAMIC) {
        delete g_alertSystem;
    }
    g_alertSystem = NULL;
    
    if(CheckPointer(g_dashboard) == POINTER_DYNAMIC) {
        delete g_dashboard;
    }
    g_dashboard = NULL;
    
    if(CheckPointer(g_solaraCore) == POINTER_DYNAMIC) {
        delete g_solaraCore;
    }
    g_solaraCore = NULL;
    
    if(CheckPointer(g_configManager) == POINTER_DYNAMIC) {
        delete g_configManager;
    }
    g_configManager = NULL;
    
    if(CheckPointer(g_errorHandler) == POINTER_DYNAMIC) {
        g_errorHandler.Deinitialize();
        delete g_errorHandler;
    }
    g_errorHandler = NULL;
    
    if(CheckPointer(g_logger) == POINTER_DYNAMIC) {
        g_logger.Info("=== Solara Platform Shutdown Complete ===", "Solara");
        delete g_logger;
    }
    g_logger = NULL;
    
    g_initialized = false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick() {
    // Check if platform is initialized
    if(!g_initialized) {
        return;
    }
    
    if(CheckPointer(g_solaraCore) == POINTER_INVALID) {
        return;
    }
    
    // Update tick counter
    g_tickCount++;
    datetime currentTime = TimeCurrent();
    
    // Process tick through core engine
    g_solaraCore.OnTick();
    
    // Update dashboard if enabled
    if(EnableDashboard && CheckPointer(g_dashboard) == POINTER_DYNAMIC) {
        g_dashboard.Update();
    }
    
    // Check for auto-reports (every hour)
    if(EnableReports && CheckPointer(g_reportGenerator) == POINTER_DYNAMIC) {
        static datetime lastReportCheck = 0;
        if(currentTime - lastReportCheck >= 3600) {
            g_reportGenerator.CheckAutoReports();
            lastReportCheck = currentTime;
        }
    }
    
    // Log tick count periodically (every 1000 ticks)
    if(g_tickCount % 1000 == 0 && CheckPointer(g_logger) == POINTER_DYNAMIC) {
        g_logger.Debug("Tick count: " + IntegerToString(g_tickCount), "Solara");
    }
    
    g_lastTickTime = currentTime;
}

//+------------------------------------------------------------------+
//| Trade transaction handler                                        |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result) {
    if(!g_initialized) {
        return;
    }
    
    if(CheckPointer(g_solaraCore) == POINTER_INVALID) {
        return;
    }
    
    // Pass trade transaction to core engine
    g_solaraCore.OnTradeTransaction(trans, request, result);
    
    // Log trade transaction
    if(CheckPointer(g_logger) == POINTER_DYNAMIC) {
        string transactionType = GetTransactionTypeString(trans.type);
        g_logger.Info("Trade Transaction: " + transactionType + 
                     ", Order: " + IntegerToString(trans.order) +
                     ", Symbol: " + trans.symbol, "Solara");
    }
    
    // Send alert for important transactions
    if(EnableAlerts && CheckPointer(g_alertSystem) == POINTER_DYNAMIC) {
        if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
            g_alertSystem.SendInfo("New deal executed: " + trans.symbol, "TradeSystem");
        } else if(trans.type == TRADE_TRANSACTION_ORDER_ADD) {
            g_alertSystem.SendInfo("New order placed: " + trans.symbol, "TradeSystem");
        }
    }
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer() {
    if(!g_initialized) {
        return;
    }
    
    // Process timer events in core engine
    if(CheckPointer(g_solaraCore) == POINTER_DYNAMIC) {
        g_solaraCore.OnTimer();
    }
    
    // Update dashboard
    if(EnableDashboard && CheckPointer(g_dashboard) == POINTER_DYNAMIC) {
        g_dashboard.Update();
    }
    
    // Check for alerts
    if(EnableAlerts && CheckPointer(g_alertSystem) == POINTER_DYNAMIC) {
        // Could evaluate alert conditions here
    }
}

//+------------------------------------------------------------------+
//| Chart event handler                                              |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long &lparam,
                  const double &dparam,
                  const string &sparam) {
    if(!g_initialized) {
        return;
    }
    
    // Pass chart events to dashboard
    if(EnableDashboard && CheckPointer(g_dashboard) == POINTER_DYNAMIC) {
        g_dashboard.OnChartEvent(id, lparam, dparam, sparam);
    }
    
    // Handle specific chart events
    switch(id) {
        case CHARTEVENT_KEYDOWN:
            HandleKeyPress((int)lparam);
            break;
        case CHARTEVENT_CLICK:
            HandleMouseClick((int)lparam, (int)dparam, sparam);
            break;
    }
}

//+------------------------------------------------------------------+
//| Initialize configuration                                         |
//+------------------------------------------------------------------+
bool InitializeConfiguration() {
    if(CheckPointer(g_logger) == POINTER_INVALID) {
        Print("ERROR: Logger not initialized for configuration");
        return false;
    }
    
    g_logger.Info("Initializing configuration system...", "Solara");
    
    // Create ConfigManager instance
    g_configManager = new CConfigManager();
    if(CheckPointer(g_configManager) == POINTER_INVALID) {
        g_logger.Error("Failed to create ConfigManager", "Solara");
        return false;
    }
    
    // Initialize with logger
    if(!g_configManager.Initialize(g_logger)) {
        g_logger.Error("Failed to initialize ConfigManager", "Solara");
        delete g_configManager;
        g_configManager = NULL;
        return false;
    }
    
    // Load configuration file
    if(!g_configManager.LoadConfig(ConfigFile)) {
        g_logger.Warn("Configuration file not found or could not be loaded: " + ConfigFile, "Solara");
        g_logger.Info("Using default configuration", "Solara");
    } else {
        g_logger.Info("Configuration loaded from: " + ConfigFile, "Solara");
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Initialize core platform                                         |
//+------------------------------------------------------------------+
bool InitializeCorePlatform() {
    if(CheckPointer(g_logger) == POINTER_INVALID) {
        Print("ERROR: Logger not initialized for core platform");
        return false;
    }
    
    g_logger.Info("Initializing core platform...", "Solara");
    
    // Create and initialize SolaraCore
    g_solaraCore = new CSolaraCore();
    if(CheckPointer(g_solaraCore) == POINTER_INVALID) {
        g_logger.Error("Failed to create SolaraCore", "Solara");
        return false;
    }
    
    // Initialize with dependencies
    if(!g_solaraCore.Initialize(g_configManager, g_logger, g_errorHandler)) {
        g_logger.Error("Failed to initialize SolaraCore", "Solara");
        delete g_solaraCore;
        g_solaraCore = NULL;
        return false;
    }
    
    // Configure trading settings
    g_solaraCore.SetTradingEnabled(EnableTrading);
    g_solaraCore.SetDemoMode(EnableDemoMode);
    g_solaraCore.SetMaxOpenPositions(MaxOpenPositions);
    
    g_logger.Info("Core platform initialized successfully", "Solara");
    return true;
}

//+------------------------------------------------------------------+
//| Initialize monitoring systems                                    |
//+------------------------------------------------------------------+
bool InitializeMonitoring() {
    if(CheckPointer(g_logger) == POINTER_INVALID) {
        Print("ERROR: Logger not initialized for monitoring");
        return false;
    }
    
    g_logger.Info("Initializing monitoring systems...", "Solara");
    
    bool allSuccessful = true;
    
    // Initialize Alert System
    if(EnableAlerts) {
        g_logger.Info("Initializing alert system...", "Solara");
        g_alertSystem = new CAlertSystem();
        if(CheckPointer(g_alertSystem) != POINTER_INVALID) {
            if(!g_alertSystem.Initialize(g_logger)) {
                g_logger.Warn("Failed to initialize Alert System", "Solara");
                delete g_alertSystem;
                g_alertSystem = NULL;
                allSuccessful = false;
            } else {
                g_logger.Info("Alert system initialized", "Solara");
            }
        } else {
            g_logger.Warn("Failed to create Alert System", "Solara");
            allSuccessful = false;
        }
    }
    
    // Initialize Report Generator
    if(EnableReports) {
        g_logger.Info("Initializing report generator...", "Solara");
        g_reportGenerator = new CReportGenerator();
        if(CheckPointer(g_reportGenerator) != POINTER_INVALID) {
            if(!g_reportGenerator.Initialize(g_logger)) {
                g_logger.Warn("Failed to initialize Report Generator", "Solara");
                delete g_reportGenerator;
                g_reportGenerator = NULL;
                allSuccessful = false;
            } else {
                g_logger.Info("Report generator initialized", "Solara");
            }
        } else {
            g_logger.Warn("Failed to create Report Generator", "Solara");
            allSuccessful = false;
        }
    }
    
    // Initialize Dashboard
    if(EnableDashboard) {
        g_logger.Info("Initializing dashboard...", "Solara");
        g_dashboard = new CDashboard();
        if(CheckPointer(g_dashboard) != POINTER_INVALID) {
            if(!g_dashboard.Initialize(g_logger)) {
                g_logger.Warn("Failed to initialize Dashboard", "Solara");
                delete g_dashboard;
                g_dashboard = NULL;
                allSuccessful = false;
            } else {
                g_logger.Info("Dashboard initialized", "Solara");
                g_dashboard.Show();
            }
        } else {
            g_logger.Warn("Failed to create Dashboard", "Solara");
            allSuccessful = false;
        }
    }
    
    return allSuccessful;
}

//+------------------------------------------------------------------+
//| Deinitialize configuration                                       |
//+------------------------------------------------------------------+
void DeinitializeConfiguration() {
    if(CheckPointer(g_configManager) == POINTER_DYNAMIC) {
        g_configManager.Deinitialize();
    }
}

//+------------------------------------------------------------------+
//| Deinitialize core platform                                       |
//+------------------------------------------------------------------+
void DeinitializeCorePlatform() {
    if(CheckPointer(g_solaraCore) == POINTER_DYNAMIC) {
        g_solaraCore.Deinitialize();
    }
}

//+------------------------------------------------------------------+
//| Deinitialize monitoring                                          |
//+------------------------------------------------------------------+
void DeinitializeMonitoring() {
    if(CheckPointer(g_dashboard) == POINTER_DYNAMIC) {
        g_dashboard.Deinitialize();
    }
    
    if(CheckPointer(g_alertSystem) == POINTER_DYNAMIC) {
        // Alert system cleanup if needed
    }
    
    if(CheckPointer(g_reportGenerator) == POINTER_DYNAMIC) {
        g_reportGenerator.Deinitialize();
    }
}

//+------------------------------------------------------------------+
//| Print platform status                                            |
//+------------------------------------------------------------------+
void PrintPlatformStatus() {
    string status = "\n" +
                   "=== SOLARA PLATFORM STATUS ===\n" +
                   "Account: " + AccountInfoString(ACCOUNT_COMPANY) + " (" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ")\n" +
                   "Balance: $" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n" +
                   "Currency: " + AccountInfoString(ACCOUNT_CURRENCY) + "\n" +
                   "Leverage: 1:" + IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE)) + "\n" +
                   "Server: " + AccountInfoString(ACCOUNT_SERVER) + "\n" +
                   "Terminal: " + TerminalInfoString(TERMINAL_INFO_NAME) + " v" + TerminalInfoString(TERMINAL_INFO_VERSION) + "\n" +
                   "Build: " + IntegerToString(TerminalInfoInteger(TERMINAL_BUILD)) + "\n" +
                   "=================================\n";
    
    Print(status);
    if(CheckPointer(g_logger) == POINTER_DYNAMIC) {
        g_logger.Info(status, "Solara");
    }
}

//+------------------------------------------------------------------+
//| Handle key press events                                          |
//+------------------------------------------------------------------+
void HandleKeyPress(int keyCode) {
    // Handle keyboard shortcuts
    switch(keyCode) {
        case 49: // '1' - Show dashboard
            if(CheckPointer(g_dashboard) == POINTER_DYNAMIC) {
                g_dashboard.Show();
                if(CheckPointer(g_logger) == POINTER_DYNAMIC) {
                    g_logger.Info("Dashboard shown (key shortcut)", "Solara");
                }
            }
            break;
            
        case 50: // '2' - Hide dashboard
            if(CheckPointer(g_dashboard) == POINTER_DYNAMIC) {
                g_dashboard.Hide();
                if(CheckPointer(g_logger) == POINTER_DYNAMIC) {
                    g_logger.Info("Dashboard hidden (key shortcut)", "Solara");
                }
            }
            break;
            
        case 51: // '3' - Generate report
            if(CheckPointer(g_reportGenerator) == POINTER_DYNAMIC) {
                g_reportGenerator.GenerateAllReports(TimeCurrent() - 86400, TimeCurrent(), "Manual_");
                if(CheckPointer(g_logger) == POINTER_DYNAMIC) {
                    g_logger.Info("Manual report generated (key shortcut)", "Solara");
                }
            }
            break;
            
        case 27: // ESC - Emergency stop
            if(CheckPointer(g_solaraCore) == POINTER_DYNAMIC) {
                g_solaraCore.EmergencyStop();
                if(CheckPointer(g_logger) == POINTER_DYNAMIC) {
                    g_logger.Warn("EMERGENCY STOP ACTIVATED (ESC key)", "Solara");
                }
                if(CheckPointer(g_alertSystem) == POINTER_DYNAMIC) {
                    g_alertSystem.SendCritical("EMERGENCY STOP ACTIVATED", "Solara");
                }
            }
            break;
    }
}

//+------------------------------------------------------------------+
//| Handle mouse click events                                        |
//+------------------------------------------------------------------+
void HandleMouseClick(int x, int y, string sparam) {
    // Could handle mouse clicks for dashboard interaction
    // This would be expanded based on dashboard GUI needs
    if(CheckPointer(g_dashboard) == POINTER_DYNAMIC) {
        // Dashboard handles its own mouse events
    }
}

//+------------------------------------------------------------------+
//| Get deinit reason string                                         |
//+------------------------------------------------------------------+
string GetDeinitReasonString(int reason) {
    switch(reason) {
        case REASON_ACCOUNT:    return "Account changed";
        case REASON_CHARTCHANGE:return "Chart changed";
        case REASON_CHARTCLOSE: return "Chart closed";
        case REASON_CLOSE:      return "Terminal closed";
        case REASON_INITFAILED: return "Initialization failed";
        case REASON_PARAMETERS: return "Parameters changed";
        case REASON_RECOMPILE:  return "Program recompiled";
        case REASON_REMOVE:     return "Program removed";
        case REASON_TEMPLATE:   return "Template changed";
        default:                return "Unknown reason";
    }
}

//+------------------------------------------------------------------+
//| Get transaction type string                                      |
//+------------------------------------------------------------------+
string GetTransactionTypeString(ENUM_TRADE_TRANSACTION_TYPE type) {
    switch(type) {
        case TRADE_TRANSACTION_ORDER_ADD:        return "Order Added";
        case TRADE_TRANSACTION_ORDER_UPDATE:     return "Order Updated";
        case TRADE_TRANSACTION_ORDER_DELETE:     return "Order Deleted";
        case TRADE_TRANSACTION_DEAL_ADD:         return "Deal Added";
        case TRADE_TRANSACTION_DEAL_UPDATE:      return "Deal Updated";
        case TRADE_TRANSACTION_DEAL_DELETE:      return "Deal Deleted";
        case TRADE_TRANSACTION_HISTORY_ADD:      return "History Added";
        case TRADE_TRANSACTION_HISTORY_UPDATE:   return "History Updated";
        case TRADE_TRANSACTION_HISTORY_DELETE:   return "History Deleted";
        case TRADE_TRANSACTION_POSITION:         return "Position";
        case TRADE_TRANSACTION_REQUEST:          return "Request";
        default:                                 return "Unknown";
    }
}

//+------------------------------------------------------------------+
//| Get error description                                            |
//+------------------------------------------------------------------+
string GetErrorDescription(int errorCode) {
    switch(errorCode) {
        case 0:   return "No error";
        case 1:   return "No error returned";
        case 2:   return "Common error";
        case 3:   return "Invalid trade parameters";
        case 4:   return "Trade server busy";
        case 5:   return "Old version of client terminal";
        case 6:   return "No connection with trade server";
        case 7:   return "Not enough rights";
        case 8:   return "Too frequent requests";
        case 9:   return "Malfunctional trade operation";
        case 64:  return "Account disabled";
        case 65:  return "Invalid account";
        case 128: return "Trade timeout";
        case 129: return "Invalid price";
        case 130: return "Invalid stops";
        case 131: return "Invalid trade volume";
        case 132: return "Market closed";
        case 133: return "Trade disabled";
        case 134: return "Not enough money";
        case 135: return "Price changed";
        case 136: return "Off quotes";
        case 137: return "Broker busy";
        case 138: return "Requote";
        case 139: return "Order is locked";
        case 140: return "Long positions only allowed";
        case 141: return "Too many requests";
        case 145: return "Modification denied because order is too close to market";
        case 146: return "Trade context is busy";
        case 147: return "Expirations are denied by broker";
        case 148: return "Amount of open and pending orders has reached the limit";
        case 149: return "Hedging is prohibited";
        case 150: return "Prohibited by FIFO rules";
        default:  return "Unknown error " + IntegerToString(errorCode);
    }
}
//+------------------------------------------------------------------+