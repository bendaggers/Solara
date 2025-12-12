// Configuration/StrategyConfig.mqh
#ifndef STRATEGYCONFIG_MQH
#define STRATEGYCONFIG_MQH

// First, define STRATEGY_FREQUENCY enum here since StrategyBase.mqh might not be ready yet
enum STRATEGY_FREQUENCY {
    FREQ_TICK_BASED = 0,    // Execute on every tick
    FREQ_1_MIN = 1,         // Every minute  
    FREQ_5_MIN = 2,         // Every 5 minutes
    FREQ_15_MIN = 3,        // Every 15 minutes
    FREQ_1_HOUR = 4,        // Hourly
    FREQ_4_HOUR = 5,        // Every 4 hours
    FREQ_DAILY = 6,         // Daily
    FREQ_WEEKLY = 7         // Weekly
};

// Helper function to convert frequency to string
string FrequencyToString(STRATEGY_FREQUENCY freq) {
    switch(freq) {
        case FREQ_TICK_BASED: return "TICK_BASED";
        case FREQ_1_MIN: return "1_MIN";
        case FREQ_5_MIN: return "5_MIN";
        case FREQ_15_MIN: return "15_MIN";
        case FREQ_1_HOUR: return "1_HOUR";
        case FREQ_4_HOUR: return "4_HOUR";
        case FREQ_DAILY: return "DAILY";
        case FREQ_WEEKLY: return "WEEKLY";
        default: return "UNKNOWN";
    }
}

// Strategy configuration structure
struct SStrategyConfig {
    // Basic identification
    string strategyName;
    string strategyClass;      // Class name to instantiate
    bool enabled;
    STRATEGY_FREQUENCY frequency;
    
    // Instrument settings
    string symbol;
    ENUM_TIMEFRAMES timeframe;
    
    // Risk parameters
    double riskPercent;        // Risk per trade as % of account
    double maxPositions;       // Maximum concurrent positions
    double maxDailyTrades;     // Maximum trades per day
    bool useGlobalRisk;        // Use global risk settings
    
    // Strategy-specific parameters (generic container)
    double param1;
    double param2;
    double param3;
    double param4;
    double param5;
    int paramInt1;
    int paramInt2;
    int paramInt3;
    string paramString1;
    string paramString2;
    
    // Magic number generation
    int magicNumber;
    int GetMagicNumber(int base) const {
        if(magicNumber > 0) return magicNumber;
        // Generate based on strategy name and base
        int hash = 0;
        for(int i = 0; i < StringLen(strategyName); i++) {
            hash = 31 * hash + StringGetCharacter(strategyName, i);
        }
        return base + (MathAbs(hash) % 9000); // Ensure 4-digit offset
    }
    
    // Validation
    bool Validate() const {
        if(StringLen(strategyName) == 0) {
            Print("Error: Strategy name cannot be empty");
            return false;
        }
        
        if(StringLen(symbol) == 0) {
            Print("Error: Symbol cannot be empty");
            return false;
        }
        
        if(riskPercent <= 0 || riskPercent > 10) {
            Print("Error: riskPercent must be between 0.01 and 10");
            return false;
        }
        
        if(maxPositions < 1) {
            Print("Error: maxPositions must be at least 1");
            return false;
        }
        
        return true;
    }
    
    // Print configuration
    void PrintConfig() const {
        Print("=== Strategy Config: ", strategyName, " ===");
        Print("Enabled: ", enabled);
        Print("Frequency: ", FrequencyToString(frequency));
        Print("Symbol: ", symbol);
        Print("Timeframe: ", EnumToString(timeframe));
        Print("Risk %: ", riskPercent);
        Print("Max Positions: ", maxPositions);
        Print("Max Daily Trades: ", maxDailyTrades);
        Print("Magic Number: ", magicNumber);
        
        if(param1 != 0) Print("Param1: ", param1);
        if(param2 != 0) Print("Param2: ", param2);
        if(param3 != 0) Print("Param3: ", param3);
        if(param4 != 0) Print("Param4: ", param4);
        if(param5 != 0) Print("Param5: ", param5);
        
        if(paramInt1 != 0) Print("ParamInt1: ", paramInt1);
        if(paramInt2 != 0) Print("ParamInt2: ", paramInt2);
        if(paramInt3 != 0) Print("ParamInt3: ", paramInt3);
        
        if(StringLen(paramString1) > 0) Print("ParamString1: ", paramString1);
        if(StringLen(paramString2) > 0) Print("ParamString2: ", paramString2);
        
        Print("==========================");
    }
};

// Configuration manager for strategies
class CStrategyConfigManager {
private:
    SStrategyConfig m_configs[];
    int m_count;
    
public:
    CStrategyConfigManager() {
        m_count = 0;
    }
    
    ~CStrategyConfigManager() {
        ArrayFree(m_configs);
    }
    
    // Add a strategy configuration
    bool AddConfig(const SStrategyConfig &config) {
        if(!config.Validate()) {
            Print("Failed to add invalid strategy config: ", config.strategyName);
            return false;
        }
        
        int newSize = m_count + 1;
        if(ArrayResize(m_configs, newSize) != newSize) {
            Print("Failed to resize config array");
            return false;
        }
        
        m_configs[m_count] = config;
        m_count++;
        
        Print("Added strategy config: ", config.strategyName);
        return true;
    }
    
    // Get configuration by index
    bool GetConfig(int index, SStrategyConfig &config) const {
        if(index < 0 || index >= m_count) {
            return false;
        }
        
        config = m_configs[index];
        return true;
    }
    
    // Get configuration by name
    bool GetConfigByName(const string name, SStrategyConfig &config) const {
        for(int i = 0; i < m_count; i++) {
            if(m_configs[i].strategyName == name) {
                config = m_configs[i];
                return true;
            }
        }
        return false;
    }
    
    // Get number of configurations
    int GetCount() const {
        return m_count;
    }
    
    // Remove configuration by name
    bool RemoveConfig(const string name) {
        for(int i = 0; i < m_count; i++) {
            if(m_configs[i].strategyName == name) {
                // Shift remaining elements
                for(int j = i; j < m_count - 1; j++) {
                    m_configs[j] = m_configs[j + 1];
                }
                
                m_count--;
                if(ArrayResize(m_configs, m_count) != m_count) {
                    Print("Warning: Failed to resize array after removal");
                }
                
                Print("Removed strategy config: ", name);
                return true;
            }
        }
        return false;
    }
    
    // Clear all configurations
    void Clear() {
        ArrayFree(m_configs);
        m_count = 0;
    }
    
    // Print all configurations
    void PrintAll() const {
        Print("=== Strategy Configurations (", m_count, " total) ===");
        for(int i = 0; i < m_count; i++) {
            m_configs[i].PrintConfig();
        }
    }
};

#endif