// Indicators/IndicatorKey.mqh
//+------------------------------------------------------------------+
//| Description: Key generation and parsing for Indicator System     |
//+------------------------------------------------------------------+
#ifndef INDICATORKEY_MQH
#define INDICATORKEY_MQH

#include "IndicatorTypes.mqh"

//+------------------------------------------------------------------+
//| Indicator Key Class                                              |
//+------------------------------------------------------------------+
class CIndicatorKey
{
public:
    //+------------------------------------------------------------------+
    //| Create key for EMA indicator                                     |
    //+------------------------------------------------------------------+
    static string CreateEMAKey(string symbol, ENUM_TIMEFRAMES timeframe, int period, 
                              ENUM_MA_METHOD method = MODE_EMA, ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        string methodStr = MA_MethodToString(method);
        string priceStr = AppliedPriceToString(price);
        
        return StringFormat("%s_%s_EMA_%d_%s_%s", 
                          symbol, 
                          TimeframeToString(timeframe), 
                          period, 
                          methodStr, 
                          priceStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for ATR indicator                                     |
    //+------------------------------------------------------------------+
    static string CreateATRKey(string symbol, ENUM_TIMEFRAMES timeframe, int period)
    {
        return StringFormat("%s_%s_ATR_%d", 
                          symbol, 
                          TimeframeToString(timeframe), 
                          period);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for Bollinger Bands indicator                         |
    //+------------------------------------------------------------------+
    static string CreateBBKey(string symbol, ENUM_TIMEFRAMES timeframe, int period, 
                             double deviation, ENUM_APPLIED_PRICE price = PRICE_CLOSE,
                             ENUM_BB_BAND band = BB_MIDDLE)
    {
        string bandStr = BB_BandToString(band);
        string priceStr = AppliedPriceToString(price);
        
        return StringFormat("%s_%s_BB_%d_%.1f_%s_%s", 
                          symbol, 
                          TimeframeToString(timeframe), 
                          period, 
                          deviation, 
                          priceStr, 
                          bandStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for SMA indicator                                     |
    //+------------------------------------------------------------------+
    static string CreateSMAKey(string symbol, ENUM_TIMEFRAMES timeframe, int period,
                              ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        string priceStr = AppliedPriceToString(price);
        
        return StringFormat("%s_%s_SMA_%d_%s", 
                          symbol, 
                          TimeframeToString(timeframe), 
                          period, 
                          priceStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create generic indicator key                                    |
    //+------------------------------------------------------------------+
    static string CreateKey(string symbol, ENUM_TIMEFRAMES timeframe, 
                           ENUM_INDICATOR_TYPE type, IndicatorParams &params)
    {
        switch(type)
        {
            case INDICATOR_EMA:
                return CreateEMAKey(symbol, timeframe, params.period, params.method, params.price);
                
            case INDICATOR_ATR:
                return CreateATRKey(symbol, timeframe, params.period);
                
            case INDICATOR_BB:
                return CreateBBKey(symbol, timeframe, params.period, params.param1, params.price);
                
            case INDICATOR_SMA:
                return CreateSMAKey(symbol, timeframe, params.period, params.price);
                
            case INDICATOR_RSI:
                return CreateRSIKey(symbol, timeframe, params.period, params.price);
                
            case INDICATOR_MACD:
                return CreateMACDKey(symbol, timeframe, params.period, (int)params.param1, 
                                    (int)params.param2, params.price);
                
            default:
                return CreateCustomKey(symbol, timeframe, type, params);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Create key for RSI indicator                                     |
    //+------------------------------------------------------------------+
    static string CreateRSIKey(string symbol, ENUM_TIMEFRAMES timeframe, int period,
                              ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        string priceStr = AppliedPriceToString(price);
        
        return StringFormat("%s_%s_RSI_%d_%s", 
                          symbol, 
                          TimeframeToString(timeframe), 
                          period, 
                          priceStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for MACD indicator                                    |
    //+------------------------------------------------------------------+
    static string CreateMACDKey(string symbol, ENUM_TIMEFRAMES timeframe, 
                               int fastEMA, int slowEMA, int signalSMA,
                               ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        string priceStr = AppliedPriceToString(price);
        
        return StringFormat("%s_%s_MACD_%d_%d_%d_%s", 
                          symbol, 
                          TimeframeToString(timeframe), 
                          fastEMA, 
                          slowEMA, 
                          signalSMA, 
                          priceStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for custom indicator                                  |
    //+------------------------------------------------------------------+
    static string CreateCustomKey(string symbol, ENUM_TIMEFRAMES timeframe, 
                                 ENUM_INDICATOR_TYPE type, IndicatorParams &params)
    {
        string typeStr = IndicatorTypeToString(type);
        
        return StringFormat("%s_%s_%s_%d_%.2f_%.2f_%d", 
                          symbol, 
                          TimeframeToString(timeframe), 
                          typeStr, 
                          params.period, 
                          params.param1, 
                          params.param2, 
                          params.param3);
    }
    
    //+------------------------------------------------------------------+
    //| Parse key into components                                        |
    //+------------------------------------------------------------------+
    static bool ParseKey(string key, string &symbol, ENUM_TIMEFRAMES &timeframe,
                        ENUM_INDICATOR_TYPE &type, IndicatorParams &params)
    {
        // Reset params
        params = IndicatorParams();
        
        // Split key by underscore
        string parts[];
        int count = StringSplit(key, '_', parts);
        
        if(count < 4)
        {
            Print("ERROR: Invalid key format: ", key);
            return false;
        }
        
        // Extract symbol and timeframe
        symbol = parts[0];
        timeframe = StringToTimeframe(parts[1]);
        
        // Extract indicator type
        string typeStr = parts[2];
        type = StringToIndicatorType(typeStr);
        
        // Parse based on indicator type
        switch(type)
        {
            case INDICATOR_EMA:
                return ParseEMAKey(parts, count, params);
                
            case INDICATOR_ATR:
                return ParseATRKey(parts, count, params);
                
            case INDICATOR_BB:
                return ParseBBKey(parts, count, params);
                
            case INDICATOR_SMA:
                return ParseSMAKey(parts, count, params);
                
            case INDICATOR_RSI:
                return ParseRSIKey(parts, count, params);
                
            case INDICATOR_MACD:
                return ParseMACDKey(parts, count, params);
                
            default:
                return ParseCustomKey(parts, count, type, params);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Parse EMA key components                                         |
    //+------------------------------------------------------------------+
    static bool ParseEMAKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 6) return false;
        
        params.type = INDICATOR_EMA;
        params.period = (int)StringToInteger(parts[3]);
        params.method = StringToMAMethod(parts[4]);
        params.price = StringToAppliedPrice(parts[5]);
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse ATR key components                                         |
    //+------------------------------------------------------------------+
    static bool ParseATRKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 4) return false;
        
        params.type = INDICATOR_ATR;
        params.period = (int)StringToInteger(parts[3]);
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse Bollinger Bands key components                             |
    //+------------------------------------------------------------------+
    static bool ParseBBKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 7) return false;
        
        params.type = INDICATOR_BB;
        params.period = (int)StringToInteger(parts[3]);
        params.param1 = StringToDouble(parts[4]);  // Deviation
        params.price = StringToAppliedPrice(parts[5]);
        // Note: Band type (parts[6]) is stored in param3
        params.param3 = BB_StringToBand(parts[6]);
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse SMA key components                                         |
    //+------------------------------------------------------------------+
    static bool ParseSMAKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 5) return false;
        
        params.type = INDICATOR_SMA;
        params.period = (int)StringToInteger(parts[3]);
        params.price = StringToAppliedPrice(parts[4]);
        params.method = MODE_SMA;
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse RSI key components                                         |
    //+------------------------------------------------------------------+
    static bool ParseRSIKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 5) return false;
        
        params.type = INDICATOR_RSI;
        params.period = (int)StringToInteger(parts[3]);
        params.price = StringToAppliedPrice(parts[4]);
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse MACD key components                                        |
    //+------------------------------------------------------------------+
    static bool ParseMACDKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 7) return false;
        
        params.type = INDICATOR_MACD;
        params.period = (int)StringToInteger(parts[3]);  // Fast EMA
        params.param1 = StringToInteger(parts[4]);       // Slow EMA
        params.param2 = StringToInteger(parts[5]);       // Signal SMA
        params.price = StringToAppliedPrice(parts[6]);
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse custom key components                                      |
    //+------------------------------------------------------------------+
    static bool ParseCustomKey(string &parts[], int count, ENUM_INDICATOR_TYPE type,
                              IndicatorParams &params)
    {
        if(count < 8) return false;
        
        params.type = type;
        params.period = (int)StringToInteger(parts[3]);
        params.param1 = StringToDouble(parts[4]);
        params.param2 = StringToDouble(parts[5]);
        params.param3 = (int)StringToInteger(parts[6]);
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Extract shift from key (if present)                              |
    //+------------------------------------------------------------------+
    static int ExtractShiftFromKey(string key)
    {
        // Check if key contains shift suffix like "_S1"
        int pos = StringFind(key, "_S");
        if(pos == -1) return 0;
        
        string shiftStr = StringSubstr(key, pos + 2);
        return (int)StringToInteger(shiftStr);
    }
    
    //+------------------------------------------------------------------+
    //| Add shift to key                                                 |
    //+------------------------------------------------------------------+
    static string AddShiftToKey(string baseKey, int shift)
    {
        if(shift == 0) return baseKey;
        return baseKey + StringFormat("_S%d", shift);
    }
    
    //+------------------------------------------------------------------+
    //| Remove shift from key                                            |
    //+------------------------------------------------------------------+
    static string RemoveShiftFromKey(string key)
    {
        int pos = StringFind(key, "_S");
        if(pos == -1) return key;
        
        return StringSubstr(key, 0, pos);
    }
    
    //+------------------------------------------------------------------+
    //| Check if key has valid format                                    |
    //+------------------------------------------------------------------+
    static bool IsValidKey(string key)
    {
        if(StringLen(key) < 5) return false;
        if(StringFind(key, "_") == -1) return false;
        
        // Check for minimum components
        string parts[];
        int count = StringSplit(key, '_', parts);
        return (count >= 4);
    }
    
    //+------------------------------------------------------------------+
    //| Get indicator type from key                                      |
    //+------------------------------------------------------------------+
    static ENUM_INDICATOR_TYPE GetTypeFromKey(string key)
    {
        int pos1 = StringFind(key, "_");
        if(pos1 == -1) return INDICATOR_CUSTOM;
        
        int pos2 = StringFind(key, "_", pos1 + 1);
        if(pos2 == -1) return INDICATOR_CUSTOM;
        
        string typeStr = StringSubstr(key, pos1 + 1, pos2 - pos1 - 1);
        
        // Find second underscore for type
        int pos3 = StringFind(key, "_", pos2 + 1);
        if(pos3 == -1) return INDICATOR_CUSTOM;
        
        typeStr = StringSubstr(key, pos2 + 1, pos3 - pos2 - 1);
        
        return StringToIndicatorType(typeStr);
    }
    
    //+------------------------------------------------------------------+
    //| Get symbol from key                                              |
    //+------------------------------------------------------------------+
    static string GetSymbolFromKey(string key)
    {
        int pos = StringFind(key, "_");
        if(pos == -1) return "";
        
        return StringSubstr(key, 0, pos);
    }
    
    //+------------------------------------------------------------------+
    //| Get timeframe from key                                           |
    //+------------------------------------------------------------------+
    static ENUM_TIMEFRAMES GetTimeframeFromKey(string key)
    {
        int pos1 = StringFind(key, "_");
        if(pos1 == -1) return PERIOD_CURRENT;
        
        int pos2 = StringFind(key, "_", pos1 + 1);
        if(pos2 == -1) return PERIOD_CURRENT;
        
        string tfStr = StringSubstr(key, pos1 + 1, pos2 - pos1 - 1);
        return StringToTimeframe(tfStr);
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert timeframe to string                              |
    //+------------------------------------------------------------------+
    static string TimeframeToString(ENUM_TIMEFRAMES tf)
    {
        switch(tf)
        {
            case PERIOD_M1:   return "M1";
            case PERIOD_M5:   return "M5";
            case PERIOD_M15:  return "M15";
            case PERIOD_M30:  return "M30";
            case PERIOD_H1:   return "H1";
            case PERIOD_H4:   return "H4";
            case PERIOD_D1:   return "D1";
            case PERIOD_W1:   return "W1";
            case PERIOD_MN1:  return "MN1";
            default:          return "CURRENT";
        }
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert string to timeframe                              |
    //+------------------------------------------------------------------+
    static ENUM_TIMEFRAMES StringToTimeframe(string tfStr)
    {
        if(tfStr == "M1")     return PERIOD_M1;
        if(tfStr == "M5")     return PERIOD_M5;
        if(tfStr == "M15")    return PERIOD_M15;
        if(tfStr == "M30")    return PERIOD_M30;
        if(tfStr == "H1")     return PERIOD_H1;
        if(tfStr == "H4")     return PERIOD_H4;
        if(tfStr == "D1")     return PERIOD_D1;
        if(tfStr == "W1")     return PERIOD_W1;
        if(tfStr == "MN1")    return PERIOD_MN1;
        
        return PERIOD_CURRENT;
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert MA method to string                              |
    //+------------------------------------------------------------------+
    static string MA_MethodToString(ENUM_MA_METHOD method)
    {
        switch(method)
        {
            case MODE_SMA:     return "SMA";
            case MODE_EMA:     return "EMA";
            case MODE_SMMA:    return "SMMA";
            case MODE_LWMA:    return "LWMA";
            default:           return "SMA";
        }
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert string to MA method                              |
    //+------------------------------------------------------------------+
    static ENUM_MA_METHOD StringToMAMethod(string methodStr)
    {
        if(methodStr == "SMA")     return MODE_SMA;
        if(methodStr == "EMA")     return MODE_EMA;
        if(methodStr == "SMMA")    return MODE_SMMA;
        if(methodStr == "LWMA")    return MODE_LWMA;
        
        return MODE_SMA;
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert applied price to string                          |
    //+------------------------------------------------------------------+
    static string AppliedPriceToString(ENUM_APPLIED_PRICE price)
    {
        switch(price)
        {
            case PRICE_CLOSE:     return "CLOSE";
            case PRICE_OPEN:      return "OPEN";
            case PRICE_HIGH:      return "HIGH";
            case PRICE_LOW:       return "LOW";
            case PRICE_MEDIAN:    return "MEDIAN";
            case PRICE_TYPICAL:   return "TYPICAL";
            case PRICE_WEIGHTED:  return "WEIGHTED";
            default:              return "CLOSE";
        }
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert string to applied price                          |
    //+------------------------------------------------------------------+
    static ENUM_APPLIED_PRICE StringToAppliedPrice(string priceStr)
    {
        if(priceStr == "CLOSE")     return PRICE_CLOSE;
        if(priceStr == "OPEN")      return PRICE_OPEN;
        if(priceStr == "HIGH")      return PRICE_HIGH;
        if(priceStr == "LOW")       return PRICE_LOW;
        if(priceStr == "MEDIAN")    return PRICE_MEDIAN;
        if(priceStr == "TYPICAL")   return PRICE_TYPICAL;
        if(priceStr == "WEIGHTED")  return PRICE_WEIGHTED;
        
        return PRICE_CLOSE;
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert BB band to string                                |
    //+------------------------------------------------------------------+
    static string BB_BandToString(ENUM_BB_BAND band)
    {
        switch(band)
        {
            case BB_UPPER:   return "UPPER";
            case BB_MIDDLE:  return "MIDDLE";
            case BB_LOWER:   return "LOWER";
            default:         return "MIDDLE";
        }
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert string to BB band                                |
    //+------------------------------------------------------------------+
    static int BB_StringToBand(string bandStr)
    {
        if(bandStr == "UPPER")   return BB_UPPER;
        if(bandStr == "MIDDLE")  return BB_MIDDLE;
        if(bandStr == "LOWER")   return BB_LOWER;
        
        return BB_MIDDLE;
    }
    
    //+------------------------------------------------------------------+
    //| Get key for specific bar shift                                   |
    //+------------------------------------------------------------------+
    static string GetKeyForShift(string symbol, ENUM_TIMEFRAMES timeframe,
                                ENUM_INDICATOR_TYPE type, IndicatorParams &params, int shift = 0)
    {
        string baseKey = CreateKey(symbol, timeframe, type, params);
        
        if(shift == 0) 
            return baseKey;
        else
            return AddShiftToKey(baseKey, shift);
    }
    
    //+------------------------------------------------------------------+
    //| Generate test keys for validation                                |
    //+------------------------------------------------------------------+
    static void TestKeyGeneration()
    {
        Print("=== Testing Key Generation ===");
        
        // Test EMA key
        string emaKey = CreateEMAKey("EURUSD", PERIOD_H4, 50, MODE_EMA, PRICE_CLOSE);
        Print("EMA Key: ", emaKey);
        
        // Test ATR key
        string atrKey = CreateATRKey("EURUSD", PERIOD_H4, 14);
        Print("ATR Key: ", atrKey);
        
        // Test BB key
        string bbKey = CreateBBKey("EURUSD", PERIOD_H4, 20, 2.0, PRICE_CLOSE, BB_LOWER);
        Print("BB Key: ", bbKey);
        
        // Test parsing
        string symbol;
        ENUM_TIMEFRAMES tf;
        ENUM_INDICATOR_TYPE type;
        IndicatorParams params;
        
        if(ParseKey(emaKey, symbol, tf, type, params))
        {
            Print("Parsed EMA: ", symbol, " ", TimeframeToString(tf), 
                  " Period: ", params.period, " Type: ", IndicatorTypeToString(type));
        }
        
        Print("=== Key Generation Test Complete ===");
    }
};

#endif // INDICATORKEY_MQH