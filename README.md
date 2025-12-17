# SOLARA Multi-Symbol Strategy Scanner - Functional Specification

## Overview
A lightweight MQL5 Expert Advisor that scans multiple currency pairs for trading opportunities using simple EMA crossover strategy. The EA operates in screening mode (logging signals to CSV) with optional auto-trading capabilities.

## Core Architecture
```
TradingScanner.mq5 - Main EA file (timer-driven execution)
Symbols.txt - Plain text file listing symbols to scan
ScannerCore.mqh - Core scanning and symbol management functions
EMAStrategy.mqh - EMA crossover strategy implementation  
TradeLogger.mqh - CSV logging and trade execution functions
```

## File Specifications

### 1. TradingScanner.mq5 (Main EA)
**Responsibilities:**
- Timer event handler (runs every 60 seconds)
- Coordinates scanning process
- Manages EA lifecycle (OnInit, OnDeinit, OnTimer)

**Input Parameters:**
```mql5
// General Settings
input bool EnableTrading = false;           // Enable auto-trading (false = screening only)
input string SymbolListFile = "Symbols.txt"; // File containing symbols to scan
input int ScanIntervalSeconds = 60;         // Scanning frequency in seconds

// EMA Strategy Settings
input int EMA_FastPeriod = 20;              // Fast EMA period
input int EMA_SlowPeriod = 50;              // Slow EMA period
input double FixedLotSize = 0.01;           // Fixed lot size for trading
input double DailyLossLimit = 100.0;        // Daily loss limit in USD per strategy

// CSV Export Settings
input string CSVFileName = "ScannerSignals.csv"; // Output CSV file name
input bool AppendToCSV = true;              // Append to existing CSV file
```

### 2. Symbols.txt (Symbol Configuration)
**Format:**
```
# Multi-Symbol Scanner - Symbol List
# Add one symbol per line
# Comments start with #
# Example symbols:

EURUSD
GBPUSD
USDJPY
XAUUSD
BTCUSD
# NAS100  # Commented out - not scanned
```

**Rules:**
- One symbol per line
- Comments start with #
- Blank lines are ignored
- Symbols must be valid and available in Market Watch

### 3. ScannerCore.mqh (Core Functions)
**Functions:**
```mql5
// Reads symbols from text file
bool ReadSymbolsFromFile(string filename, string &symbols[])

// Checks if new bar has formed for given symbol/timeframe
bool IsNewBar(string symbol, ENUM_TIMEFRAMES timeframe, datetime &lastBarTime)

// Gets array of timeframes for strategy
void GetStrategyTimeframes(ENUM_TIMEFRAMES &timeframes[])

// Validates if symbol exists and is tradeable
bool IsValidSymbol(string symbol)
```

### 4. EMAStrategy.mqh (Strategy Logic)
**Entry Conditions (ALL must be true):**
1. **Current Price Position:**
   - Current close price > EMA20
   - Current close price > EMA50

2. **EMA Crossover (Previous Bar):**
   - On previous bar (bar index 1):
     - EMA20 > EMA50 (fast above slow)
   - On bar before previous (bar index 2):
     - EMA20 <= EMA50 (fast was below or equal to slow)
   - This confirms crossover happened on previous bar

3. **Crossover Freshness:**
   - Crossover must have occurred exactly on previous bar
   - Not older than 1 bar

**Exit Conditions (ANY triggers exit):**
1. **Price Below EMA20:**
   - Current close price < EMA20 value
   - AND candle body does not touch EMA20 line
   - Candle body defined as: (open + close) / 2

2. **Stop Loss (if trading enabled):**
   - Fixed percentage or ATR-based stop loss

**Strategy Logic Flow:**
```
For each symbol in symbol list:
  For each timeframe in [PERIOD_H1, PERIOD_H4, PERIOD_D1]:
    If new bar formed:
      Calculate EMA20 and EMA50 for current and previous bars
      Check entry conditions
      If entry signal:
        Log signal to CSV
        If trading enabled AND risk limits allow:
          Place buy order with stop loss
```

### 5. TradeLogger.mqh (Logging & Execution)
**Functions:**
```mql5
// Logs signal to CSV file
void LogSignalToCSV(string csvFile, string symbol, string strategy, 
                   string signal, double price, double ema20, 
                   double ema50, string timeframe, bool append = true)

// Executes trade if conditions met
bool ExecuteTrade(string symbol, string strategy, ENUM_ORDER_TYPE type, 
                 double lotSize, double slPoints, double tpPoints)

// Checks daily loss limits
bool CheckDailyLossLimit(string strategy, double dailyLossLimit)

// Formats CSV row
string FormatCSVRow(datetime timestamp, string symbol, string strategy, 
                   string signal, double price, double ema20, 
                   double ema50, string timeframe)
```

## CSV Output Format
**File Location:** `MQL5/Files/ScannerSignals.csv`

**Columns:**
```
Timestamp,Symbol,Strategy,Signal,Price,EMA20,EMA50,Timeframe,Action
```

**Example Row:**
```
2024-01-15 14:30:00,EURUSD,EMA_Crossover,BUY,1.09542,1.09480,1.09320,H1,SCREENED
```

**Column Details:**
- `Timestamp`: Signal detection time (YYYY-MM-DD HH:MM:SS)
- `Symbol`: Currency pair (e.g., EURUSD)
- `Strategy`: Strategy name (e.g., EMA_Crossover)
- `Signal`: BUY or SELL (currently only BUY for this strategy)
- `Price`: Entry price at signal detection
- `EMA20`: EMA20 value at signal bar
- `EMA50`: EMA50 value at signal bar  
- `Timeframe`: Chart timeframe (H1, H4, D1, etc.)
- `Action`: SCREENED (logged) or TRADED (if trading enabled)

## Timeframe Handling
The strategy checks three timeframes independently:
1. **H1 (1-hour)** - Checks every hour at minute 00
2. **H4 (4-hour)** - Checks every 4 hours at hours 00, 04, 08, 12, 16, 20
3. **D1 (Daily)** - Checks daily at 00:00

**New Bar Detection Logic:**
- Each symbol/timeframe combination maintains last checked bar time
- On each scan, compare current bar open time with last checked time
- If different, new bar has formed and strategy should be evaluated

## Risk Management (When Trading Enabled)
**Per-Strategy Limits:**
1. **Fixed Lot Size:** Each trade uses predefined lot size
2. **Daily Loss Limit:** Stops trading for strategy if daily loss exceeds limit
3. **Maximum Open Positions:** 1 position per symbol per strategy

**Daily Loss Tracking:**
- Resets at 00:00 server time
- Tracks net profit/loss per strategy
- If loss > DailyLossLimit, strategy is disabled for rest of day

## Error Handling
**Critical Errors (EA stops):**
- Symbol list file not found
- No valid symbols to scan
- File system errors (cannot write CSV)

**Non-Critical Errors (Continue scanning):**
- Individual symbol not available
- Indicator calculation errors
- Temporary connectivity issues

**Error Logging:**
All errors logged to Experts journal with timestamp and details.

## Performance Considerations
**Scanning Efficiency:**
- Scans only when new bar forms (not every tick)
- 60-second timer interval (configurable)
- Parallel symbol processing (not sequential)

**Resource Usage:**
- Minimal memory footprint
- No database dependencies
- Simple file-based operations

## Setup Instructions
1. **Prepare Symbol List:**
   - Create `Symbols.txt` in `MQL5/Files/` folder
   - Add one symbol per line

2. **Configure EA:**
   - Attach EA to any chart (timeframe irrelevant)
   - Set input parameters
   - Enable/disable trading as needed

3. **Monitor Output:**
   - Check Experts tab for logs
   - Review `ScannerSignals.csv` for signals
   - Monitor trades if trading enabled

## Future Enhancement Placeholders
**Marked with `// TODO:` comments in code:**
1. **SMS Integration:** `// TODO: Implement SMS notification`
2. **Additional Strategies:** `// TODO: Add more strategy modules`
3. **Advanced Risk Management:** `// TODO: Implement dynamic position sizing`
4. **Webhook Notifications:** `// TODO: Add webhook support`
5. **Performance Analytics:** `// TODO: Add strategy performance tracking`

## Testing Protocol
**Unit Tests:**
1. Symbol list reading
2. New bar detection
3. EMA crossover logic
4. CSV logging

**Integration Tests:**
1. Full scanning cycle
2. Multiple symbol processing
3. CSV file creation/append
4. Trading execution (if enabled)

**Manual Tests:**
1. Verify signals against manual chart analysis
2. Check CSV format and data accuracy
3. Test error handling scenarios

## Limitations
1. **Single Strategy:** Currently implements only EMA crossover
2. **Fixed Timeframes:** Hardcoded to H1, H4, D1 (configurable in code)
3. **Basic Risk Management:** Simple fixed lot and daily loss limits
4. **No Backtesting:** Designed for live scanning only

## Support & Maintenance
**Log Files:**
- `ScannerSignals.csv` - All trading signals
- Experts Journal - Error and operation logs

**Troubleshooting:**
1. No signals: Check symbol list and Market Watch
2. CSV not updating: Check file permissions
3. EA not running: Check timer events and errors

**Version History:**
- v1.0: Initial release with EMA crossover strategy
- v1.1: Added multi-timeframe support
- v1.2: Enhanced CSV logging format