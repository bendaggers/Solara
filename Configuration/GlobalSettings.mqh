// Configuration/GlobalSettings.mqh
#ifndef GLOBALSETTINGS_MQH
#define GLOBALSETTINGS_MQH

#include "..\Utilities\Logger.mqh"

// Global platform settings structure
struct SGlobalSettings {
    // Platform behavior
    bool enableLogging;
    ENUM_LOG_LEVEL logLevel;
    string logFilePath;
    bool enableEmailAlerts;
    string emailAddress;
    
    // Trading hours
    bool restrictTradingHours;
    int tradingStartHour;     // Server hour (0-23)
    int tradingEndHour;       // Server hour (0-23)
    bool skipWeekends;
    
    // Risk management
    double maxDailyLossPercent;    // Maximum daily loss as % of account
    double maxPositionRiskPercent; // Maximum risk per position (% of account)
    double maxDrawdownPercent;     // Maximum allowed drawdown (% of account)
    double maxLeverage;            // Maximum leverage to use
    bool enableCircuitBreakers;
    
    // Execution settings
    int maxSlippagePoints;         // Maximum allowed slippage in points
    int magicNumberBase;           // Base for magic numbers
    bool enableECNMode;            // Use ECN execution if available
    int maxRetryAttempts;          // Order execution retry attempts
    int retryDelayMs;              // Delay between retries in milliseconds
    
    // Monitoring
    bool enableDashboard;
    int dashboardUpdateInterval;   // In seconds
    bool generateDailyReports;
    string reportEmail;
    
    // Default constructor
    SGlobalSettings() {
        // Platform defaults
        enableLogging = true;
        logLevel = LOG_LEVEL_INFO;
        logFilePath = "Logs\\Solara\\";
        enableEmailAlerts = false;
        emailAddress = "";
        
        // Trading hours defaults
        restrictTradingHours = false;
        tradingStartHour = 0;
        tradingEndHour = 23;
        skipWeekends = true;
        
        // Risk defaults (conservative)
        maxDailyLossPercent = 2.0;
        maxPositionRiskPercent = 1.0;
        maxDrawdownPercent = 10.0;
        maxLeverage = 10.0;
        enableCircuitBreakers = true;
        
        // Execution defaults
        maxSlippagePoints = 10;
        magicNumberBase = 10000;
        enableECNMode = false;
        maxRetryAttempts = 3;
        retryDelayMs = 1000;
        
        // Monitoring defaults
        enableDashboard = true;
        dashboardUpdateInterval = 5;
        generateDailyReports = true;
        reportEmail = "";
    }
    
    // Validation function
    bool Validate() const {
        // Basic validation
        if(maxDailyLossPercent <= 0 || maxDailyLossPercent > 100) {
            Print("Error: maxDailyLossPercent must be between 0.01 and 100");
            return false;
        }
        
        if(maxPositionRiskPercent <= 0 || maxPositionRiskPercent > 10) {
            Print("Error: maxPositionRiskPercent must be between 0.01 and 10");
            return false;
        }
        
        if(maxDrawdownPercent <= 0 || maxDrawdownPercent > 100) {
            Print("Error: maxDrawdownPercent must be between 0.01 and 100");
            return false;
        }
        
        if(maxLeverage <= 0) {
            Print("Error: maxLeverage must be positive");
            return false;
        }
        
        if(tradingStartHour < 0 || tradingStartHour > 23) {
            Print("Error: tradingStartHour must be 0-23");
            return false;
        }
        
        if(tradingEndHour < 0 || tradingEndHour > 23) {
            Print("Error: tradingEndHour must be 0-23");
            return false;
        }
        
        return true;
    }
    
    // Print settings for debugging
    void PrintSettings() const {
        Print("=== Global Settings ===");
        Print("Platform:");
        Print("  Enable Logging: ", enableLogging);
        Print("  Log Level: ", EnumToString(logLevel));
        Print("  Log Path: ", logFilePath);
        
        Print("\nTrading Hours:");
        Print("  Restrict Hours: ", restrictTradingHours);
        Print("  Start Hour: ", tradingStartHour);
        Print("  End Hour: ", tradingEndHour);
        Print("  Skip Weekends: ", skipWeekends);
        
        Print("\nRisk Management:");
        Print("  Max Daily Loss: ", maxDailyLossPercent, "%");
        Print("  Max Position Risk: ", maxPositionRiskPercent, "%");
        Print("  Max Drawdown: ", maxDrawdownPercent, "%");
        Print("  Max Leverage: 1:", maxLeverage);
        Print("  Circuit Breakers: ", enableCircuitBreakers);
        
        Print("\nExecution:");
        Print("  Max Slippage: ", maxSlippagePoints, " points");
        Print("  Magic Base: ", magicNumberBase);
        Print("  ECN Mode: ", enableECNMode);
        Print("  Max Retries: ", maxRetryAttempts);
        Print("  Retry Delay: ", retryDelayMs, "ms");
        
        Print("\nMonitoring:");
        Print("  Dashboard: ", enableDashboard);
        Print("  Update Interval: ", dashboardUpdateInterval, "s");
        Print("  Daily Reports: ", generateDailyReports);
        Print("=======================");
    }
};

#endif