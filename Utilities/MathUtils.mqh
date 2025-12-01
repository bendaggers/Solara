//+------------------------------------------------------------------+
//| MathUtils.mqh - Mathematical utilities for Solara                |
//+------------------------------------------------------------------+
#ifndef MATHUTILS_MQH
#define MATHUTILS_MQH

#include "Logger.mqh"
#include <Arrays\ArrayDouble.mqh>

//+------------------------------------------------------------------+
//| CMathUtils - Main mathematical utilities class                   |
//+------------------------------------------------------------------+
class CMathUtils {
private:
    CLogger* m_logger;
    
public:
    CMathUtils(void) {
        m_logger = GlobalLogger;
    }
    
    //+------------------------------------------------------------------+
    //| Basic mathematical operations                                    |
    //+------------------------------------------------------------------+
    double Normalize(double value, int digits) {
        return NormalizeDouble(value, digits);
    }
    
    double RoundToTick(double price, double tickSize) {
        if(tickSize <= 0) return price;
        return NormalizeDouble(MathRound(price / tickSize) * tickSize, 8);
    }
    
    double RoundToStep(double value, double step) {
        if(step <= 0) return value;
        return MathRound(value / step) * step;
    }
    
    //+------------------------------------------------------------------+
    //| Statistical calculations                                         |
    //+------------------------------------------------------------------+
    double CalculateMean(const double &array[]) {
        int size = ArraySize(array);
        if(size == 0) return 0;
        
        double sum = 0;
        for(int i = 0; i < size; i++) {
            sum += array[i];
        }
        return sum / size;
    }
    
    double CalculateStandardDeviation(const double &array[], double mean = DBL_MAX) {
        int size = ArraySize(array);
        if(size < 2) return 0;
        
        if(mean == DBL_MAX) {
            mean = CalculateMean(array);
        }
        
        double sumSquares = 0;
        for(int i = 0; i < size; i++) {
            double deviation = array[i] - mean;
            sumSquares += deviation * deviation;
        }
        
        return MathSqrt(sumSquares / (size - 1));
    }
    
    double CalculateVariance(const double &array[], double mean = DBL_MAX) {
        double stdDev = CalculateStandardDeviation(array, mean);
        return stdDev * stdDev;
    }
    
    double CalculateZScore(double value, const double &array[]) {
        double mean = CalculateMean(array);
        double stdDev = CalculateStandardDeviation(array, mean);
        
        if(stdDev == 0) return 0;
        return (value - mean) / stdDev;
    }
    
    //+------------------------------------------------------------------+
    //| Financial calculations                                           |
    //+------------------------------------------------------------------+
    double CalculatePercentageChange(double oldValue, double newValue) {
        if(oldValue == 0) return 0;
        return ((newValue - oldValue) / oldValue) * 100;
    }
    
    double CalculatePipValue(string symbol, double lotSize = 1.0) {
        double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
        double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        
        if(tickSize > 0 && tickValue > 0) {
            return (tickValue / tickSize) * point * lotSize;
        }
        return 0;
    }
    
    double CalculateProfitPips(string symbol, double entryPrice, double exitPrice, bool isBuy) {
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        if(point == 0) return 0;
        
        double priceDiff = isBuy ? (exitPrice - entryPrice) : (entryPrice - exitPrice);
        return priceDiff / point;
    }
    
    //+------------------------------------------------------------------+
    //| Risk management calculations                                     |
    //+------------------------------------------------------------------+
    double CalculatePositionSize(double accountBalance, double riskPercent, double stopLossPips, 
                                string symbol, bool logCalculation = false) {
        if(accountBalance <= 0 || riskPercent <= 0 || stopLossPips <= 0) {
            if(logCalculation && m_logger != NULL) {
                m_logger.Error("Invalid parameters for position size calculation", "MathUtils");
            }
            return 0;
        }
        
        double riskAmount = accountBalance * (riskPercent / 100);
        double pipValue = CalculatePipValue(symbol, 1.0);
        
        if(pipValue <= 0) {
            if(logCalculation && m_logger != NULL) {
                m_logger.Error("Cannot calculate pip value for symbol: " + symbol, "MathUtils");
            }
            return 0;
        }
        
        double lotSize = riskAmount / (stopLossPips * pipValue);
        
        // Normalize to allowed lot steps
        double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
        double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
        double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
        
        lotSize = MathMax(minLot, MathMin(maxLot, lotSize));
        lotSize = RoundToStep(lotSize, lotStep);
        
        if(logCalculation && m_logger != NULL) {
            m_logger.Info(StringFormat("Position size: Balance=%.2f, Risk=%.1f%%, SL=%.1f pips, Lots=%.2f",
                                      accountBalance, riskPercent, stopLossPips, lotSize), "MathUtils");
        }
        
        return lotSize;
    }
    
    double CalculateRiskRewardRatio(double entryPrice, double stopLoss, double takeProfit, bool isBuy) {
        double risk = MathAbs(entryPrice - stopLoss);
        double reward = MathAbs(takeProfit - entryPrice);
        
        if(risk == 0) return 0;
        return reward / risk;
    }
    
    //+------------------------------------------------------------------+
    //| Array operations                                                 |
    //+------------------------------------------------------------------+
    void ArrayReverse(double &array[]) {
        int size = ArraySize(array);
        for(int i = 0; i < size / 2; i++) {
            double temp = array[i];
            array[i] = array[size - 1 - i];
            array[size - 1 - i] = temp;
        }
    }
    
    void ArrayShiftLeft(double &array[], int shiftCount = 1) {
        int size = ArraySize(array);
        if(size <= 1) return;
        
        for(int shift = 0; shift < shiftCount; shift++) {
            for(int i = 0; i < size - 1; i++) {
                array[i] = array[i + 1];
            }
            array[size - 1] = 0;
        }
    }
    
    void ArrayShiftRight(double &array[], int shiftCount = 1) {
        int size = ArraySize(array);
        if(size <= 1) return;
        
        for(int shift = 0; shift < shiftCount; shift++) {
            for(int i = size - 1; i > 0; i--) {
                array[i] = array[i - 1];
            }
            array[0] = 0;
        }
    }
    
    bool ArrayContains(const double &array[], double value, double tolerance = 0.00001) {
        for(int i = 0; i < ArraySize(array); i++) {
            if(MathAbs(array[i] - value) <= tolerance) {
                return true;
            }
        }
        return false;
    }
    
    int ArrayFind(const double &array[], double value, double tolerance = 0.00001) {
        for(int i = 0; i < ArraySize(array); i++) {
            if(MathAbs(array[i] - value) <= tolerance) {
                return i;
            }
        }
        return -1;
    }
    
    //+------------------------------------------------------------------+
    //| Moving average calculations                                      |
    //+------------------------------------------------------------------+
    double CalculateSMA(const double &array[], int period) {
        int size = ArraySize(array);
        if(size < period) return 0;
        
        double sum = 0;
        for(int i = size - period; i < size; i++) {
            sum += array[i];
        }
        return sum / period;
    }
    
    double CalculateEMA(const double &array[], int period, double previousEMA = 0) {
        int size = ArraySize(array);
        if(size == 0) return 0;
        
        double multiplier = 2.0 / (period + 1);
        
        if(previousEMA == 0) {
            // Calculate SMA as initial EMA
            return CalculateSMA(array, MathMin(period, size));
        } else {
            return (array[size - 1] - previousEMA) * multiplier + previousEMA;
        }
    }
    
    //+------------------------------------------------------------------+
    //| Normalization and scaling                                        |
    //+------------------------------------------------------------------+
    void NormalizeArray(double &array[], double minRange = 0, double maxRange = 1) {
        int size = ArraySize(array);
        if(size == 0) return;
        
        double minVal = array[0];
        double maxVal = array[0];
        
        // Find min and max
        for(int i = 1; i < size; i++) {
            if(array[i] < minVal) minVal = array[i];
            if(array[i] > maxVal) maxVal = array[i];
        }
        
        // Normalize
        double range = maxVal - minVal;
        if(range == 0) {
            // All values are the same, set to middle of range
            double mid = (minRange + maxRange) / 2;
            for(int i = 0; i < size; i++) {
                array[i] = mid;
            }
        } else {
            for(int i = 0; i < size; i++) {
                array[i] = minRange + (array[i] - minVal) * (maxRange - minRange) / range;
            }
        }
    }
    
    double ScaleValue(double value, double oldMin, double oldMax, double newMin, double newMax) {
        if(oldMax == oldMin) return newMin;
        return newMin + (value - oldMin) * (newMax - newMin) / (oldMax - oldMin);
    }
    
    //+------------------------------------------------------------------+
    //| Validation and comparison                                        |
    //+------------------------------------------------------------------+
    bool IsEqual(double a, double b, double tolerance = 0.00001) {
        return MathAbs(a - b) <= tolerance;
    }
    
    bool IsZero(double value, double tolerance = 0.00001) {
        return MathAbs(value) <= tolerance;
    }
    
    bool IsPositive(double value, bool includeZero = false) {
        return includeZero ? (value >= 0) : (value > 0);
    }
    
    bool IsNegative(double value, bool includeZero = false) {
        return includeZero ? (value <= 0) : (value < 0);
    }
    
    int Compare(double a, double b, double tolerance = 0.00001) {
        if(MathAbs(a - b) <= tolerance) return 0;
        return (a > b) ? 1 : -1;
    }
    
    //+------------------------------------------------------------------+
    //| Random number generation                                         |
    //+------------------------------------------------------------------+
    double RandomDouble(double min, double max) {
        return min + (MathRand() / 32767.0) * (max - min);
    }
    
    int RandomInteger(int min, int max) {
        return min + (MathRand() % (max - min + 1));
    }
    
    bool RandomBoolean() {
        return (MathRand() % 2) == 0;
    }
    
    //+------------------------------------------------------------------+
    //| Geometric and trigonometric calculations                         |
    //+------------------------------------------------------------------+
    double CalculateDistance(double x1, double y1, double x2, double y2) {
        double dx = x2 - x1;
        double dy = y2 - y1;
        return MathSqrt(dx * dx + dy * dy);
    }
    
    double CalculateSlope(double x1, double y1, double x2, double y2) {
        if(x2 == x1) return DBL_MAX; // Vertical line
        return (y2 - y1) / (x2 - x1);
    }
    
    double CalculateAngle(double x1, double y1, double x2, double y2) {
        double slope = CalculateSlope(x1, y1, x2, y2);
        if(slope == DBL_MAX) return 90; // Vertical line
        return MathArctan(slope) * 180 / M_PI;
    }
};

//+------------------------------------------------------------------+
//| Global math utils instance                                       |
//+------------------------------------------------------------------+
CMathUtils* GlobalMathUtils = NULL;

//+------------------------------------------------------------------+
//| Math utils initialization                                        |
//+------------------------------------------------------------------+
void InitializeGlobalMathUtils() {
    if(GlobalMathUtils == NULL) {
        GlobalMathUtils = new CMathUtils();
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global math utils initialized", "MathUtils");
        }
    }
}

//+------------------------------------------------------------------+
//| Math utils cleanup                                               |
//+------------------------------------------------------------------+
void CleanupGlobalMathUtils() {
    if(GlobalMathUtils != NULL) {
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global math utils cleanup", "MathUtils");
        }
        delete GlobalMathUtils;
        GlobalMathUtils = NULL;
    }
}

#endif