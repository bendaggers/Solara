// Solara.mq5 - Main EA for Multi-Symbol Strategy Scanner
//+------------------------------------------------------------------+
//| Description: Scans multiple symbols for EMA crossover signals    |
//|              on multiple timeframes, logs to CSV                 |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, Trading Scanner"
#property link      "https://example.com"
#property version   "1.00"
#property description "Multi-Symbol Strategy Scanner - Scans symbols for EMA crossover signals"
#property description "Logs signals to CSV file. Optional auto-trading available."
#property strict

//+------------------------------------------------------------------+
//| Includes                                                         |
//+------------------------------------------------------------------+
#include "ScannerCore.mqh"
#include "TradeLogger.mqh"
#include "EMAStrategy.mqh"
#include "Symbols.mqh"

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
input group "=== General Settings ==="
input bool   EnableTrading = false;           // Enable auto-trading (false = screening only)
input int    ScanIntervalSeconds = 60;        // Scanning frequency in seconds

input group "=== EMA Strategy Settings ==="
input int    EMA_FastPeriod = 20;             // Fast EMA period
input int    EMA_SlowPeriod = 50;             // Slow EMA period
input double FixedLotSize = 0.01;             // Fixed lot size for trading
input double DailyLossLimit = 100.0;          // Daily loss limit in USD per strategy

input group "=== CSV Export Settings ==="
input string CSVFileName = "ScannerSignals.csv"; // Output CSV file name
input bool   AppendToCSV = true;              // Append to existing CSV file

input group "=== Timeframe Settings ==="
input bool   ScanH1 = true;                   // Scan 1-hour timeframe
input bool   ScanH4 = true;                   // Scan 4-hour timeframe  
input bool   ScanD1 = true;                   // Scan daily timeframe

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
string   Symbols[];                           // Array of symbols to scan
int      SymbolCount = 0;                     // Number of symbols

// Last checked bar times per symbol per timeframe (flattened array)
datetime LastBarTimes[];                      // Size = SymbolCount * 3

// Strategy settings
EMAStrategySettings EMA_Settings;

// Scan statistics
int      TotalScans = 0;
int      TotalSignals = 0;
datetime LastScanTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("=== Trading Scanner Initializing ===");
    
    // Initialize strategy settings
    EMA_Settings.fastPeriod = EMA_FastPeriod;
    EMA_Settings.slowPeriod = EMA_SlowPeriod;
    EMA_Settings.lotSize = FixedLotSize;
    EMA_Settings.dailyLossLimit = DailyLossLimit;
    EMA_Settings.enableTrading = EnableTrading;
    
    // Validate settings
    if(!ValidateSettings())
    {
        Print("ERROR: Invalid settings. Please check input parameters.");
        return INIT_PARAMETERS_INCORRECT;
    }
    
    // Load symbols from include file
    if(!LoadSymbols())
    {
        Print("ERROR: Failed to load symbols");
        return INIT_FAILED;
    }
    
    Print("Loaded ", SymbolCount, " symbols for scanning");
    
    // Initialize last bar times array (flattened 1D array)
    ArrayResize(LastBarTimes, SymbolCount * 3);  // 3 timeframes per symbol
    
    for(int i = 0; i < SymbolCount; i++)
    {
        // Set initial times for H1, H4, D1
        LastBarTimes[i * 3 + 0] = 0;  // H1
        LastBarTimes[i * 3 + 1] = 0;  // H4  
        LastBarTimes[i * 3 + 2] = 0;  // D1
    }
    
    // Print settings
    PrintSettings();
    
    // Set timer for scanning
    EventSetTimer(ScanIntervalSeconds);
    
    Print("Trading Scanner initialized successfully");
    Print("Mode: ", EnableTrading ? "TRADING" : "SCREENING");
    Print("Scan interval: ", ScanIntervalSeconds, " seconds");
    Print("========================================");
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Load symbols from include file                                   |
//+------------------------------------------------------------------+
bool LoadSymbols()
{
    // Copy symbols from include file
    SymbolCount = GetSymbolCount();
    if(SymbolCount == 0)
    {
        Print("ERROR: No symbols defined in Symbols.mqh");
        return false;
    }
    
    ArrayResize(Symbols, SymbolCount);
    for(int i = 0; i < SymbolCount; i++)
    {
        Symbols[i] = GetSymbol(i);
    }
    
    return true;
}

// ... REST OF THE FILE REMAINS THE SAME (OnDeinit, OnTimer, etc.) ...

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    // Kill timer
    EventKillTimer();
    
    // Print statistics
    Print("=== Trading Scanner Deinitializing ===");
    Print("Total scans performed: ", TotalScans);
    Print("Total signals found: ", TotalSignals);
    Print("Deinit reason: ", GetDeinitReasonText(reason));
    Print("======================================");
}

//+------------------------------------------------------------------+
//| Timer function - Main scanning loop                              |
//+------------------------------------------------------------------+
void OnTimer()
{
    // Perform scan
    PerformScan();
    
    // Update last scan time
    LastScanTime = TimeCurrent();
    TotalScans++;
    
    // Update comment on chart
    UpdateChartComment();
}

//+------------------------------------------------------------------+
//| Perform scan of all symbols and timeframes                       |
//+------------------------------------------------------------------+
void PerformScan()
{
    int signalsThisScan = 0;
    
    // Loop through all symbols
    for(int i = 0; i < SymbolCount; i++)
    {
        string symbol = Symbols[i];
        
        // Validate symbol
        if(!IsValidSymbol(symbol))
        {
            continue;
        }
        
        // Check each timeframe
        if(ScanH1)
        {
            if(CheckAndScanTimeframe(symbol, PERIOD_H1, 0))
                signalsThisScan++;
        }
        
        if(ScanH4)
        {
            if(CheckAndScanTimeframe(symbol, PERIOD_H4, 1))
                signalsThisScan++;
        }
        
        if(ScanD1)
        {
            if(CheckAndScanTimeframe(symbol, PERIOD_D1, 2))
                signalsThisScan++;
        }
    }
    
    // Update statistics
    TotalSignals += signalsThisScan;
    
    // Log scan completion
    if(signalsThisScan > 0 || TotalScans % 10 == 0) // Log every 10th scan or when signals found
    {
        Print("Scan #", TotalScans, " completed. Signals found: ", signalsThisScan);
    }
}

//+------------------------------------------------------------------+
//| Check and scan specific timeframe                                |
//+------------------------------------------------------------------+
bool CheckAndScanTimeframe(string symbol, ENUM_TIMEFRAMES timeframe, int timeframeIndex)
{
    int symbolIndex = ArrayIndexOfSymbol(symbol);
    if(symbolIndex == -1) return false;
    
    // Calculate index in flattened array
    int arrayIndex = symbolIndex * 3 + timeframeIndex;
    
    // Check if new bar has formed
    if(IsNewBar(symbol, timeframe, LastBarTimes[arrayIndex]))
    {
        // Run EMA strategy
        TradingSignal signal = CheckEMAStrategy(symbol, timeframe, EMA_Settings);
        
        if(signal.signal != "")
        {
            // Log to CSV
            LogSignalToCSV(CSVFileName, signal, AppendToCSV);
            return true;
        }
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Find array index of symbol                                       |
//+------------------------------------------------------------------+
int ArrayIndexOfSymbol(string symbol)
{
    for(int i = 0; i < SymbolCount; i++)
    {
        if(Symbols[i] == symbol)
            return i;
    }
    return -1;
}

//+------------------------------------------------------------------+
//| Validate all settings                                            |
//+------------------------------------------------------------------+
bool ValidateSettings()
{
    // Validate EMA periods
    if(EMA_FastPeriod <= 0 || EMA_SlowPeriod <= 0)
    {
        Print("ERROR: EMA periods must be positive");
        return false;
    }
    
    if(EMA_FastPeriod >= EMA_SlowPeriod)
    {
        Print("ERROR: Fast EMA period must be less than slow EMA period");
        return false;
    }
    
    // Validate lot size
    if(FixedLotSize <= 0)
    {
        Print("ERROR: Lot size must be positive");
        return false;
    }
    
    // Validate scan interval
    if(ScanIntervalSeconds < 10)
    {
        Print("WARNING: Scan interval very short (", ScanIntervalSeconds, "s). Minimum 10s recommended.");
    }
    
    // Validate at least one timeframe is selected
    if(!ScanH1 && !ScanH4 && !ScanD1)
    {
        Print("ERROR: At least one timeframe must be selected for scanning");
        return false;
    }
    
    // Validate strategy settings
    if(!ValidateSettings(EMA_Settings))
    {
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Print all settings                                               |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Print all settings                                               |
//+------------------------------------------------------------------+
void PrintSettings()
{
    Print("=== Scanner Settings ===");
    Print("Scan Interval: ", ScanIntervalSeconds, " seconds");
    Print("CSV File: ", CSVFileName);
    Print("Append to CSV: ", AppendToCSV ? "Yes" : "No");
    Print("Trading Enabled: ", EnableTrading ? "Yes" : "No");
    Print("Symbols to scan: ", SymbolCount, " symbols");
    Print("");
    
    Print("=== Timeframes to Scan ===");
    Print("H1 (1-hour): ", ScanH1 ? "Yes" : "No");
    Print("H4 (4-hour): ", ScanH4 ? "Yes" : "No");
    Print("D1 (Daily): ", ScanD1 ? "Yes" : "No");
    Print("");
    
    PrintStrategySettings(EMA_Settings);
}

//+------------------------------------------------------------------+
//| Update chart comment with status                                 |
//+------------------------------------------------------------------+
void UpdateChartComment()
{
    string comment = "Trading Scanner v1.0\n";
    comment += "=====================\n";
    comment += "Mode: " + (EnableTrading ? "TRADING" : "SCREENING") + "\n";
    comment += "Symbols: " + IntegerToString(SymbolCount) + "\n";
    comment += "Total Scans: " + IntegerToString(TotalScans) + "\n";
    comment += "Total Signals: " + IntegerToString(TotalSignals) + "\n";
    comment += "Last Scan: " + (TotalScans > 0 ? TimeToString(LastScanTime, TIME_SECONDS) : "Never") + "\n";
    comment += "Next Scan: " + TimeToString(LastScanTime + ScanIntervalSeconds, TIME_SECONDS) + "\n";
    comment += "CSV File: " + CSVFileName + "\n";
    
    Comment(comment);
}

//+------------------------------------------------------------------+
//| Get deinit reason text                                           |
//+------------------------------------------------------------------+
string GetDeinitReasonText(const int reason)
{
    switch(reason)
    {
        case REASON_ACCOUNT:    return "Account changed";
        case REASON_CHARTCHANGE: return "Chart changed";
        case REASON_CHARTCLOSE:  return "Chart closed";
        case REASON_CLOSE:       return "Terminal closed";
        case REASON_INITFAILED:  return "Initialization failed";
        case REASON_PARAMETERS:  return "Input parameters changed";
        case REASON_RECOMPILE:   return "Program recompiled";
        case REASON_REMOVE:      return "Expert removed from chart";
        case REASON_TEMPLATE:    return "Template changed";
        default:                 return "Unknown reason";
    }
}

//+------------------------------------------------------------------+
//| Manual scan function (can be called from button or hotkey)       |
//+------------------------------------------------------------------+
void ManualScan()
{
    Print("Manual scan triggered at ", TimeToString(TimeCurrent(), TIME_SECONDS));
    PerformScan();
}

//+------------------------------------------------------------------+
//| Test function - Check single symbol manually                     |
//+------------------------------------------------------------------+
void TestSymbol(string symbol, ENUM_TIMEFRAMES timeframe)
{
    Print("Testing ", symbol, " on ", TimeframeToString(timeframe));
    
    if(!IsValidSymbol(symbol))
    {
        Print("ERROR: Symbol not valid");
        return;
    }
    
    TradingSignal signal = CheckEMAStrategy(symbol, timeframe, EMA_Settings);
    
    if(signal.signal != "")
    {
        Print("SIGNAL FOUND: ", signal.signal, " @ ", DoubleToString(signal.price, 5));
        Print("EMA20: ", DoubleToString(signal.ema20, 5));
        Print("EMA50: ", DoubleToString(signal.ema50, 5));
    }
    else
    {
        Print("No signal found");
    }
}

//+------------------------------------------------------------------+
//| Chart event handler (for manual controls)                        |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
    // TODO: Add chart objects for manual controls
    // Example: Buttons for manual scan, symbol test, etc.
}