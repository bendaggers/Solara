//+------------------------------------------------------------------+
//| MoneyManagerFactory.mqh                                          |
//| Description: Factory pattern for creating and managing           |
//|              money management instances                          |
//+------------------------------------------------------------------+
#ifndef MONEYMANAGERFACTORY_MQH
#define MONEYMANAGERFACTORY_MQH

#include "MoneyManagerBase.mqh"
#include "FixedFractional.mqh"
#include "FixedLot.mqh"
// Include other money managers as they are created
// #include "VolatilityBased.mqh"
// #include "KellyCriterion.mqh"
// #include "FixedRatio.mqh"

//+------------------------------------------------------------------+
//| Money manager creation parameters                                |
//+------------------------------------------------------------------+
struct SMoneyManagerCreateParams {
    ENUM_MONEY_MANAGEMENT method;
    SMoneyManagerConfig config;
    string customClassName;  // For custom implementations
    
    SMoneyManagerCreateParams() {
        method = MM_FIXED_FRACTIONAL;
        customClassName = "";
    }
};

//+------------------------------------------------------------------+
//| CMoneyManagerFactory - Factory for money managers                |
//+------------------------------------------------------------------+
class CMoneyManagerFactory {
private:
    // Registry of available money managers
    struct SMoneyManagerInfo {
        ENUM_MONEY_MANAGEMENT method;
        string className;
        string description;
    };
    
    SMoneyManagerInfo m_registry[10];
    int m_registryCount;
    
    // Component dependencies
    CSymbolInfo* m_symbolInfo;
    CRiskManager* m_riskManager;
    CLogger* m_logger;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CMoneyManagerFactory() : 
        m_registryCount(0),
        m_symbolInfo(NULL),
        m_riskManager(NULL),
        m_logger(NULL)
    {
        InitializeRegistry();
    }
    
    ~CMoneyManagerFactory() {
        // Cleanup
    }
    
    //+------------------------------------------------------------------+
    //| Initialization                                                   |
    //+------------------------------------------------------------------+
    void Initialize(CSymbolInfo* symbolInfo = NULL, 
                   CRiskManager* riskManager = NULL,
                   CLogger* logger = NULL) {
        m_symbolInfo = symbolInfo;
        m_riskManager = riskManager;
        m_logger = logger;
        
        if(m_logger != NULL) {
            m_logger.Info("Money Manager Factory initialized", "MoneyManagerFactory");
        }
    }
    
    //+------------------------------------------------------------------+
    //| Money Manager Creation                                           |
    //+------------------------------------------------------------------+
    CMoneyManagerBase* CreateMoneyManager(ENUM_MONEY_MANAGEMENT method) {
        SMoneyManagerCreateParams params;
        params.method = method;
        // Create a default config
        params.config = SMoneyManagerConfig();
        params.config.method = method;
        return CreateMoneyManager(params);
    }
    
    CMoneyManagerBase* CreateMoneyManager(const SMoneyManagerCreateParams &params) {
        CMoneyManagerBase* moneyManager = NULL;
        
        switch(params.method) {
            case MM_FIXED_FRACTIONAL:
                moneyManager = CreateFixedFractional(params.config);
                break;
                
            case MM_FIXED_LOT:
                moneyManager = CreateFixedLot(params.config);
                break;
                
            case MM_VOLATILITY_BASED:
                // moneyManager = CreateVolatilityBased(params.config);
                if(m_logger != NULL) {
                    m_logger.Warn("VolatilityBased money manager not yet implemented", "MoneyManagerFactory");
                }
                break;
                
            case MM_KELLY_CRITERION:
                // moneyManager = CreateKellyCriterion(params.config);
                if(m_logger != NULL) {
                    m_logger.Warn("KellyCriterion money manager not yet implemented", "MoneyManagerFactory");
                }
                break;
                
            case MM_FIXED_RATIO:
                // moneyManager = CreateFixedRatio(params.config);
                if(m_logger != NULL) {
                    m_logger.Warn("FixedRatio money manager not yet implemented", "MoneyManagerFactory");
                }
                break;
                
            case MM_CUSTOM:
                moneyManager = CreateCustomMoneyManager(params.customClassName, params.config);
                break;
                
            default:
                if(m_logger != NULL) {
                    m_logger.Error("Unknown money management method: " + IntegerToString(params.method), 
                                  "MoneyManagerFactory");
                }
                break;
        }
        
        if(moneyManager != NULL && m_logger != NULL) {
            string managerName = moneyManager.GetName();
            m_logger.Info("Created money manager: " + managerName, "MoneyManagerFactory");
        }
        
        return moneyManager;
    }
    
    //+------------------------------------------------------------------+
    //| Specific money manager creators                                  |
    //+------------------------------------------------------------------+
    CFixedFractional* CreateFixedFractional(const SMoneyManagerConfig &config) {
        CFixedFractional* moneyManager = new CFixedFractional();
        
        if(moneyManager != NULL) {
            // Initialize with dependencies
            if(!moneyManager.Initialize(m_symbolInfo, m_riskManager, m_logger)) {
                delete moneyManager;
                if(m_logger != NULL) {
                    m_logger.Error("Failed to initialize FixedFractional money manager", "MoneyManagerFactory");
                }
                return NULL;
            }
            
            // Apply configuration
            moneyManager.SetConfig(config);
        }
        
        return moneyManager;
    }
    
    CFixedFractional* CreateFixedFractional(double riskPercent) {
        SMoneyManagerConfig config;
        config.riskPercent = riskPercent;
        config.method = MM_FIXED_FRACTIONAL;
        
        return CreateFixedFractional(config);
    }
    
    CFixedLot* CreateFixedLot(const SMoneyManagerConfig &config) {
        CFixedLot* moneyManager = new CFixedLot();
        
        if(moneyManager != NULL) {
            // Initialize with dependencies
            if(!moneyManager.Initialize(m_symbolInfo, m_riskManager, m_logger)) {
                delete moneyManager;
                if(m_logger != NULL) {
                    m_logger.Error("Failed to initialize FixedLot money manager", "MoneyManagerFactory");
                }
                return NULL;
            }
            
            // Apply configuration
            moneyManager.SetConfig(config);
            
            // Set specific lot size if provided
            if(config.fixedLotSize > 0) {
                moneyManager.SetLotSize(config.fixedLotSize);
            }
        }
        
        return moneyManager;
    }
    
    CFixedLot* CreateFixedLot(double lotSize) {
        SMoneyManagerConfig config;
        config.method = MM_FIXED_LOT;
        config.fixedLotSize = lotSize;
        
        return CreateFixedLot(config);
    }
    
    // Template for other creators (to be implemented when files are created)
    /*
    CVolatilityBased* CreateVolatilityBased(const SMoneyManagerConfig &config) {
        CVolatilityBased* moneyManager = new CVolatilityBased();
        // Initialization logic
        return moneyManager;
    }
    
    CKellyCriterion* CreateKellyCriterion(const SMoneyManagerConfig &config) {
        CKellyCriterion* moneyManager = new CKellyCriterion();
        // Initialization logic
        return moneyManager;
    }
    
    CFixedRatio* CreateFixedRatio(const SMoneyManagerConfig &config) {
        CFixedRatio* moneyManager = new CFixedRatio();
        // Initialization logic
        return moneyManager;
    }
    */
    
    //+------------------------------------------------------------------+
    //| Custom money manager creation                                    |
    //+------------------------------------------------------------------+
    CMoneyManagerBase* CreateCustomMoneyManager(string className, const SMoneyManagerConfig &config) {
        if(className == "") {
            if(m_logger != NULL) {
                m_logger.Error("Custom money manager class name is empty", "MoneyManagerFactory");
            }
            return NULL;
        }
        
        // This is a placeholder for dynamic creation
        // In MQL5, dynamic creation by class name is limited
        // You would need to implement a registration system
        
        if(m_logger != NULL) {
            m_logger.Warn("Custom money manager creation not fully implemented: " + className, 
                         "MoneyManagerFactory");
        }
        
        return NULL;
    }
    
    //+------------------------------------------------------------------+
    //| Registry management                                              |
    //+------------------------------------------------------------------+
    bool RegisterMoneyManager(ENUM_MONEY_MANAGEMENT method, string className, string description) {
        if(m_registryCount >= 10) {
            if(m_logger != NULL) {
                m_logger.Error("Money manager registry is full", "MoneyManagerFactory");
            }
            return false;
        }
        
        m_registry[m_registryCount].method = method;
        m_registry[m_registryCount].className = className;
        m_registry[m_registryCount].description = description;
        m_registryCount++;
        
        if(m_logger != NULL) {
            m_logger.Info("Registered money manager: " + className, "MoneyManagerFactory");
        }
        
        return true;
    }
    
    bool UnregisterMoneyManager(ENUM_MONEY_MANAGEMENT method) {
        for(int i = 0; i < m_registryCount; i++) {
            if(m_registry[i].method == method) {
                // Shift remaining entries
                for(int j = i; j < m_registryCount - 1; j++) {
                    m_registry[j] = m_registry[j + 1];
                }
                m_registryCount--;
                
                if(m_logger != NULL) {
                    m_logger.Info("Unregistered money manager: " + IntegerToString(method), 
                                 "MoneyManagerFactory");
                }
                return true;
            }
        }
        return false;
    }
    
    int GetRegisteredCount() const {
        return m_registryCount;
    }
    
    string GetMethodInfo(ENUM_MONEY_MANAGEMENT method) const {
        for(int i = 0; i < m_registryCount; i++) {
            if(m_registry[i].method == method) {
                return m_registry[i].className + " - " + m_registry[i].description;
            }
        }
        return "Not registered";
    }
    
    void PrintRegistry() {
        if(m_logger == NULL) return;
        
        m_logger.Info("=== Money Manager Registry ===", "MoneyManagerFactory");
        m_logger.Info("Registered Count: " + IntegerToString(m_registryCount), "MoneyManagerFactory");
        
        for(int i = 0; i < m_registryCount; i++) {
            string info = "[" + IntegerToString(i) + "] " +
                         "Method: " + IntegerToString(m_registry[i].method) +
                         ", Class: " + m_registry[i].className +
                         ", Desc: " + m_registry[i].description;
            m_logger.Info(info, "MoneyManagerFactory");
        }
        
        m_logger.Info("=============================", "MoneyManagerFactory");
    }
    
    //+------------------------------------------------------------------+
    //| Configuration helpers                                            |
    //+------------------------------------------------------------------+
    SMoneyManagerConfig CreateDefaultConfig(ENUM_MONEY_MANAGEMENT method) {
        SMoneyManagerConfig config;
        config.method = method;
        
        // Set method-specific defaults
        switch(method) {
            case MM_FIXED_FRACTIONAL:
                config.riskPercent = 1.0;
                config.maxPositionSizePercent = 2.0;
                break;
                
            case MM_FIXED_LOT:
                config.fixedLotSize = 0.01;
                config.maxPositionSizePercent = 5.0;
                break;
                
            case MM_VOLATILITY_BASED:
                config.volatilityPeriod = 14;
                config.volatilityMultiplier = 1.0;
                config.maxPositionSizePercent = 3.0;
                break;
                
            case MM_KELLY_CRITERION:
                config.kellyFraction = 0.25;
                config.maxPositionSizePercent = 2.0;
                break;
                
            case MM_FIXED_RATIO:
                config.fixedRatioDelta = 1000.0;
                config.maxPositionSizePercent = 2.5;
                break;
        }
        
        return config;
    }
    
    SMoneyManagerCreateParams CreateDefaultParams(ENUM_MONEY_MANAGEMENT method) {
        SMoneyManagerCreateParams params;
        params.method = method;
        params.config = CreateDefaultConfig(method);
        return params;
    }
    
    //+------------------------------------------------------------------+
    //| Batch creation and management                                    |
    //+------------------------------------------------------------------+
    int CreateMultipleManagers(ENUM_MONEY_MANAGEMENT &methods[], int count, 
                              CMoneyManagerBase* &managers[]) {
        if(count <= 0) return 0;
        
        ArrayResize(managers, count);
        int successCount = 0;
        
        for(int i = 0; i < count; i++) {
            managers[i] = CreateMoneyManager(methods[i]);
            if(managers[i] != NULL) {
                successCount++;
            }
        }
        
        return successCount;
    }
    
    void DeleteMultipleManagers(CMoneyManagerBase* &managers[]) {
        int count = ArraySize(managers);
        for(int i = 0; i < count; i++) {
            if(CheckPointer(managers[i]) == POINTER_DYNAMIC) {
                delete managers[i];
                managers[i] = NULL;
            }
        }
        ArrayFree(managers);
    }
    
    //+------------------------------------------------------------------+
    //| Utility methods                                                  |
    //+------------------------------------------------------------------+
    string MethodToString(ENUM_MONEY_MANAGEMENT method) {
        switch(method) {
            case MM_FIXED_FRACTIONAL: return "FixedFractional";
            case MM_FIXED_LOT: return "FixedLot";
            case MM_VOLATILITY_BASED: return "VolatilityBased";
            case MM_KELLY_CRITERION: return "KellyCriterion";
            case MM_FIXED_RATIO: return "FixedRatio";
            case MM_CUSTOM: return "Custom";
            default: return "Unknown";
        }
    }
    
    ENUM_MONEY_MANAGEMENT StringToMethod(string methodName) {
        if(methodName == "FixedFractional") return MM_FIXED_FRACTIONAL;
        if(methodName == "FixedLot") return MM_FIXED_LOT;
        if(methodName == "VolatilityBased") return MM_VOLATILITY_BASED;
        if(methodName == "KellyCriterion") return MM_KELLY_CRITERION;
        if(methodName == "FixedRatio") return MM_FIXED_RATIO;
        if(methodName == "Custom") return MM_CUSTOM;
        return MM_FIXED_FRACTIONAL; // Default
    }
    
private:
    //+------------------------------------------------------------------+
    //| Private initialization                                           |
    //+------------------------------------------------------------------+
    void InitializeRegistry() {
        // Register built-in money managers
        RegisterMoneyManager(MM_FIXED_FRACTIONAL, "CFixedFractional", 
                           "Fixed percentage risk per trade");
        
        RegisterMoneyManager(MM_FIXED_LOT, "CFixedLot", 
                           "Fixed lot size for testing and simple trading");
        
        // These will be registered when their classes are created
        /*
        RegisterMoneyManager(MM_VOLATILITY_BASED, "CVolatilityBased", 
                           "ATR-based position sizing");
        RegisterMoneyManager(MM_KELLY_CRITERION, "CKellyCriterion", 
                           "Kelly criterion optimal betting");
        RegisterMoneyManager(MM_FIXED_RATIO, "CFixedRatio", 
                           "Fixed ratio position sizing");
        RegisterMoneyManager(MM_CUSTOM, "Custom", 
                           "Custom money manager implementation");
        */
    }
};

#endif // MONEYMANAGERFACTORY_MQH