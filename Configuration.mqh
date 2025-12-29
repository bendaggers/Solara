// Configuration.mqh - Central configuration handler
//+------------------------------------------------------------------+
//| Description: Manages global configuration and settings           |
//+------------------------------------------------------------------+
#ifndef CONFIGURATION_MQH
#define CONFIGURATION_MQH

//+------------------------------------------------------------------+
//| Global configuration structure                                   |
//+------------------------------------------------------------------+
struct GlobalConfig
{
    bool     enableTrading;        // Master trading toggle
    int      scanIntervalSeconds;  // Base scan frequency
    double   globalDailyLossLimit; // Total daily loss limit
    string   csvFileName;          // Output CSV file
    bool     appendToCSV;          // Append to existing CSV
    
    GlobalConfig()
    {
        enableTrading = false;
        scanIntervalSeconds = 60;
        globalDailyLossLimit = 500.0;
        csvFileName = "ScannerSignals.csv";
        appendToCSV = true;
    }
};

//+------------------------------------------------------------------+
//| EMA strategy configuration                                       |
//+------------------------------------------------------------------+
struct EMAConfig
{
    bool     enabled;              // Enable EMA strategy
    int      fastPeriod;           // Fast EMA period
    int      slowPeriod;           // Slow EMA period
    double   lotSize;              // Lot size
    double   dailyLossLimit;       // Daily loss limit
    int      maxPositions;         // Maximum positions
    int      magicNumber;          // Magic number
    
    EMAConfig()
    {
        enabled = true;
        fastPeriod = 20;
        slowPeriod = 50;
        lotSize = 0.01;
        dailyLossLimit = 100.0;
        maxPositions = 10;
        magicNumber = 12345;
    }
};

//+------------------------------------------------------------------+
//| PTS strategy configuration                                       |
//+------------------------------------------------------------------+
struct PTSConfig
{
    bool     enabled;              // Enable PTS strategy
    double   lotSize;              // Lot size
    double   dailyLossLimit;       // Daily loss limit
    int      maxPositions;         // Maximum positions
    int      magicNumber;          // Magic number
    double   slMultiplier;         // Stop loss multiplier
    double   tpMultiplier;         // Take profit multiplier
    int      bbPeriod;             // Bollinger Band period
    double   bbDeviation;          // Bollinger Band deviation
    int      atrPeriod;            // ATR period
    string   csvFileName;          // Qualified pairs CSV
    
    PTSConfig()
    {
        enabled = false;
        lotSize = 0.01;
        dailyLossLimit = 100.0;
        maxPositions = 10;
        magicNumber = 202412;
        slMultiplier = 2.0;
        tpMultiplier = 4.0;
        bbPeriod = 20;
        bbDeviation = 2.0;
        atrPeriod = 14;
        csvFileName = "QualifiedPairs.csv";
    }
};

//+------------------------------------------------------------------+
//| Configuration Manager Class                                      |
//+------------------------------------------------------------------+
class CConfigurationManager
{
private:
    GlobalConfig  m_global;
    EMAConfig     m_ema;
    PTSConfig     m_pts;
    
public:
    // Constructor
    CConfigurationManager() {}
    
    // Get global configuration
    GlobalConfig GetGlobalConfig() { return m_global; }
    
    // Get EMA configuration
    EMAConfig GetEMAConfig() { return m_ema; }
    
    // Get PTS configuration
    PTSConfig GetPTSConfig() { return m_pts; }
    
    // Set global configuration
    void SetGlobalConfig(const GlobalConfig &config) { m_global = config; }
    
    // Set EMA configuration
    void SetEMAConfig(const EMAConfig &config) { m_ema = config; }
    
    // Set PTS configuration
    void SetPTSConfig(const PTSConfig &config) { m_pts = config; }
    
    // Validate all configurations
    bool ValidateAll()
    {
        if(m_global.scanIntervalSeconds < 10)
        {
            Print("ERROR: Scan interval too short (minimum 10 seconds)");
            return false;
        }
        
        if(m_global.globalDailyLossLimit < 0)
        {
            Print("ERROR: Global daily loss limit cannot be negative");
            return false;
        }
        
        if(m_ema.enabled)
        {
            if(m_ema.fastPeriod <= 0 || m_ema.slowPeriod <= 0)
            {
                Print("ERROR: EMA periods must be positive");
                return false;
            }
            
            if(m_ema.fastPeriod >= m_ema.slowPeriod)
            {
                Print("ERROR: Fast EMA period must be less than slow EMA period");
                return false;
            }
            
            if(m_ema.lotSize <= 0)
            {
                Print("ERROR: EMA lot size must be positive");
                return false;
            }
        }
        
        if(m_pts.enabled)
        {
            if(m_pts.slMultiplier <= 0 || m_pts.tpMultiplier <= 0)
            {
                Print("ERROR: PTS multipliers must be positive");
                return false;
            }
            
            if(m_pts.lotSize <= 0)
            {
                Print("ERROR: PTS lot size must be positive");
                return false;
            }
            
            if(m_pts.bbPeriod <= 0 || m_pts.bbDeviation <= 0)
            {
                Print("ERROR: Bollinger Band parameters must be positive");
                return false;
            }
        }
        
        return true;
    }
    
    // Print all configurations
    void PrintAll()
    {
        Print("=== Configuration Summary ===");
        
        Print("Global Settings:");
        Print("  Trading Enabled: ", m_global.enableTrading ? "Yes" : "No");
        Print("  Scan Interval: ", m_global.scanIntervalSeconds, " seconds");
        Print("  Global Loss Limit: $", m_global.globalDailyLossLimit);
        Print("  CSV File: ", m_global.csvFileName);
        
        Print("EMA Strategy:");
        Print("  Enabled: ", m_ema.enabled ? "Yes" : "No");
        Print("  Fast EMA: ", m_ema.fastPeriod);
        Print("  Slow EMA: ", m_ema.slowPeriod);
        Print("  Lot Size: ", m_ema.lotSize);
        Print("  Loss Limit: $", m_ema.dailyLossLimit);
        Print("  Max Positions: ", m_ema.maxPositions);
        Print("  Magic Number: ", m_ema.magicNumber);
        
        Print("PTS Strategy:");
        Print("  Enabled: ", m_pts.enabled ? "Yes" : "No");
        Print("  Lot Size: ", m_pts.lotSize);
        Print("  Loss Limit: $", m_pts.dailyLossLimit);
        Print("  Max Positions: ", m_pts.maxPositions);
        Print("  Magic Number: ", m_pts.magicNumber);
        Print("  SL Multiplier: ", m_pts.slMultiplier);
        Print("  TP Multiplier: ", m_pts.tpMultiplier);
        Print("  BB Period: ", m_pts.bbPeriod);
        Print("  BB Deviation: ", m_pts.bbDeviation);
        Print("  ATR Period: ", m_pts.atrPeriod);
        Print("  Risk-Reward: 1:", DoubleToString(m_pts.tpMultiplier / m_pts.slMultiplier, 1));
        
        Print("=============================");
    }
};

#endif // CONFIGURATION_MQH