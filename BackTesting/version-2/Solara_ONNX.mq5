//+------------------------------------------------------------------+
//|                                                 Solara_ONNX.mq5   |
//|                                    Solara ML Trading System       |
//|                                    SHORT-only Entry Model         |
//+------------------------------------------------------------------+
#property copyright "Solara Trading System"
#property version   "1.00"
#property description "ML-based SHORT entry filter using ONNX model"

//--- Include model constants (auto-generated)
#include <SolaraModelConstants.mqh>

//--- Input parameters
input group "=== Model Settings ==="
input string   InpModelPath = "solara_model.onnx";    // ONNX Model Path (in MQL5/Files/)
input double   InpProbThreshold = PROBABILITY_THRESHOLD; // Probability Threshold

input group "=== Signal Settings ==="
input double   InpBBThreshold = BB_THRESHOLD;          // BB Position Threshold
input int      InpRSIThreshold = RSI_THRESHOLD;        // RSI Threshold
input int      InpRSIPeriod = 14;                      // RSI Period
input int      InpBBPeriod = 20;                       // Bollinger Period
input double   InpBBDeviation = 2.0;                   // Bollinger Deviation

input group "=== Trade Settings ==="
input int      InpTPPips = TP_PIPS;                    // Take Profit (pips)
input int      InpSLPips = SL_PIPS;                    // Stop Loss (pips)
input int      InpMaxHoldingBars = MAX_HOLDING_BARS;   // Max Holding Bars
input double   InpLotSize = 0.01;                      // Lot Size
input int      InpMagicNumber = 12345;                 // Magic Number

input group "=== Display Settings ==="
input bool     InpShowPanel = true;                    // Show Info Panel
input color    InpPanelColor = clrDarkSlateGray;       // Panel Background

//--- ONNX handle
long onnx_handle = INVALID_HANDLE;

//--- Indicator handles
int rsi_handle = INVALID_HANDLE;
int bb_handle = INVALID_HANDLE;
int atr_handle = INVALID_HANDLE;

//--- Feature array (must match MODEL_FEATURES)
float features[];

//--- Global variables
double current_probability = 0.0;
bool signal_triggered = false;
string last_signal_time = "";

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    //--- Initialize feature array
    ArrayResize(features, MODEL_FEATURES);
    ArrayInitialize(features, 0.0);
    
    //--- Load ONNX model
    string model_path = InpModelPath;
    onnx_handle = OnnxCreate(model_path, ONNX_DEFAULT);
    
    if(onnx_handle == INVALID_HANDLE)
    {
        Print("❌ Failed to load ONNX model: ", model_path);
        Print("   Make sure the file is in MQL5/Files/ folder");
        return INIT_FAILED;
    }
    
    //--- Set input shape
    ulong input_shape[] = {1, MODEL_FEATURES};
    if(!OnnxSetInputShape(onnx_handle, 0, input_shape))
    {
        Print("❌ Failed to set ONNX input shape");
        return INIT_FAILED;
    }
    
    Print("✅ ONNX model loaded successfully");
    Print("   Features: ", MODEL_FEATURES);
    Print("   Probability threshold: ", InpProbThreshold);
    
    //--- Initialize indicators
    rsi_handle = iRSI(_Symbol, PERIOD_CURRENT, InpRSIPeriod, PRICE_CLOSE);
    bb_handle = iBands(_Symbol, PERIOD_CURRENT, InpBBPeriod, 0, InpBBDeviation, PRICE_CLOSE);
    atr_handle = iATR(_Symbol, PERIOD_CURRENT, 14);
    
    if(rsi_handle == INVALID_HANDLE || bb_handle == INVALID_HANDLE || atr_handle == INVALID_HANDLE)
    {
        Print("❌ Failed to initialize indicators");
        return INIT_FAILED;
    }
    
    //--- Create info panel
    if(InpShowPanel)
        CreatePanel();
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    //--- Release ONNX model
    if(onnx_handle != INVALID_HANDLE)
    {
        OnnxRelease(onnx_handle);
        onnx_handle = INVALID_HANDLE;
    }
    
    //--- Release indicators
    if(rsi_handle != INVALID_HANDLE) IndicatorRelease(rsi_handle);
    if(bb_handle != INVALID_HANDLE) IndicatorRelease(bb_handle);
    if(atr_handle != INVALID_HANDLE) IndicatorRelease(atr_handle);
    
    //--- Remove panel
    ObjectsDeleteAll(0, "Solara_");
}

//+------------------------------------------------------------------+
//| Expert tick function                                               |
//+------------------------------------------------------------------+
void OnTick()
{
    //--- Check for new bar
    static datetime last_bar_time = 0;
    datetime current_bar_time = iTime(_Symbol, PERIOD_CURRENT, 0);
    
    if(current_bar_time == last_bar_time)
        return; // Same bar, skip
    
    last_bar_time = current_bar_time;
    
    //--- Calculate features
    if(!CalculateFeatures())
    {
        if(InpShowPanel) UpdatePanel("Error calculating features", 0, false);
        return;
    }
    
    //--- Check signal conditions (BB + RSI)
    double bb_position = GetBBPosition();
    double rsi_value = GetRSI();
    
    signal_triggered = (bb_position >= InpBBThreshold && rsi_value >= InpRSIThreshold);
    
    if(!signal_triggered)
    {
        current_probability = 0.0;
        if(InpShowPanel) UpdatePanel("No signal", 0, false);
        return;
    }
    
    //--- Run ONNX inference
    current_probability = PredictProbability();
    
    //--- Check if probability exceeds threshold
    if(current_probability >= InpProbThreshold)
    {
        //--- Check if we can open a trade
        if(CanOpenTrade())
        {
            OpenShortTrade();
            last_signal_time = TimeToString(TimeCurrent());
        }
    }
    
    //--- Update panel
    if(InpShowPanel)
        UpdatePanel(signal_triggered ? "Signal!" : "Waiting", current_probability, signal_triggered);
}

//+------------------------------------------------------------------+
//| Calculate all features for the model                              |
//+------------------------------------------------------------------+
bool CalculateFeatures()
{
    //--- Get indicator values
    double rsi[], bb_upper[], bb_lower[], bb_middle[], atr[];
    
    if(CopyBuffer(rsi_handle, 0, 1, 10, rsi) <= 0) return false;
    if(CopyBuffer(bb_handle, 1, 1, 10, bb_upper) <= 0) return false;  // Upper band
    if(CopyBuffer(bb_handle, 2, 1, 10, bb_lower) <= 0) return false;  // Lower band
    if(CopyBuffer(bb_handle, 0, 1, 10, bb_middle) <= 0) return false; // Middle band
    if(CopyBuffer(atr_handle, 0, 1, 10, atr) <= 0) return false;
    
    //--- Get price data
    double close = iClose(_Symbol, PERIOD_CURRENT, 1);
    double high = iHigh(_Symbol, PERIOD_CURRENT, 1);
    double low = iLow(_Symbol, PERIOD_CURRENT, 1);
    double volume = (double)iVolume(_Symbol, PERIOD_CURRENT, 1);
    
    //--- Calculate features (ORDER MUST MATCH feature_names from training!)
    //--- Check your SolaraModelConstants.mqh for exact order
    
    int idx = 0;
    
    // Feature: bb_width_pct
    double bb_width = bb_upper[0] - bb_lower[0];
    features[idx++] = (float)(bb_width / bb_middle[0]);
    
    // Feature: trend_strength (simplified - use ADX if available)
    double price_change = MathAbs(close - iClose(_Symbol, PERIOD_CURRENT, 11));
    double avg_change = atr[0] * 10;
    features[idx++] = (float)MathMin(price_change / avg_change, 1.0);
    
    // Feature: time_since_last_touch
    features[idx++] = (float)GetTimeSinceLastTouch(bb_upper[0]);
    
    // Feature: rsi_value
    features[idx++] = (float)(rsi[0] / 100.0); // Normalize to 0-1
    
    // Feature: volume_ratio
    double volume_sma = GetVolumeSMA(20);
    features[idx++] = (float)(volume / volume_sma);
    
    // Feature: atr_pct
    features[idx++] = (float)(atr[0] / close);
    
    // Feature: support_distance_pct
    double recent_low = GetRecentLow(20);
    features[idx++] = (float)((close - recent_low) / close);
    
    return true;
}

//+------------------------------------------------------------------+
//| Get BB Position (0-1 scale)                                        |
//+------------------------------------------------------------------+
double GetBBPosition()
{
    double bb_upper[], bb_lower[];
    
    if(CopyBuffer(bb_handle, 1, 1, 1, bb_upper) <= 0) return 0;
    if(CopyBuffer(bb_handle, 2, 1, 1, bb_lower) <= 0) return 0;
    
    double close = iClose(_Symbol, PERIOD_CURRENT, 1);
    double bb_range = bb_upper[0] - bb_lower[0];
    
    if(bb_range == 0) return 0.5;
    
    return (close - bb_lower[0]) / bb_range;
}

//+------------------------------------------------------------------+
//| Get RSI value                                                      |
//+------------------------------------------------------------------+
double GetRSI()
{
    double rsi[];
    if(CopyBuffer(rsi_handle, 0, 1, 1, rsi) <= 0) return 50;
    return rsi[0];
}

//+------------------------------------------------------------------+
//| Run ONNX model inference                                           |
//+------------------------------------------------------------------+
double PredictProbability()
{
    //--- Prepare output array
    float output[];
    ArrayResize(output, 2); // Binary classification: [prob_class_0, prob_class_1]
    
    //--- Run inference
    if(!OnnxRun(onnx_handle, ONNX_DEFAULT, features, output))
    {
        Print("❌ ONNX inference failed");
        return 0.0;
    }
    
    //--- Return probability of positive class (SHORT wins)
    // Note: Output format depends on how model was exported
    // Typically output[1] is probability of class 1 (win)
    
    if(ArraySize(output) >= 2)
        return (double)output[1];
    else
        return (double)output[0];
}

//+------------------------------------------------------------------+
//| Check if we can open a new trade                                   |
//+------------------------------------------------------------------+
bool CanOpenTrade()
{
    //--- Check if already have an open position
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionSelectByTicket(PositionGetTicket(i)))
        {
            if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber &&
               PositionGetString(POSITION_SYMBOL) == _Symbol)
            {
                return false; // Already have a position
            }
        }
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Open a SHORT trade                                                 |
//+------------------------------------------------------------------+
void OpenShortTrade()
{
    double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
    
    double tp = NormalizeDouble(price - InpTPPips * point * 10, digits);
    double sl = NormalizeDouble(price + InpSLPips * point * 10, digits);
    
    MqlTradeRequest request = {};
    MqlTradeResult result = {};
    
    request.action = TRADE_ACTION_DEAL;
    request.symbol = _Symbol;
    request.volume = InpLotSize;
    request.type = ORDER_TYPE_SELL;
    request.price = price;
    request.sl = sl;
    request.tp = tp;
    request.deviation = 10;
    request.magic = InpMagicNumber;
    request.comment = StringFormat("Solara SHORT P=%.2f", current_probability);
    
    if(OrderSend(request, result))
    {
        Print("✅ SHORT opened: ", result.order, " @ ", price, 
              " TP:", tp, " SL:", sl, " Prob:", current_probability);
    }
    else
    {
        Print("❌ OrderSend failed: ", GetLastError());
    }
}

//+------------------------------------------------------------------+
//| Helper: Get time since last touch of upper BB                      |
//+------------------------------------------------------------------+
int GetTimeSinceLastTouch(double upper_band)
{
    for(int i = 1; i <= 100; i++)
    {
        double high = iHigh(_Symbol, PERIOD_CURRENT, i);
        if(high >= upper_band)
            return i;
    }
    return 100; // No touch found
}

//+------------------------------------------------------------------+
//| Helper: Get volume SMA                                             |
//+------------------------------------------------------------------+
double GetVolumeSMA(int period)
{
    double sum = 0;
    for(int i = 1; i <= period; i++)
    {
        sum += (double)iVolume(_Symbol, PERIOD_CURRENT, i);
    }
    return sum / period;
}

//+------------------------------------------------------------------+
//| Helper: Get recent low                                             |
//+------------------------------------------------------------------+
double GetRecentLow(int period)
{
    double lowest = iLow(_Symbol, PERIOD_CURRENT, 1);
    for(int i = 2; i <= period; i++)
    {
        double low = iLow(_Symbol, PERIOD_CURRENT, i);
        if(low < lowest) lowest = low;
    }
    return lowest;
}

//+------------------------------------------------------------------+
//| Create info panel                                                  |
//+------------------------------------------------------------------+
void CreatePanel()
{
    int x = 10, y = 30;
    int width = 200, height = 150;
    
    ObjectCreate(0, "Solara_Panel", OBJ_RECTANGLE_LABEL, 0, 0, 0);
    ObjectSetInteger(0, "Solara_Panel", OBJPROP_XDISTANCE, x);
    ObjectSetInteger(0, "Solara_Panel", OBJPROP_YDISTANCE, y);
    ObjectSetInteger(0, "Solara_Panel", OBJPROP_XSIZE, width);
    ObjectSetInteger(0, "Solara_Panel", OBJPROP_YSIZE, height);
    ObjectSetInteger(0, "Solara_Panel", OBJPROP_BGCOLOR, InpPanelColor);
    ObjectSetInteger(0, "Solara_Panel", OBJPROP_BORDER_TYPE, BORDER_FLAT);
    
    CreateLabel("Solara_Title", x + 10, y + 10, "☀️ SOLARA ML", clrGold, 12);
    CreateLabel("Solara_Status", x + 10, y + 35, "Status: Initializing...", clrWhite, 9);
    CreateLabel("Solara_Prob", x + 10, y + 55, "Probability: -", clrWhite, 9);
    CreateLabel("Solara_BB", x + 10, y + 75, "BB Position: -", clrWhite, 9);
    CreateLabel("Solara_RSI", x + 10, y + 95, "RSI: -", clrWhite, 9);
    CreateLabel("Solara_Signal", x + 10, y + 115, "Signal: -", clrWhite, 9);
}

//+------------------------------------------------------------------+
//| Create a text label                                                |
//+------------------------------------------------------------------+
void CreateLabel(string name, int x, int y, string text, color clr, int size)
{
    ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
    ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
    ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
    ObjectSetString(0, name, OBJPROP_TEXT, text);
    ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
    ObjectSetInteger(0, name, OBJPROP_FONTSIZE, size);
}

//+------------------------------------------------------------------+
//| Update info panel                                                  |
//+------------------------------------------------------------------+
void UpdatePanel(string status, double prob, bool triggered)
{
    double bb_pos = GetBBPosition();
    double rsi = GetRSI();
    
    color status_color = triggered ? clrLime : clrWhite;
    
    ObjectSetString(0, "Solara_Status", OBJPROP_TEXT, "Status: " + status);
    ObjectSetInteger(0, "Solara_Status", OBJPROP_COLOR, status_color);
    
    ObjectSetString(0, "Solara_Prob", OBJPROP_TEXT, 
        StringFormat("Probability: %.1f%% (need %.1f%%)", prob * 100, InpProbThreshold * 100));
    ObjectSetInteger(0, "Solara_Prob", OBJPROP_COLOR, 
        prob >= InpProbThreshold ? clrLime : clrWhite);
    
    ObjectSetString(0, "Solara_BB", OBJPROP_TEXT, 
        StringFormat("BB Position: %.2f (need %.2f)", bb_pos, InpBBThreshold));
    ObjectSetInteger(0, "Solara_BB", OBJPROP_COLOR, 
        bb_pos >= InpBBThreshold ? clrLime : clrWhite);
    
    ObjectSetString(0, "Solara_RSI", OBJPROP_TEXT, 
        StringFormat("RSI: %.1f (need %d)", rsi, InpRSIThreshold));
    ObjectSetInteger(0, "Solara_RSI", OBJPROP_COLOR, 
        rsi >= InpRSIThreshold ? clrLime : clrWhite);
    
    string signal_text = triggered ? 
        (prob >= InpProbThreshold ? "🟢 TAKE SHORT!" : "🟡 Signal but low prob") :
        "⚪ Waiting for signal";
    ObjectSetString(0, "Solara_Signal", OBJPROP_TEXT, signal_text);
}
//+------------------------------------------------------------------+
