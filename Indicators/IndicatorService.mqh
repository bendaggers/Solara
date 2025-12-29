// Indicators/IndicatorKey.mqh
//+------------------------------------------------------------------+
//| Description: Key generation and parsing for Indicator System     |
//|              Creates unique cache keys like "EURUSD_H4_EMA_50"   |
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
        // Validate inputs
        if(!ValidateSymbolTimeframe(symbol, timeframe))
            return "";
            
        if(period <= 0)
        {
            Print("ERROR: Invalid EMA period: ", period);
            return "";
        }
        
        string methodStr = MA_MethodToString(method);
        string priceStr = AppliedPriceToString(price);
        string tfStr = TimeframeToString(timeframe);
        
        // Create normalized symbol (remove any special characters)
        string normalizedSymbol = NormalizeSymbol(symbol);
        
        return StringFormat("%s_%s_EMA_%d_%s_%s", 
                          normalizedSymbol, 
                          tfStr, 
                          period, 
                          methodStr, 
                          priceStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for ATR indicator                                     |
    //+------------------------------------------------------------------+
    static string CreateATRKey(string symbol, ENUM_TIMEFRAMES timeframe, int period)
    {
        // Validate inputs
        if(!ValidateSymbolTimeframe(symbol, timeframe))
            return "";
            
        if(period <= 0)
        {
            Print("ERROR: Invalid ATR period: ", period);
            return "";
        }
        
        string tfStr = TimeframeToString(timeframe);
        string normalizedSymbol = NormalizeSymbol(symbol);
        
        return StringFormat("%s_%s_ATR_%d", 
                          normalizedSymbol, 
                          tfStr, 
                          period);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for Bollinger Bands indicator                         |
    //+------------------------------------------------------------------+
    static string CreateBBKey(string symbol, ENUM_TIMEFRAMES timeframe, int period, 
                             double deviation, ENUM_APPLIED_PRICE price = PRICE_CLOSE,
                             ENUM_BB_BAND band = BB_MIDDLE)
    {
        // Validate inputs
        if(!ValidateSymbolTimeframe(symbol, timeframe))
            return "";
            
        if(period <= 0)
        {
            Print("ERROR: Invalid BB period: ", period);
            return "";
        }
        
        if(deviation <= 0)
        {
            Print("ERROR: Invalid BB deviation: ", deviation);
            return "";
        }
        
        string bandStr = BB_BandToString(band);
        string priceStr = AppliedPriceToString(price);
        string tfStr = TimeframeToString(timeframe);
        string normalizedSymbol = NormalizeSymbol(symbol);
        
        // Format deviation with 1 decimal place
        string deviationStr = DoubleToString(deviation, 1);
        
        return StringFormat("%s_%s_BB_%d_%s_%s_%s", 
                          normalizedSymbol, 
                          tfStr, 
                          period, 
                          deviationStr, 
                          priceStr, 
                          bandStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for SMA indicator                                     |
    //+------------------------------------------------------------------+
    static string CreateSMAKey(string symbol, ENUM_TIMEFRAMES timeframe, int period,
                              ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        // Validate inputs
        if(!ValidateSymbolTimeframe(symbol, timeframe))
            return "";
            
        if(period <= 0)
        {
            Print("ERROR: Invalid SMA period: ", period);
            return "";
        }
        
        string priceStr = AppliedPriceToString(price);
        string tfStr = TimeframeToString(timeframe);
        string normalizedSymbol = NormalizeSymbol(symbol);
        
        return StringFormat("%s_%s_SMA_%d_%s", 
                          normalizedSymbol, 
                          tfStr, 
                          period, 
                          priceStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for RSI indicator                                     |
    //+------------------------------------------------------------------+
    static string CreateRSIKey(string symbol, ENUM_TIMEFRAMES timeframe, int period,
                              ENUM_APPLIED_PRICE price = PRICE_CLOSE)
    {
        // Validate inputs
        if(!ValidateSymbolTimeframe(symbol, timeframe))
            return "";
            
        if(period <= 0)
        {
            Print("ERROR: Invalid RSI period: ", period);
            return "";
        }
        
        string priceStr = AppliedPriceToString(price);
        string tfStr = TimeframeToString(timeframe);
        string normalizedSymbol = NormalizeSymbol(symbol);
        
        return StringFormat("%s_%s_RSI_%d_%s", 
                          normalizedSymbol, 
                          tfStr, 
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
        // Validate inputs
        if(!ValidateSymbolTimeframe(symbol, timeframe))
            return "";
            
        if(fastEMA <= 0 || slowEMA <= 0 || signalSMA <= 0)
        {
            Print("ERROR: Invalid MACD parameters - Fast: ", fastEMA, 
                  ", Slow: ", slowEMA, ", Signal: ", signalSMA);
            return "";
        }
        
        if(fastEMA >= slowEMA)
        {
            Print("ERROR: MACD fast EMA must be smaller than slow EMA");
            return "";
        }
        
        string priceStr = AppliedPriceToString(price);
        string tfStr = TimeframeToString(timeframe);
        string normalizedSymbol = NormalizeSymbol(symbol);
        
        return StringFormat("%s_%s_MACD_%d_%d_%d_%s", 
                          normalizedSymbol, 
                          tfStr, 
                          fastEMA, 
                          slowEMA, 
                          signalSMA, 
                          priceStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create key for Stochastic indicator                              |
    //+------------------------------------------------------------------+
    static string CreateStochasticKey(string symbol, ENUM_TIMEFRAMES timeframe,
                                     int Kperiod, int Dperiod, int slowing,
                                     ENUM_MA_METHOD maMethod = MODE_SMA,
                                     ENUM_STO_PRICE priceField = STO_LOWHIGH)
    {
        // Validate inputs
        if(!ValidateSymbolTimeframe(symbol, timeframe))
            return "";
            
        if(Kperiod <= 0 || Dperiod <= 0 || slowing <= 0)
        {
            Print("ERROR: Invalid Stochastic parameters");
            return "";
        }
        
        string methodStr = MA_MethodToString(maMethod);
        string priceFieldStr = StochasticPriceFieldToString(priceField);
        string tfStr = TimeframeToString(timeframe);
        string normalizedSymbol = NormalizeSymbol(symbol);
        
        return StringFormat("%s_%s_STOCH_%d_%d_%d_%s_%s", 
                          normalizedSymbol, 
                          tfStr, 
                          Kperiod, 
                          Dperiod, 
                          slowing, 
                          methodStr, 
                          priceFieldStr);
    }
    
    //+------------------------------------------------------------------+
    //| Create generic indicator key                                    |
    //+------------------------------------------------------------------+
    static string CreateKey(string symbol, ENUM_TIMEFRAMES timeframe, 
                           ENUM_INDICATOR_TYPE type, IndicatorParams &params)
    {
        // Validate inputs
        if(!ValidateSymbolTimeframe(symbol, timeframe))
            return "";
            
        switch(type)
        {
            case INDICATOR_EMA:
                return CreateEMAKey(symbol, timeframe, params.period, params.method, params.price);
                
            case INDICATOR_ATR:
                return CreateATRKey(symbol, timeframe, params.period);
                
            case INDICATOR_BB:
                return CreateBBKey(symbol, timeframe, params.period, params.param1, params.price, 
                                 (ENUM_BB_BAND)params.param3);
                
            case INDICATOR_SMA:
                return CreateSMAKey(symbol, timeframe, params.period, params.price);
                
            case INDICATOR_RSI:
                return CreateRSIKey(symbol, timeframe, params.period, params.price);
                
            case INDICATOR_MACD:
                return CreateMACDKey(symbol, timeframe, params.period, 
                                    (int)params.param1, (int)params.param2, params.price);
                
            case INDICATOR_STOCH:
                return CreateStochasticKey(symbol, timeframe, params.period,
                                          (int)params.param1, (int)params.param2,
                                          params.method, (ENUM_STO_PRICE)params.price);
                
            default:
                return CreateCustomKey(symbol, timeframe, type, params);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Create key for custom indicator                                  |
    //+------------------------------------------------------------------+
    static string CreateCustomKey(string symbol, ENUM_TIMEFRAMES timeframe, 
                                 ENUM_INDICATOR_TYPE type, IndicatorParams &params)
    {
        string typeStr = IndicatorTypeToString(type);
        string tfStr = TimeframeToString(timeframe);
        string normalizedSymbol = NormalizeSymbol(symbol);
        
        // Create a safe string representation of the type
        string safeTypeStr = StringReplace(typeStr, " ", "_");
        safeTypeStr = StringReplace(safeTypeStr, "-", "_");
        
        return StringFormat("%s_%s_%s_%d_%.2f_%.2f_%d_%d_%d", 
                          normalizedSymbol, 
                          tfStr, 
                          safeTypeStr, 
                          params.period, 
                          params.param1, 
                          params.param2, 
                          params.param3,
                          params.method,
                          params.price);
    }
    
    //+------------------------------------------------------------------+
    //| Parse key into components                                        |
    //+------------------------------------------------------------------+
    static bool ParseKey(string key, string &symbol, ENUM_TIMEFRAMES &timeframe,
                        ENUM_INDICATOR_TYPE &type, IndicatorParams &params)
    {
        // Reset params
        params = IndicatorParams();
        
        // Validate key format
        if(!IsValidKey(key))
        {
            Print("ERROR: Invalid key format: ", key);
            return false;
        }
        
        // Split key by underscore
        string parts[];
        int count = StringSplit(key, '_', parts);
        
        if(count < 4)
        {
            Print("ERROR: Key has insufficient parts: ", key);
            return false;
        }
        
        // Extract symbol and timeframe
        symbol = parts[0];
        timeframe = StringToTimeframe(parts[1]);
        
        // Validate timeframe
        if(timeframe == PERIOD_CURRENT && parts[1] != "CURRENT")
        {
            Print("ERROR: Invalid timeframe in key: ", parts[1]);
            return false;
        }
        
        // Extract indicator type from position 2
        string typeStr = parts[2];
        type = StringToIndicatorType(typeStr);
        
        if(type == INDICATOR_CUSTOM && typeStr != "CUSTOM")
        {
            Print("WARNING: Unknown indicator type: ", typeStr);
            // Continue parsing as custom
        }
        
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
                
            case INDICATOR_STOCH:
                return ParseStochasticKey(parts, count, params);
                
            default:
                return ParseCustomKey(parts, count, type, params);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Parse EMA key components                                         |
    //+------------------------------------------------------------------+
    static bool ParseEMAKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 6) 
        {
            Print("ERROR: EMA key requires at least 6 parts");
            return false;
        }
        
        params.type = INDICATOR_EMA;
        params.period = (int)StringToInteger(parts[3]);
        params.method = StringToMAMethod(parts[4]);
        params.price = StringToAppliedPrice(parts[5]);
        
        // Validate parsed values
        if(params.period <= 0)
        {
            Print("ERROR: Invalid period in EMA key: ", parts[3]);
            return false;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse ATR key components                                         |
    //+------------------------------------------------------------------+
    static bool ParseATRKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 4) 
        {
            Print("ERROR: ATR key requires at least 4 parts");
            return false;
        }
        
        params.type = INDICATOR_ATR;
        params.period = (int)StringToInteger(parts[3]);
        
        // Validate
        if(params.period <= 0)
        {
            Print("ERROR: Invalid period in ATR key: ", parts[3]);
            return false;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse Bollinger Bands key components                             |
    //+------------------------------------------------------------------+
    static bool ParseBBKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 7) 
        {
            Print("ERROR: BB key requires at least 7 parts");
            return false;
        }
        
        params.type = INDICATOR_BB;
        params.period = (int)StringToInteger(parts[3]);
        params.param1 = StringToDouble(parts[4]);  // Deviation
        params.price = StringToAppliedPrice(parts[5]);
        params.param3 = BB_StringToBand(parts[6]); // Band type
        
        // Validate
        if(params.period <= 0)
        {
            Print("ERROR: Invalid period in BB key: ", parts[3]);
            return false;
        }
        
        if(params.param1 <= 0)
        {
            Print("ERROR: Invalid deviation in BB key: ", parts[4]);
            return false;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse SMA key components                                         |
    //+------------------------------------------------------------------+
    static bool ParseSMAKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 5) 
        {
            Print("ERROR: SMA key requires at least 5 parts");
            return false;
        }
        
        params.type = INDICATOR_SMA;
        params.period = (int)StringToInteger(parts[3]);
        params.price = StringToAppliedPrice(parts[4]);
        params.method = MODE_SMA;
        
        // Validate
        if(params.period <= 0)
        {
            Print("ERROR: Invalid period in SMA key: ", parts[3]);
            return false;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse RSI key components                                         |
    //+------------------------------------------------------------------+
    static bool ParseRSIKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 5) 
        {
            Print("ERROR: RSI key requires at least 5 parts");
            return false;
        }
        
        params.type = INDICATOR_RSI;
        params.period = (int)StringToInteger(parts[3]);
        params.price = StringToAppliedPrice(parts[4]);
        
        // Validate
        if(params.period <= 0)
        {
            Print("ERROR: Invalid period in RSI key: ", parts[3]);
            return false;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse MACD key components                                        |
    //+------------------------------------------------------------------+
    static bool ParseMACDKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 7) 
        {
            Print("ERROR: MACD key requires at least 7 parts");
            return false;
        }
        
        params.type = INDICATOR_MACD;
        params.period = (int)StringToInteger(parts[3]);  // Fast EMA
        params.param1 = StringToInteger(parts[4]);       // Slow EMA
        params.param2 = StringToInteger(parts[5]);       // Signal SMA
        params.price = StringToAppliedPrice(parts[6]);
        
        // Validate
        if(params.period <= 0 || params.param1 <= 0 || params.param2 <= 0)
        {
            Print("ERROR: Invalid MACD parameters in key");
            return false;
        }
        
        if(params.period >= params.param1)
        {
            Print("ERROR: MACD fast EMA must be smaller than slow EMA");
            return false;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse Stochastic key components                                  |
    //+------------------------------------------------------------------+
    static bool ParseStochasticKey(string &parts[], int count, IndicatorParams &params)
    {
        if(count < 8) 
        {
            Print("ERROR: Stochastic key requires at least 8 parts");
            return false;
        }
        
        params.type = INDICATOR_STOCH;
        params.period = (int)StringToInteger(parts[3]);      // K period
        params.param1 = StringToInteger(parts[4]);           // D period
        params.param2 = StringToInteger(parts[5]);           // Slowing
        params.method = StringToMAMethod(parts[6]);          // MA method
        params.price = (ENUM_APPLIED_PRICE)StringToInteger(parts[7]); // Price field
        
        // Validate
        if(params.period <= 0 || params.param1 <= 0 || params.param2 <= 0)
        {
            Print("ERROR: Invalid Stochastic parameters in key");
            return false;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Parse custom key components                                      |
    //+------------------------------------------------------------------+
    static bool ParseCustomKey(string &parts[], int count, ENUM_INDICATOR_TYPE type,
                              IndicatorParams &params)
    {
        if(count < 9) 
        {
            Print("ERROR: Custom key requires at least 9 parts");
            return false;
        }
        
        params.type = type;
        params.period = (int)StringToInteger(parts[3]);
        params.param1 = StringToDouble(parts[4]);
        params.param2 = StringToDouble(parts[5]);
        params.param3 = (int)StringToInteger(parts[6]);
        params.method = (ENUM_MA_METHOD)StringToInteger(parts[7]);
        params.price = (ENUM_APPLIED_PRICE)StringToInteger(parts[8]);
        
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
        
        // Validate shift is reasonable
        if(shift < 0 || shift > 1000)
        {
            Print("WARNING: Unusual shift value: ", shift);
        }
        
        return baseKey + StringFormat("_S%d", shift);
    }
    
    //+------------------------------------------------------------------+
    //| Remove shift from key                                            |
    //+------------------------------------------------------------------+
    static string RemoveShiftFromKey(string key)
    {
        int pos = StringFind(key, "_S");
        if(pos == -1) return key;
        
        // Check if what follows "_S" is actually a number
        string afterS = StringSubstr(key, pos + 2);
        if(StringLen(afterS) == 0) return key;
        
        // Check if all characters after "_S" are digits
        for(int i = 0; i < StringLen(afterS); i++)
        {
            if(afterS[i] < '0' || afterS[i] > '9')
                return key; // Not a valid shift suffix
        }
        
        return StringSubstr(key, 0, pos);
    }
    
    //+------------------------------------------------------------------+
    //| Check if key has valid format                                    |
    //+------------------------------------------------------------------+
    static bool IsValidKey(string key)
    {
        if(StringLen(key) < 5) 
        {
            Print("DEBUG: Key too short: ", key);
            return false;
        }
        
        if(StringFind(key, "_") == -1)
        {
            Print("DEBUG: Key missing underscore separator: ", key);
            return false;
        }
        
        // Check for minimum components (Symbol_TF_Type)
        string parts[];
        int count = StringSplit(key, '_', parts);
        
        if(count < 3)
        {
            Print("DEBUG: Key has insufficient parts: ", key);
            return false;
        }
        
        // Validate symbol format (should be like EURUSD, GBPUSD, etc.)
        string symbol = parts[0];
        if(StringLen(symbol) < 3 || StringLen(symbol) > 12)
        {
            Print("DEBUG: Invalid symbol in key: ", symbol);
            return false;
        }
        
        // Validate timeframe (should be valid timeframe string)
        string tfStr = parts[1];
        if(StringToTimeframe(tfStr) == PERIOD_CURRENT && tfStr != "CURRENT")
        {
            Print("DEBUG: Invalid timeframe in key: ", tfStr);
            return false;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Get indicator type from key                                      |
    //+------------------------------------------------------------------+
    static ENUM_INDICATOR_TYPE GetTypeFromKey(string key)
    {
        if(!IsValidKey(key))
            return INDICATOR_CUSTOM;
        
        string parts[];
        int count = StringSplit(key, '_', parts);
        
        if(count < 3)
            return INDICATOR_CUSTOM;
        
        string typeStr = parts[2];
        return StringToIndicatorType(typeStr);
    }
    
    //+------------------------------------------------------------------+
    //| Get symbol from key                                              |
    //+------------------------------------------------------------------+
    static string GetSymbolFromKey(string key)
    {
        if(!IsValidKey(key))
            return "";
        
        string parts[];
        int count = StringSplit(key, '_', parts);
        
        if(count < 1)
            return "";
        
        return parts[0];
    }
    
    //+------------------------------------------------------------------+
    //| Get timeframe from key                                           |
    //+------------------------------------------------------------------+
    static ENUM_TIMEFRAMES GetTimeframeFromKey(string key)
    {
        if(!IsValidKey(key))
            return PERIOD_CURRENT;
        
        string parts[];
        int count = StringSplit(key, '_', parts);
        
        if(count < 2)
            return PERIOD_CURRENT;
        
        return StringToTimeframe(parts[1]);
    }
    
    //+------------------------------------------------------------------+
    //| Get period from key                                              |
    //+------------------------------------------------------------------+
    static int GetPeriodFromKey(string key)
    {
        if(!IsValidKey(key))
            return 0;
        
        string parts[];
        int count = StringSplit(key, '_', parts);
        
        if(count < 4)
            return 0;
        
        // Try to parse period from the likely position
        return (int)StringToInteger(parts[3]);
    }
    
    //+------------------------------------------------------------------+
    //| Get key for specific bar shift                                   |
    //+------------------------------------------------------------------+
    static string GetKeyForShift(string symbol, ENUM_TIMEFRAMES timeframe,
                                ENUM_INDICATOR_TYPE type, IndicatorParams &params, int shift = 0)
    {
        string baseKey = CreateKey(symbol, timeframe, type, params);
        
        if(baseKey == "") return "";
        
        if(shift == 0) 
            return baseKey;
        else
            return AddShiftToKey(baseKey, shift);
    }
    
    //+------------------------------------------------------------------+
    //| Normalize symbol name (remove invalid characters)                |
    //+------------------------------------------------------------------+
    static string NormalizeSymbol(string symbol)
    {
        // Remove any characters that could cause issues in keys
        string result = symbol;
        
        // Replace spaces with underscores
        result = StringReplace(result, " ", "_");
        
        // Remove any other problematic characters
        string invalidChars = "\\/*?\"<>|";
        for(int i = 0; i < StringLen(invalidChars); i++)
        {
            string charStr = StringSubstr(invalidChars, i, 1);
            result = StringReplace(result, charStr, "");
        }
        
        return result;
    }
    
    //+------------------------------------------------------------------+
    //| Validate symbol and timeframe                                    |
    //+------------------------------------------------------------------+
    static bool ValidateSymbolTimeframe(string symbol, ENUM_TIMEFRAMES timeframe)
    {
        if(StringLen(symbol) == 0)
        {
            Print("ERROR: Empty symbol");
            return false;
        }
        
        // Check if symbol exists (basic check)
        if(StringFind(symbol, " ") != -1)
        {
            Print("WARNING: Symbol contains spaces: '", symbol, "'");
        }
        
        // Validate timeframe
        if(timeframe == PERIOD_CURRENT)
        {
            Print("WARNING: Using PERIOD_CURRENT in cache key - may cause issues");
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert timeframe to string                              |
    //+------------------------------------------------------------------+
    static string TimeframeToString(ENUM_TIMEFRAMES tf)
    {
        switch(tf)
        {
            case PERIOD_M1:   return "M1";
            case PERIOD_M2:   return "M2";
            case PERIOD_M3:   return "M3";
            case PERIOD_M4:   return "M4";
            case PERIOD_M5:   return "M5";
            case PERIOD_M6:   return "M6";
            case PERIOD_M10:  return "M10";
            case PERIOD_M12:  return "M12";
            case PERIOD_M15:  return "M15";
            case PERIOD_M20:  return "M20";
            case PERIOD_M30:  return "M30";
            case PERIOD_H1:   return "H1";
            case PERIOD_H2:   return "H2";
            case PERIOD_H3:   return "H3";
            case PERIOD_H4:   return "H4";
            case PERIOD_H6:   return "H6";
            case PERIOD_H8:   return "H8";
            case PERIOD_H12:  return "H12";
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
        if(tfStr == "M2")     return PERIOD_M2;
        if(tfStr == "M3")     return PERIOD_M3;
        if(tfStr == "M4")     return PERIOD_M4;
        if(tfStr == "M5")     return PERIOD_M5;
        if(tfStr == "M6")     return PERIOD_M6;
        if(tfStr == "M10")    return PERIOD_M10;
        if(tfStr == "M12")    return PERIOD_M12;
        if(tfStr == "M15")    return PERIOD_M15;
        if(tfStr == "M20")    return PERIOD_M20;
        if(tfStr == "M30")    return PERIOD_M30;
        if(tfStr == "H1")     return PERIOD_H1;
        if(tfStr == "H2")     return PERIOD_H2;
        if(tfStr == "H3")     return PERIOD_H3;
        if(tfStr == "H4")     return PERIOD_H4;
        if(tfStr == "H6")     return PERIOD_H6;
        if(tfStr == "H8")     return PERIOD_H8;
        if(tfStr == "H12")    return PERIOD_H12;
        if(tfStr == "D1")     return PERIOD_D1;
        if(tfStr == "W1")     return PERIOD_W1;
        if(tfStr == "MN1")    return PERIOD_MN1;
        if(tfStr == "CURRENT") return PERIOD_CURRENT;
        
        Print("WARNING: Unknown timeframe string: ", tfStr);
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
            default:           
                Print("WARNING: Unknown MA method: ", method);
                return "SMA";
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
        
        Print("WARNING: Unknown MA method string: ", methodStr);
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
            default:              
                Print("WARNING: Unknown applied price: ", price);
                return "CLOSE";
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
        
        Print("WARNING: Unknown applied price string: ", priceStr);
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
            default:         
                Print("WARNING: Unknown BB band: ", band);
                return "MIDDLE";
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
        
        Print("WARNING: Unknown BB band string: ", bandStr);
        return BB_MIDDLE;
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert Stochastic price field to string                 |
    //+------------------------------------------------------------------+
    static string StochasticPriceFieldToString(ENUM_STO_PRICE priceField)
    {
        switch(priceField)
        {
            case STO_LOWHIGH:    return "LOWHIGH";
            case STO_CLOSECLOSE: return "CLOSECLOSE";
            default:             
                Print("WARNING: Unknown Stochastic price field: ", priceField);
                return "LOWHIGH";
        }
    }
    
    //+------------------------------------------------------------------+
    //| Helper: Convert string to Stochastic price field                 |
    //+------------------------------------------------------------------+
    static int StringToStochasticPriceField(string priceFieldStr)
    {
        if(priceFieldStr == "LOWHIGH")    return STO_LOWHIGH;
        if(priceFieldStr == "CLOSECLOSE") return STO_CLOSECLOSE;
        
        Print("WARNING: Unknown Stochastic price field string: ", priceFieldStr);
        return STO_LOWHIGH;
    }
    
    //+------------------------------------------------------------------+
    //| Generate test keys for validation                                |
    //+------------------------------------------------------------------+
    static void TestKeyGeneration()
    {
        Print("=== Testing Key Generation and Parsing ===");
        
        // Test 1: EMA Key
        string emaKey = CreateEMAKey("EURUSD", PERIOD_H4, 50, MODE_EMA, PRICE_CLOSE);
        Print("1. EMA Key: ", emaKey);
        
        string symbol;
        ENUM_TIMEFRAMES tf;
        ENUM_INDICATOR_TYPE type;
        IndicatorParams params;
        
        if(ParseKey(emaKey, symbol, tf, type, params))
        {
            Print("   Parsed: ", symbol, " ", TimeframeToString(tf), 
                  " EMA(", params.period, ") ", 
                  MA_MethodToString(params.method), " ", AppliedPriceToString(params.price));
        }
        
        // Test 2: ATR Key
        string atrKey = CreateATRKey("GBPUSD", PERIOD_D1, 14);
        Print("2. ATR Key: ", atrKey);
        
        if(ParseKey(atrKey, symbol, tf, type, params))
        {
            Print("   Parsed: ", symbol, " ", TimeframeToString(tf), 
                  " ATR(", params.period, ")");
        }
        
        // Test 3: BB Key
        string bbKey = CreateBBKey("USDJPY", PERIOD_H1, 20, 2.0, PRICE_CLOSE, BB_LOWER);
        Print("3. BB Key: ", bbKey);
        
        if(ParseKey(bbKey, symbol, tf, type, params))
        {
            Print("   Parsed: ", symbol, " ", TimeframeToString(tf), 
                  " BB(", params.period, ", ", params.param1, ") ", 
                  AppliedPriceToString(params.price), " ", BB_BandToString((ENUM_BB_BAND)params.