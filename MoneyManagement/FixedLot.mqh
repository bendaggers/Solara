//+------------------------------------------------------------------+
//| FixedLot.mqh                                                     |
//| Description: Fixed lot size for testing and simple trading       |
//+------------------------------------------------------------------+
#ifndef FIXEDLOT_MQH
#define FIXEDLOT_MQH

#include "MoneyManagerBase.mqh"

//+------------------------------------------------------------------+
//| CFixedLot - Fixed lot size money management                      |
//+------------------------------------------------------------------+
class CFixedLot : public CMoneyManagerBase {
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CFixedLot() {
        m_config.method = MM_FIXED_LOT;
        m_config.fixedLotSize = 0.01;  // Default
    }
    
    //+------------------------------------------------------------------+
    //| Overridden initialization                                        |
    //+------------------------------------------------------------------+
    virtual bool Initialize(CSymbolInfo* symbolInfo = NULL, 
                           CRiskManager* riskManager = NULL,
                           CLogger* logger = NULL) override {
        if(!CMoneyManagerBase::Initialize(symbolInfo, riskManager, logger)) {
            return false;
        }
        
        LogInfo("Fixed Lot Money Manager initialized");
        LogInfo("Default lot size: " + DoubleToString(m_config.fixedLotSize, 2));
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Core calculation methods                                         |
    //+------------------------------------------------------------------+
    virtual SCalcResult CalculatePositionSize(const SCalcParams &params) override {
        SCalcResult result;
        result.calculationTime = TimeCurrent();
        
        // Use the fixed lot size from config
        double lotSize = m_config.fixedLotSize;
        
        // Apply lot size limits (min/max, lot step rounding)
        lotSize = ApplyLotSizeLimits(params.symbol, lotSize);
        
        // Validate
        if(!ValidateLotSize(params.symbol, lotSize)) {
            result.errorMessage = "Lot size validation failed";
            result.success = false;
            return result;
        }
        
        // Calculate stop loss pips for reporting
        double stopLossPips = CalculateStopLossPips(params.symbol, params.entryPrice, 
                                                   params.stopLossPrice, params.orderType);
        
        // Populate result
        result.success = true;
        result.lotSize = lotSize;
        result.riskAmount = 0.0;  // Fixed lot doesn't calculate risk
        result.riskPercent = 0.0;
        result.positionValue = CalculatePositionValue(params.symbol, lotSize, params.entryPrice);
        result.stopLossPips = stopLossPips;
        result.positionSizePercent = CalculatePositionSizePercent(params.symbol, lotSize, 
                                                                 params.entryPrice, params.accountBalance);
        
        RecordCalculation(result);
        
        LogDebug("Fixed Lot Calculation: " + 
                 "Lot=" + DoubleToString(result.lotSize, 2) + 
                 ", Value=" + DoubleToString(result.positionValue, 2));
        
        return result;
    }
    
    virtual double CalculateRiskAmount(const SCalcParams &params) override {
        // Fixed lot doesn't calculate risk based on account
        return 0.0;
    }
    
    virtual double CalculateOptimalLotSize(double riskAmount, const SCalcParams &params) override {
        // Always return the fixed lot size
        return m_config.fixedLotSize;
    }
    
    //+------------------------------------------------------------------+
    //| Setter methods                                                   |
    //+------------------------------------------------------------------+
    void SetLotSize(double lotSize) {
        if(lotSize > 0) {
            m_config.fixedLotSize = lotSize;
            LogInfo("Lot size set to: " + DoubleToString(lotSize, 2));
        } else {
            LogError("Invalid lot size: " + DoubleToString(lotSize, 2));
        }
    }
    
    double GetLotSize() const {
        return m_config.fixedLotSize;
    }
    
    //+------------------------------------------------------------------+
    //| Information methods                                              |
    //+------------------------------------------------------------------+
    virtual string GetName() const override {
        return "FixedLot";
    }
    
    virtual string GetDescription() const override {
        return "Fixed lot size: " + DoubleToString(m_config.fixedLotSize, 2) + " lots";
    }
    
private:
    //+------------------------------------------------------------------+
    //| Helper methods                                                   |
    //+------------------------------------------------------------------+
    double CalculatePositionValue(string symbol, double lotSize, double price) {
        double contractSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
        return lotSize * contractSize * price;
    }
    
    double CalculatePositionSizePercent(string symbol, double lotSize, double price, double accountBalance) {
        if(accountBalance <= 0) return 0.0;
        double positionValue = CalculatePositionValue(symbol, lotSize, price);
        return (positionValue / accountBalance) * 100.0;
    }
};

#endif // FIXEDLOT_MQH