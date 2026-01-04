// Solara.mq5 - Main EA for Multi-Symbol Strategy Scanner
//+------------------------------------------------------------------+
//| Description: Multi-strategy scanner with EMA and PTS strategies  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, Trading Scanner"
#property link      "https://example.com"
#property version   "2.00"
#property description "Multi-Strategy Scanner - EMA Crossover & Pullback Trading"
#property strict

//+------------------------------------------------------------------+
//| Includes                                                         |
//+------------------------------------------------------------------+
#include "StrategyBase.mqh"
#include "StrategyManager.mqh"
#include "/Strategies/EMAStrategy.mqh"
#include "/Strategies/PTSStrategy.mqh"
#include "TradeLogger.mqh"
#include "ScannerCore.mqh"
#include "Symbols.mqh"

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
input group "=== GLOBAL SETTINGS ==="
input bool   EnableTrading = true;           // Master trading toggle
input int    ScanIntervalSeconds = 60;        // Base scan frequency in seconds
input double GlobalDailyLossLimit = 500.0;    // Total daily loss limit for all strategies

input group "=== EMA STRATEGY SETTINGS ==="
input bool   Enable_EMA_Strategy = false;      // Enable EMA Crossover strategy
input int    EMA_FastPeriod = 20;             // Fast EMA period
input int    EMA_SlowPeriod = 50;             // Slow EMA period
input double EMA_LotSize = 0.01;              // Lot size for EMA strategy
input double EMA_DailyLossLimit = 100.0;      // Daily loss limit for EMA strategy
input int    EMA_MaxPositions = 10;           // Maximum positions for EMA strategy

input group "=== PTS STRATEGY SETTINGS ==="
input bool   Enable_PTS_Strategy = true;     // Enable Pullback Trading strategy
input double PTS_LotSize = 0.01;              // Lot size for PTS strategy
input double PTS_DailyLossLimit = 100.0;      // Daily loss limit for PTS strategy
input int    PTS_MaxPositions = 10;           // Maximum positions for PTS strategy
input double PTS_SL_Multiplier = 2.0;         // Stop loss multiplier (ATR)
input double PTS_TP_Multiplier = 4.0;         // Take profit multiplier (ATR)
input int    PTS_BB_Period = 20;              // Bollinger Band period
input double PTS_BB_Deviation = 2.0;          // Bollinger Band deviation
input int    PTS_ATR_Period = 14;             // ATR period

input group "=== CSV & LOGGING SETTINGS ==="
input string CSV_FileName = "ScannerSignals.csv"; // Output CSV file name
input bool   AppendToCSV = true;              // Append to existing CSV file

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
CStrategyManager*   g_strategyManager;        // Strategy manager instance
CEMAStrategy*       g_emaStrategy;            // EMA strategy instance
CPTSStrategy*       g_ptsStrategy;            // PTS strategy instance

// Statistics
int      g_totalScans = 0;
int      g_totalSignals = 0;
datetime g_lastScanTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("=== Solara Multi-Strategy Scanner Initializing v2.0 ===");
    
    // Initialize strategy manager
    g_strategyManager = new CStrategyManager();
    
    // Initialize EMA Strategy if enabled
    if(Enable_EMA_Strategy)
    {
        g_emaStrategy = new CEMAStrategy();
        g_emaStrategy.SetEnabled(true);
        g_emaStrategy.SetPeriods(EMA_FastPeriod, EMA_SlowPeriod);
        
        BaseSettings emaSettings;
        emaSettings.name = "EMA_Crossover";
        emaSettings.enabled = EnableTrading && Enable_EMA_Strategy;
        emaSettings.lotSize = EMA_LotSize;
        emaSettings.dailyLossLimit = EMA_DailyLossLimit;
        emaSettings.maxPositions = EMA_MaxPositions;
        emaSettings.magicNumber = 12345;
        
        // Apply settings (would need setter methods in CEMAStrategy)
        // For now, we'll use the constructor defaults
        g_emaStrategy.SetEnabled(emaSettings.enabled);
        
        g_strategyManager.AddStrategy(g_emaStrategy);
        Print("EMA Strategy initialized and added");
    }
    
    // Initialize PTS Strategy if enabled
    if(Enable_PTS_Strategy)
    {
        g_ptsStrategy = new CPTSStrategy();
        g_ptsStrategy.SetEnabled(true);
        g_ptsStrategy.SetPTSParameters(PTS_SL_Multiplier, PTS_TP_Multiplier, 
                                       PTS_BB_Period, PTS_BB_Deviation);
        
        BaseSettings ptsSettings;
        ptsSettings.name = "Pullback_Trading_System";
        ptsSettings.enabled = EnableTrading && Enable_PTS_Strategy;
        ptsSettings.lotSize = PTS_LotSize;
        ptsSettings.dailyLossLimit = PTS_DailyLossLimit;
        ptsSettings.maxPositions = PTS_MaxPositions;
        ptsSettings.magicNumber = 202412;
        
        // Apply settings
        g_ptsStrategy.SetEnabled(ptsSettings.enabled);
        
        g_strategyManager.AddStrategy(g_ptsStrategy);
        Print("PTS Strategy initialized and added");
    }
    
    // Initialize all strategies
    if(!g_strategyManager.InitializeAll())
    {
        Print("ERROR: Failed to initialize strategies");
        return INIT_FAILED;
    }
    
    // Print configuration summary
    PrintConfiguration();
    
    // Set timer for scanning
    EventSetTimer(ScanIntervalSeconds);
    
    Print("Solara Scanner initialized successfully");
    Print("Strategies active: ", g_strategyManager.GetStrategyCount());
    Print("Master Trading: ", EnableTrading ? "ENABLED" : "DISABLED");
    Print("==================================================");
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    // Kill timer
    EventKillTimer();
    
    // Deinitialize strategies
    if(g_strategyManager)
        g_strategyManager.DeinitializeAll();
    
    // Clean up
    if(g_emaStrategy) delete g_emaStrategy;
    if(g_ptsStrategy) delete g_ptsStrategy;
    if(g_strategyManager) delete g_strategyManager;
    
    // Print statistics
    Print("=== Solara Scanner Deinitializing ===");
    Print("Total scans performed: ", g_totalScans);
    Print("Total signals found: ", g_totalSignals);
    Print("Strategies active: ", g_strategyManager ? g_strategyManager.GetStrategyCount() : 0);
    Print("Deinit reason: ", GetDeinitReasonText(reason));
    Print("=====================================");
}

//+------------------------------------------------------------------+
//| Timer function - Main scanning loop                              |
//+------------------------------------------------------------------+
void OnTimer()
{
    // Update statistics
    g_lastScanTime = TimeCurrent();
    g_totalScans++;
    
    // ========== ADDED: TIME CHECKING FOR PTS STRATEGY ==========
    MqlDateTime timeNow;
    TimeCurrent(timeNow);
    
    // 1. DEBUG: Print time for verification
    if(g_totalScans % 30 == 0) // Every 30 scans (30 minutes)
    {
        Print("Current Time: ", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
              " | Hour: ", timeNow.hour, " | Minute: ", timeNow.min);
    }
    
    // 2. Check for 00:05 GMT for PTS Daily Filter
    if(timeNow.hour == 0 && timeNow.min == 5 && timeNow.sec < 10)
    {
        Print("=== 00:05 GMT DETECTED - Running PTS Daily Filter ===");
        if(g_ptsStrategy && g_ptsStrategy.IsEnabled())
        {
            g_ptsStrategy.RunDailyFilter();
            Print("=== Immediate H4 Scan after Daily Filter ===");
            g_ptsStrategy.RunH4Scan();
        }
    }
    
    // 3. Check for H4 scan times (04:00, 08:00, 12:00, 16:00, 20:00 GMT)
    int h4_times[] = {4, 8, 12, 16, 20};
    for(int i = 0; i < ArraySize(h4_times); i++)
    {
        if(timeNow.hour == h4_times[i] && timeNow.min == 0 && timeNow.sec < 10)
        {
            Print("=== H4 Scan Time ", h4_times[i], ":00 GMT ===");
            if(g_ptsStrategy && g_ptsStrategy.IsEnabled())
            {
                g_ptsStrategy.RunH4Scan();
            }
        }
    }
    // ========== END OF ADDED CODE ==========
    
    // Run strategy manager timer
    if(g_strategyManager)
        g_strategyManager.OnTimer();
    
    // Update chart comment
    UpdateChartComment();
    
    // Log every 10th scan
    if(g_totalScans % 10 == 0)
    {
        Print("Scan #", g_totalScans, " completed at ", TimeToString(g_lastScanTime, TIME_SECONDS));
        if(g_strategyManager)
            g_strategyManager.PrintAllStatus();
    }
}

//+------------------------------------------------------------------+
//| Print configuration summary                                      |
//+------------------------------------------------------------------+
void PrintConfiguration()
{
    Print("=== Solara Configuration Summary ===");
    Print("Scan Interval: ", ScanIntervalSeconds, " seconds");
    Print("Global Daily Loss Limit: $", GlobalDailyLossLimit);
    Print("Master Trading: ", EnableTrading ? "ENABLED" : "DISABLED");
    Print("");
    
    Print("=== EMA Strategy ===");
    Print("Enabled: ", Enable_EMA_Strategy ? "Yes" : "No");
    Print("Trading: ", (EnableTrading && Enable_EMA_Strategy) ? "Yes" : "No");
    Print("Fast EMA: ", EMA_FastPeriod);
    Print("Slow EMA: ", EMA_SlowPeriod);
    Print("Lot Size: ", EMA_LotSize);
    Print("Daily Loss Limit: $", EMA_DailyLossLimit);
    Print("Max Positions: ", EMA_MaxPositions);
    Print("");
    
    Print("=== PTS Strategy ===");
    Print("Enabled: ", Enable_PTS_Strategy ? "Yes" : "No");
    Print("Trading: ", (EnableTrading && Enable_PTS_Strategy) ? "Yes" : "No");
    Print("Lot Size: ", PTS_LotSize);
    Print("Daily Loss Limit: $", PTS_DailyLossLimit);
    Print("Max Positions: ", PTS_MaxPositions);
    Print("SL Multiplier: ", PTS_SL_Multiplier);
    Print("TP Multiplier: ", PTS_TP_Multiplier);
    Print("Risk-Reward Ratio: 1:", DoubleToString(PTS_TP_Multiplier / PTS_SL_Multiplier, 1));
    Print("BB Period: ", PTS_BB_Period);
    Print("BB Deviation: ", PTS_BB_Deviation);
    Print("ATR Period: ", PTS_ATR_Period);
    Print("");
    
    Print("=== Logging ===");
    Print("CSV File: ", CSV_FileName);
    Print("Append to CSV: ", AppendToCSV ? "Yes" : "No");
    Print("===============================");
}

//+------------------------------------------------------------------+
//| Update chart comment with status                                 |
//+------------------------------------------------------------------+
void UpdateChartComment()
{
    string comment = "Solara Scanner v2.0\n";
    comment += "=====================\n";
    comment += "Mode: " + (EnableTrading ? "TRADING" : "SCREENING") + "\n";
    
    if(g_strategyManager)
    {
        comment += "Strategies: ";
        comment += (Enable_EMA_Strategy ? "EMA[ON] " : "EMA[OFF] ");
        comment += (Enable_PTS_Strategy ? "PTS[ON]" : "PTS[OFF]");
        comment += "\n";
        
        comment += "Total Positions: " + IntegerToString(g_strategyManager.GetTotalOpenPositions()) + "\n";
        comment += "Today P&L: $" + DoubleToString(g_strategyManager.GetTotalTodayPNL(), 2) + "\n";
    }
    
    comment += "Total Scans: " + IntegerToString(g_totalScans) + "\n";
    comment += "Total Signals: " + IntegerToString(g_totalSignals) + "\n";
    comment += "Last Scan: " + (g_totalScans > 0 ? TimeToString(g_lastScanTime, TIME_SECONDS) : "Never") + "\n";
    comment += "Next Scan: " + TimeToString(g_lastScanTime + ScanIntervalSeconds, TIME_SECONDS) + "\n";
    
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
//| Manual scan function                                             |
//+------------------------------------------------------------------+
void ManualScan()
{
    Print("=== Manual scan triggered at ", TimeToString(TimeCurrent(), TIME_SECONDS), " ===");
    
    if(g_strategyManager)
    {
        // Force run PTS daily filter if it's around 00:05 GMT
        MqlDateTime currentTime;
        TimeCurrent(currentTime);
        
        if(currentTime.hour == 0 && currentTime.min == 5)
        {
            Print("Manual PTS Daily Filter execution");
            if(g_ptsStrategy && g_ptsStrategy.IsEnabled())
            {
                // We need to add a public method to run daily filter
                Print("Note: Daily filter would run at next scheduled time");
            }
        }
        
        // Run timer event
        g_strategyManager.OnTimer();
    }
    
    UpdateChartComment();
}

//+------------------------------------------------------------------+
//| Run PTS Daily Filter manually                                    |
//+------------------------------------------------------------------+
void RunPTSDailyFilter()
{
    if(g_ptsStrategy && g_ptsStrategy.IsEnabled())
    {
        Print("=== Manual PTS Daily Filter Execution ===");
        // Note: We need to add a public RunDailyFilter() method to CPTSStrategy
        Print("Daily filter would qualify pairs based on D1 trends");
        Print("This function requires implementation in PTSStrategy class");
    }
    else
    {
        Print("PTS Strategy not enabled");
    }
}

//+------------------------------------------------------------------+
//| Chart event handler                                              |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
    // Add chart objects for manual controls if needed
    // Example: Buttons for manual scan, strategy toggles, etc.
    
    if(id == CHARTEVENT_KEYDOWN)
    {
        // Example: Space bar for manual scan
        if(lparam == 32) // Space key
        {
            ManualScan();
        }
    }
}

//+------------------------------------------------------------------+
//| Test function - Check single symbol                              |
//+------------------------------------------------------------------+
void TestSymbol(string symbol, ENUM_TIMEFRAMES timeframe)
{
    Print("Testing ", symbol, " on ", TimeframeToString(timeframe));
    
    if(!IsValidSymbol(symbol))
    {
        Print("ERROR: Symbol not valid");
        return;
    }
    
    // Test EMA strategy
    if(g_emaStrategy && g_emaStrategy.IsEnabled())
    {
        BaseSignal signal = g_emaStrategy.CheckSignal(symbol, timeframe);
        
        if(signal.signal != "")
        {
            Print("EMA SIGNAL: ", signal.signal, " @ ", DoubleToString(signal.price, 5));
        }
    }
    
    // Test PTS strategy (only H4)
    if(g_ptsStrategy && g_ptsStrategy.IsEnabled() && timeframe == PERIOD_H4)
    {
        BaseSignal signal = g_ptsStrategy.CheckSignal(symbol, timeframe);
        
        if(signal.signal != "")
        {
            Print("PTS SIGNAL: ", signal.signal, " @ ", DoubleToString(signal.price, 5));
        }
    }
}