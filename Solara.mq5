// Solara.mq5 - Main EA for Multi-Symbol Strategy Scanner
//+------------------------------------------------------------------+
//| Description: Multi-strategy scanner with PTS and BB Reversal     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, Trading Scanner"
#property link      "https://example.com"
#property version   "2.00"
#property description "Multi-Strategy Scanner - Pullback Trading & BB Reversal Data Collection"
#property strict

//+------------------------------------------------------------------+
//| Includes                                                         |
//+------------------------------------------------------------------+
#include "StrategyBase.mqh"
#include "StrategyManager.mqh"
#include "/Strategies/PTSStrategy.mqh"
#include "/Strategies/BBReversalStrategy.mqh"
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

input group "=== BB REVERSAL STRATEGY SETTINGS ==="
input bool   Enable_BB_Reversal = true;           // Enable BB Reversal data collection
input int    BB_LookbackPeriod = 20;              // Lookback periods for label calculation
input bool   BB_KeepOnlyLastRow = true;           // Keep only last row in CSV
input string BB_SupportLevels = "1.0800,1.0750,1.0700"; // Support levels for EURUSD
input int    BB_LondonStart = 8;                  // London session start hour
input int    BB_LondonEnd = 17;                   // London session end hour
input int    BB_NYStart = 13;                     // NY session start hour
input int    BB_NYEnd = 22;                       // NY session end hour

input int    BB_Period = 20;                      // Bollinger Band period
input double BB_Deviation = 2.0;                  // BB deviation
input int    BB_RSI_Period = 14;                  // RSI period
input int    BB_ATR_Period = 14;                  // ATR period
input int    BB_SMA_Short = 50;                   // Short SMA period
input int    BB_SMA_Long = 200;                   // Long SMA period
input int    BB_Volume_SMA_Period = 20;           // Volume SMA period
input int    BB_Touch_Lookback = 20;              // Touch history lookback

input group "=== CSV & LOGGING SETTINGS ==="
input string CSV_FileName = "ScannerSignals.csv"; // Output CSV file name
input bool   AppendToCSV = true;              // Append to existing CSV file

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
CStrategyManager*   g_strategyManager;        // Strategy manager instance
CPTSStrategy*       g_ptsStrategy;            // PTS strategy instance
CBBReversalStrategy* g_bbReversalStrategy;    // BB Reversal strategy instance

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
    
    // Initialize PTS Strategy if enabled
    if(Enable_PTS_Strategy)
    {
        g_ptsStrategy = new CPTSStrategy();
        g_ptsStrategy.SetEnabled(true);

        g_ptsStrategy.SetPTSParameters(PTS_SL_Multiplier, PTS_TP_Multiplier,
                                        0.00015,  // emaSlopeThreshold
                                        0.35,     // longBBMin
                                        0.75,     // longBBMax
                                        0.25,     // shortBBMin
                                        0.65,     // shortBBMax
                                        0.5,      // atrRatioThreshold
                                        18);      // adxMinValue
        
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
    
    // Initialize BB Reversal Strategy if enabled
    if(Enable_BB_Reversal)
    {
        g_bbReversalStrategy = new CBBReversalStrategy();
        g_bbReversalStrategy.SetEnabled(true);
        g_bbReversalStrategy.SetTimeframe(PERIOD_H4);
        g_bbReversalStrategy.SetLookbackPeriod(BB_LookbackPeriod);
        g_bbReversalStrategy.SetKeepOnlyLastRow(BB_KeepOnlyLastRow);
        
        // Parse support levels if provided
        if(BB_SupportLevels != "")
            g_bbReversalStrategy.SetSupportLevels(BB_SupportLevels);
        
        // Set session times
        g_bbReversalStrategy.SetSessionTimes(BB_LondonStart, BB_LondonEnd, 
                                             BB_NYStart, BB_NYEnd);
        
        BaseSettings bbSettings;
        bbSettings.name = "BB_Reversal_Data_Collector";
        bbSettings.enabled = EnableTrading && Enable_BB_Reversal;
        bbSettings.lotSize = 0.0;  // No trading
        bbSettings.dailyLossLimit = 0.0;
        bbSettings.maxPositions = 0;
        bbSettings.magicNumber = 303030;
        
        g_bbReversalStrategy.SetEnabled(bbSettings.enabled);
        
        g_strategyManager.AddStrategy(g_bbReversalStrategy);
        Print("BB Reversal Strategy initialized for data collection");
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
    if(g_ptsStrategy) delete g_ptsStrategy;
    if(g_bbReversalStrategy) delete g_bbReversalStrategy;
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
    
    // ========== TIME CHECKING FOR PTS STRATEGY ==========
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
    // ========== END OF TIME CHECKING ==========
    
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
    
    // ADD BB REVERSAL STRATEGY CONFIGURATION
    Print("=== BB Reversal Strategy ===");
    Print("Enabled: ", Enable_BB_Reversal ? "Yes" : "No");
    Print("Mode: Data Collection Only (No Trading)");
    Print("Lookback Period: ", BB_LookbackPeriod, " candles");
    Print("Keep Only Last Row: ", BB_KeepOnlyLastRow ? "Yes" : "No");
    Print("Support Levels: ", BB_SupportLevels);
    Print("London Session: ", BB_LondonStart, ":00 - ", BB_LondonEnd, ":00 GMT");
    Print("NY Session: ", BB_NYStart, ":00 - ", BB_NYEnd, ":00 GMT");
    Print("Indicator Parameters:");
    Print("  BB Period: ", BB_Period, " | Deviation: ", BB_Deviation);
    Print("  RSI Period: ", BB_RSI_Period);
    Print("  ATR Period: ", BB_ATR_Period);
    Print("  SMA Short/Long: ", BB_SMA_Short, "/", BB_SMA_Long);
    Print("  Volume SMA Period: ", BB_Volume_SMA_Period);
    Print("  Touch Lookback: ", BB_Touch_Lookback);
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
        comment += (Enable_PTS_Strategy ? "PTS[ON] " : "PTS[OFF] ");
        comment += (Enable_BB_Reversal ? "BB_Rev[ON]" : "BB_Rev[OFF]");
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
        Print("Daily filter would qualify pairs based on D1 trends");
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
    
    // Test PTS strategy (only H4)
    if(g_ptsStrategy && g_ptsStrategy.IsEnabled() && timeframe == PERIOD_H4)
    {
        BaseSignal signal = g_ptsStrategy.CheckSignal(symbol, timeframe);
        
        if(signal.signal != "")
        {
            Print("PTS SIGNAL: ", signal.signal, " @ ", DoubleToString(signal.price, 5));
        }
    }
    
    // Test BB Reversal strategy (data collection)
    if(g_bbReversalStrategy && g_bbReversalStrategy.IsEnabled() && timeframe == PERIOD_H4)
    {
        Print("BB Reversal strategy would collect data on BB touch");
        Print("Data saved to CSV file when BB touch conditions met");
    }
}