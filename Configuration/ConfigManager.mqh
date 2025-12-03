// Configuration/ConfigManager.mqh
#ifndef CONFIGMANAGER_MQH
#define CONFIGMANAGER_MQH

#include "GlobalSettings.mqh"
#include "StrategyConfig.mqh"

// Forward declaration
class CConfigManager;

// Singleton instance
CConfigManager* g_configManager = NULL;

// Configuration file manager
class CConfigManager {
private:
    SGlobalSettings m_globalSettings;
    CStrategyConfigManager m_strategyConfigs;
    string m_configPath;
    bool m_initialized;
    
    // Helper function to trim strings (MQL5 doesn't have StringTrim)
    string TrimString(string text) {
        // Remove leading and trailing spaces
        int start = 0;
        int end = StringLen(text) - 1;
        
        // Find first non-space character
        while(start <= end && StringGetCharacter(text, start) == ' ') {
            start++;
        }
        
        // Find last non-space character
        while(end >= start && StringGetCharacter(text, end) == ' ') {
            end--;
        }
        
        if(start > end) {
            return ""; // All spaces
        }
        
        return StringSubstr(text, start, end - start + 1);
    }
    
    // Singleton pattern - private constructor
    CConfigManager() {
        m_configPath = "Solara\\Config\\";
        m_initialized = false;
    }
    
public:
    // Singleton access
    static CConfigManager* Instance() {
        if(g_configManager == NULL) {
            g_configManager = new CConfigManager();
        }
        return g_configManager;
    }
    
    // Initialize
    bool Initialize() {
        if(m_initialized) {
            return true;
        }
        
        // Create config directory if it doesn't exist
        if(!CreateDirectory(m_configPath)) {
            Print("Warning: Could not create config directory: ", m_configPath);
        }
        
        // Load configurations
        if(!LoadGlobalSettings()) {
            Print("Warning: Could not load global settings");
        }
        
        if(!LoadStrategyConfigs()) {
            Print("Warning: Could not load strategy configs");
        }
        
        m_initialized = true;
        Print("ConfigManager initialized");
        return true;
    }
    
    // Deinitialize
    void Deinitialize() {
        // Save configurations on exit
        if(m_initialized) {
            SaveGlobalSettings();
            SaveStrategyConfigs();
        }
        
        m_initialized = false;
        Print("ConfigManager deinitialized");
    }
    
    // Getters
    SGlobalSettings GetGlobalSettings() {
        return m_globalSettings;
    }
    
    void SetGlobalSettings(const SGlobalSettings &settings) {
        m_globalSettings = settings;
    }
    
    CStrategyConfigManager* GetStrategyConfigs() {
        return &m_strategyConfigs;
    }
    
    bool IsInitialized() const {
        return m_initialized;
    }
    
    // Set config path
    void SetConfigPath(string path) {
        m_configPath = path;
        if(StringSubstr(m_configPath, StringLen(m_configPath) - 1) != "\\") {
            m_configPath += "\\";
        }
    }
    
    // Load global settings from file
    bool LoadGlobalSettings() {
        string filename = m_configPath + "GlobalSettings.ini";
        
        // Check if file exists
        int fileHandle = FileOpen(filename, FILE_READ|FILE_TXT);
        if(fileHandle == INVALID_HANDLE) {
            Print("Global settings file not found, using defaults: ", filename);
            SaveGlobalSettings(); // Create default file
            return true;
        }
        
        // Read the file line by line
        while(!FileIsEnding(fileHandle)) {
            string line = FileReadString(fileHandle);
            line = TrimString(line); // Fixed: Using custom TrimString function
            
            // Skip empty lines and comments
            if(StringLen(line) == 0 || StringGetCharacter(line, 0) == '#') {
                continue;
            }
            
            // Find key=value separator
            int separatorPos = StringFind(line, "=");
            if(separatorPos > 0) {
                string key = StringSubstr(line, 0, separatorPos);
                string value = StringSubstr(line, separatorPos + 1);
                
                // Parse settings based on key
                if(key == "enableLogging") m_globalSettings.enableLogging = (StringToInteger(value) != 0);
                else if(key == "logLevel") m_globalSettings.logLevel = (ENUM_LOG_LEVEL)StringToInteger(value);
                else if(key == "logFilePath") m_globalSettings.logFilePath = value;
                else if(key == "enableEmailAlerts") m_globalSettings.enableEmailAlerts = (StringToInteger(value) != 0);
                else if(key == "emailAddress") m_globalSettings.emailAddress = value;
                else if(key == "restrictTradingHours") m_globalSettings.restrictTradingHours = (StringToInteger(value) != 0);
                else if(key == "tradingStartHour") m_globalSettings.tradingStartHour = (int)StringToInteger(value);
                else if(key == "tradingEndHour") m_globalSettings.tradingEndHour = (int)StringToInteger(value);
                else if(key == "skipWeekends") m_globalSettings.skipWeekends = (StringToInteger(value) != 0);
                else if(key == "maxDailyLossPercent") m_globalSettings.maxDailyLossPercent = StringToDouble(value);
                else if(key == "maxPositionRiskPercent") m_globalSettings.maxPositionRiskPercent = StringToDouble(value);
                else if(key == "maxDrawdownPercent") m_globalSettings.maxDrawdownPercent = StringToDouble(value);
                else if(key == "maxLeverage") m_globalSettings.maxLeverage = StringToDouble(value);
                else if(key == "enableCircuitBreakers") m_globalSettings.enableCircuitBreakers = (StringToInteger(value) != 0);
                else if(key == "maxSlippagePoints") m_globalSettings.maxSlippagePoints = (int)StringToInteger(value);
                else if(key == "magicNumberBase") m_globalSettings.magicNumberBase = (int)StringToInteger(value);
                else if(key == "enableECNMode") m_globalSettings.enableECNMode = (StringToInteger(value) != 0);
                else if(key == "maxRetryAttempts") m_globalSettings.maxRetryAttempts = (int)StringToInteger(value);
                else if(key == "retryDelayMs") m_globalSettings.retryDelayMs = (int)StringToInteger(value);
                else if(key == "enableDashboard") m_globalSettings.enableDashboard = (StringToInteger(value) != 0);
                else if(key == "dashboardUpdateInterval") m_globalSettings.dashboardUpdateInterval = (int)StringToInteger(value);
                else if(key == "generateDailyReports") m_globalSettings.generateDailyReports = (StringToInteger(value) != 0);
                else if(key == "reportEmail") m_globalSettings.reportEmail = value;
            }
        }
        
        FileClose(fileHandle);
        
        if(!m_globalSettings.Validate()) {
            Print("Loaded global settings failed validation");
            return false;
        }
        
        Print("Global settings loaded from: ", filename);
        return true;
    }
    
    // Save global settings to file
    bool SaveGlobalSettings() {
        string filename = m_configPath + "GlobalSettings.ini";
        
        int fileHandle = FileOpen(filename, FILE_WRITE|FILE_TXT);
        if(fileHandle == INVALID_HANDLE) {
            Print("Failed to create global settings file: ", filename);
            return false;
        }
        
        // Write header
        FileWrite(fileHandle, "# Solara Global Settings");
        FileWrite(fileHandle, "# Generated on: ", TimeToString(TimeCurrent()));
        FileWrite(fileHandle, "");
        
        // Platform settings
        FileWrite(fileHandle, "[Platform]");
        FileWrite(fileHandle, "enableLogging=", IntegerToString(m_globalSettings.enableLogging));
        FileWrite(fileHandle, "logLevel=", IntegerToString(m_globalSettings.logLevel));
        FileWrite(fileHandle, "logFilePath=", m_globalSettings.logFilePath);
        FileWrite(fileHandle, "enableEmailAlerts=", IntegerToString(m_globalSettings.enableEmailAlerts));
        FileWrite(fileHandle, "emailAddress=", m_globalSettings.emailAddress);
        FileWrite(fileHandle, "");
        
        // Trading hours
        FileWrite(fileHandle, "[TradingHours]");
        FileWrite(fileHandle, "restrictTradingHours=", IntegerToString(m_globalSettings.restrictTradingHours));
        FileWrite(fileHandle, "tradingStartHour=", IntegerToString(m_globalSettings.tradingStartHour));
        FileWrite(fileHandle, "tradingEndHour=", IntegerToString(m_globalSettings.tradingEndHour));
        FileWrite(fileHandle, "skipWeekends=", IntegerToString(m_globalSettings.skipWeekends));
        FileWrite(fileHandle, "");
        
        // Risk management
        FileWrite(fileHandle, "[RiskManagement]");
        FileWrite(fileHandle, "maxDailyLossPercent=", DoubleToString(m_globalSettings.maxDailyLossPercent, 2));
        FileWrite(fileHandle, "maxPositionRiskPercent=", DoubleToString(m_globalSettings.maxPositionRiskPercent, 2));
        FileWrite(fileHandle, "maxDrawdownPercent=", DoubleToString(m_globalSettings.maxDrawdownPercent, 2));
        FileWrite(fileHandle, "maxLeverage=", DoubleToString(m_globalSettings.maxLeverage, 1));
        FileWrite(fileHandle, "enableCircuitBreakers=", IntegerToString(m_globalSettings.enableCircuitBreakers));
        FileWrite(fileHandle, "");
        
        // Execution
        FileWrite(fileHandle, "[Execution]");
        FileWrite(fileHandle, "maxSlippagePoints=", IntegerToString(m_globalSettings.maxSlippagePoints));
        FileWrite(fileHandle, "magicNumberBase=", IntegerToString(m_globalSettings.magicNumberBase));
        FileWrite(fileHandle, "enableECNMode=", IntegerToString(m_globalSettings.enableECNMode));
        FileWrite(fileHandle, "maxRetryAttempts=", IntegerToString(m_globalSettings.maxRetryAttempts));
        FileWrite(fileHandle, "retryDelayMs=", IntegerToString(m_globalSettings.retryDelayMs));
        FileWrite(fileHandle, "");
        
        // Monitoring
        FileWrite(fileHandle, "[Monitoring]");
        FileWrite(fileHandle, "enableDashboard=", IntegerToString(m_globalSettings.enableDashboard));
        FileWrite(fileHandle, "dashboardUpdateInterval=", IntegerToString(m_globalSettings.dashboardUpdateInterval));
        FileWrite(fileHandle, "generateDailyReports=", IntegerToString(m_globalSettings.generateDailyReports));
        FileWrite(fileHandle, "reportEmail=", m_globalSettings.reportEmail);
        
        FileClose(fileHandle);
        Print("Global settings saved to: ", filename);
        return true;
    }
    
    // Load strategy configurations
    bool LoadStrategyConfigs() {
        string filename = m_configPath + "Strategies.ini";
        
        // Check if file exists
        int fileHandle = FileOpen(filename, FILE_READ|FILE_TXT);
        if(fileHandle == INVALID_HANDLE) {
            Print("Strategy configs file not found: ", filename);
            return true; // It's okay if the file doesn't exist yet
        }
        
        SStrategyConfig currentConfig;
        bool inStrategyBlock = false;
        
        // Read the file line by line
        while(!FileIsEnding(fileHandle)) {
            string line = FileReadString(fileHandle);
            line = TrimString(line); // Fixed: Using custom TrimString function
            
            if(StringLen(line) == 0) {
                continue;
            }
            
            // Check for strategy block start
            if(StringFind(line, "[Strategy:") == 0) {
                // Save previous config if exists
                if(inStrategyBlock) {
                    m_strategyConfigs.AddConfig(currentConfig);
                }
                
                // Start new config
                currentConfig = SStrategyConfig();
                string strategyName = StringSubstr(line, 10, StringLen(line) - 11);
                currentConfig.strategyName = strategyName;
                inStrategyBlock = true;
                continue;
            }
            
            if(!inStrategyBlock) {
                continue;
            }
            
            // Parse key=value pairs
            int separatorPos = StringFind(line, "=");
            if(separatorPos > 0) {
                string key = StringSubstr(line, 0, separatorPos);
                string value = StringSubstr(line, separatorPos + 1);
                
                // Parse settings based on key
                if(key == "enabled") currentConfig.enabled = (StringToInteger(value) != 0);
                else if(key == "frequency") currentConfig.frequency = (STRATEGY_FREQUENCY)StringToInteger(value);
                else if(key == "symbol") currentConfig.symbol = value;
                else if(key == "timeframe") currentConfig.timeframe = (ENUM_TIMEFRAMES)StringToInteger(value);
                else if(key == "riskPercent") currentConfig.riskPercent = StringToDouble(value);
                else if(key == "maxPositions") currentConfig.maxPositions = StringToDouble(value);
                else if(key == "maxDailyTrades") currentConfig.maxDailyTrades = StringToDouble(value);
                else if(key == "useGlobalRisk") currentConfig.useGlobalRisk = (StringToInteger(value) != 0);
                else if(key == "param1") currentConfig.param1 = StringToDouble(value);
                else if(key == "param2") currentConfig.param2 = StringToDouble(value);
                else if(key == "param3") currentConfig.param3 = StringToDouble(value);
                else if(key == "param4") currentConfig.param4 = StringToDouble(value);
                else if(key == "param5") currentConfig.param5 = StringToDouble(value);
                else if(key == "paramInt1") currentConfig.paramInt1 = (int)StringToInteger(value);
                else if(key == "paramInt2") currentConfig.paramInt2 = (int)StringToInteger(value);
                else if(key == "paramInt3") currentConfig.paramInt3 = (int)StringToInteger(value);
                else if(key == "paramString1") currentConfig.paramString1 = value;
                else if(key == "paramString2") currentConfig.paramString2 = value;
                else if(key == "magicNumber") currentConfig.magicNumber = (int)StringToInteger(value);
            }
        }
        
        // Save the last config
        if(inStrategyBlock) {
            m_strategyConfigs.AddConfig(currentConfig);
        }
        
        FileClose(fileHandle);
        
        Print("Loaded ", IntegerToString(m_strategyConfigs.GetCount()), " strategy configs from: ", filename);
        return true;
    }
    
    // Save strategy configurations
    bool SaveStrategyConfigs() {
        string filename = m_configPath + "Strategies.ini";
        
        int fileHandle = FileOpen(filename, FILE_WRITE|FILE_TXT);
        if(fileHandle == INVALID_HANDLE) {
            Print("Failed to create strategy configs file: ", filename);
            return false;
        }
        
        // Write header
        FileWrite(fileHandle, "# Solara Strategy Configurations");
        FileWrite(fileHandle, "# Generated on: ", TimeToString(TimeCurrent()));
        FileWrite(fileHandle, "");
        
        // Write each strategy
        int count = m_strategyConfigs.GetCount();
        for(int i = 0; i < count; i++) {
            SStrategyConfig config;
            if(m_strategyConfigs.GetConfig(i, config)) {
                FileWrite(fileHandle, "[Strategy:", config.strategyName, "]");
                FileWrite(fileHandle, "enabled=", IntegerToString(config.enabled));
                FileWrite(fileHandle, "frequency=", IntegerToString(config.frequency));
                FileWrite(fileHandle, "symbol=", config.symbol);
                FileWrite(fileHandle, "timeframe=", IntegerToString(config.timeframe));
                FileWrite(fileHandle, "riskPercent=", DoubleToString(config.riskPercent, 2));
                FileWrite(fileHandle, "maxPositions=", DoubleToString(config.maxPositions, 0));
                FileWrite(fileHandle, "maxDailyTrades=", DoubleToString(config.maxDailyTrades, 0));
                FileWrite(fileHandle, "useGlobalRisk=", IntegerToString(config.useGlobalRisk));
                
                if(config.param1 != 0) FileWrite(fileHandle, "param1=", DoubleToString(config.param1, 5));
                if(config.param2 != 0) FileWrite(fileHandle, "param2=", DoubleToString(config.param2, 5));
                if(config.param3 != 0) FileWrite(fileHandle, "param3=", DoubleToString(config.param3, 5));
                if(config.param4 != 0) FileWrite(fileHandle, "param4=", DoubleToString(config.param4, 5));
                if(config.param5 != 0) FileWrite(fileHandle, "param5=", DoubleToString(config.param5, 5));
                
                if(config.paramInt1 != 0) FileWrite(fileHandle, "paramInt1=", IntegerToString(config.paramInt1));
                if(config.paramInt2 != 0) FileWrite(fileHandle, "paramInt2=", IntegerToString(config.paramInt2));
                if(config.paramInt3 != 0) FileWrite(fileHandle, "paramInt3=", IntegerToString(config.paramInt3));
                
                if(StringLen(config.paramString1) > 0) FileWrite(fileHandle, "paramString1=", config.paramString1);
                if(StringLen(config.paramString2) > 0) FileWrite(fileHandle, "paramString2=", config.paramString2);
                
                if(config.magicNumber > 0) FileWrite(fileHandle, "magicNumber=", IntegerToString(config.magicNumber));
                
                FileWrite(fileHandle, ""); // Empty line between strategies
            }
        }
        
        FileClose(fileHandle);
        Print("Saved ", IntegerToString(m_strategyConfigs.GetCount()), " strategy configs to: ", filename);
        return true;
    }
    
    // Create directory if it doesn't exist
    bool CreateDirectory(string path) {
        // Check if directory exists by trying to open a file in it
        string testFile = path + "test.tmp";
        int handle = FileOpen(testFile, FILE_WRITE|FILE_TXT);
        if(handle != INVALID_HANDLE) {
            FileClose(handle);
            FileDelete(testFile);
            return true;
        }
        
        // Try to create the directory
        ResetLastError();
        if(FolderCreate(path)) {
            return true;
        }
        
        // Check if error is because directory already exists
        int error = GetLastError();
        if(error == 5020) { // 5020 = folder already exists
            return true;
        }
        
        Print("Failed to create directory: ", path, " Error: ", error);
        return false;
    }
};

#endif