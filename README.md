# SOLARA MULTI-STRATEGY SCANNER

## Functional Specification v2.0

### Document Control

- Document Title: Solara Multi-Strategy Scanner Specification
- Version: 2.0
- Date: December 2024
- Status: Active Development
- Based On: Current working Solara.mq5 codebase
- Target: Integration with Pullback Trading System (PTS)

## 1\. EXECUTIVE SUMMARY

Solara is a multi-strategy trading scanner for MetaTrader 5 that operates in two modes:

- SCANNING MODE: Screen symbols for trading signals and log to CSV
- TRADING MODE: Automatically execute trades based on signals

Current Status: Solara.mq5 is operational with EMA crossover strategy.  
New Integration: Adding Pullback Trading System (PTS) as a second strategy.

Key Features (Current + Planned):

- ✅ EMA 20/50 Crossover Strategy (Existing)
- ✅ Multi-symbol scanning (40+ forex pairs)
- ✅ Multi-timeframe scanning (H1, H4, D1)
- ✅ CSV logging of all signals
- ✅ Daily loss limits
- 🔄 PULLBACK TRADING STRATEGY (New)
- 🔄 Strategy toggle system (On/Off per strategy)
- 🔄 Independent configuration per strategy

## 2\. CURRENT ARCHITECTURE (As Built)

### 2.1 File Structure (ACTUAL)

Solara/

├── Solara.mq5 (MAIN EA - Working)

├── EMAStrategy.mqh (EMA Crossover Strategy)

├── TradeLogger.mqh (CSV Logging & Trade Execution)

├── ScannerCore.mqh (Utility Functions)

└── SymbolList.mqh (Symbol Definitions)

### 2.2 Current Component Overview

| Component | Status | Purpose |
| --- | --- | --- |
| Solara.mq5 | ✅ Working | Main EA with timer-based scanning |
| EMAStrategy.mqh | ✅ Working | EMA 20/50 crossover logic |
| TradeLogger.mqh | ✅ Working | CSV logging & trade execution |
| ScannerCore.mqh | ✅ Working | Symbol validation & new bar detection |
| SymbolList.mqh | ✅ Working | List of symbols to scan |

## 3\. TARGET ARCHITECTURE (After PTS Integration)

### 3.1 Revised File Structure

Solara/

├── Solara.mq5 (MAIN EA - Enhanced)

├── StrategyBase.mqh (NEW - Abstract base class)

├── StrategyManager.mqh (NEW - Strategy orchestration)

├── Configuration.mqh (NEW - Central config)

├── TradeLogger.mqh (Enhanced for multi-strategy)

├── ScannerCore.mqh (Enhanced)

├── SymbolList.mqh (No change)

└── Strategies/ (NEW - Strategy implementations)

├── EMAStrategy.mqh (Refactored to extend StrategyBase)

└── PTSStrategy.mqh (NEW - Pullback Trading Strategy)

### 3.2 Component Relationships

text

┌─────────────────────────────────────────────┐

│ Solara.mq5 (Main EA) │

│ • Timer-based execution │

│ • User input management │

│ • Chart event handling │

└─────────────────────┬───────────────────────┘

│

┌─────────────▼─────────────┐

│ StrategyManager.mqh │

│ • Strategy lifecycle │

│ • Risk coordination │

│ • Performance tracking │

└─────────────┬─────────────┘

│

┌─────────────▼─────────────┐

│ StrategyBase.mqh │

│ (Abstract Interface) │

└─────────────┬─────────────┘

│

┌─────────────────┼─────────────────┐

▼ ▼ ▼

┌─────────┐ ┌─────────┐ ┌─────────┐

│ EMA │ │ PTS │ │ Future │

│ Strategy│ │ Strategy│ │ Strategy│

└─────────┘ └─────────┘ └─────────┘

## 4\. STRATEGY TOGGLE SYSTEM (NEW FEATURE)

### 4.1 User Interface Design

// In Solara.mq5 Input Parameters

input group "=== STRATEGY SELECTION ==="

input bool Enable_EMA_Strategy = true; // \[✔\] Enable EMA Crossover

input bool Enable_PTS_Strategy = false; // \[ \] Enable Pullback Trading

input group "=== EMA STRATEGY SETTINGS ==="

input int EMA_FastPeriod = 20;

input int EMA_SlowPeriod = 50;

// ... existing EMA inputs

input group "=== PTS STRATEGY SETTINGS ==="

input double PTS_LotSize = 0.01;

input int PTS_MaxPositions = 10;

input string PTS_CSVFile = "QualifiedPairs.csv";

// ... PTS-specific inputs

### 4.2 Toggle Behavior

| State | Description |
| --- | --- |
| EMA ON, PTS OFF | Current behavior (backward compatible) |
| EMA OFF, PTS ON | Test PTS strategy in isolation |
| BOTH ON | Both strategies active (max positions apply) |
| BOTH OFF | Scanner runs but no trades (monitoring only) |

4.3 Magic Number Allocation

| Strategy | Magic Number | Comment Format |
| --- | --- | --- |
| EMA | 12345 | "EMA_Crossover" |
| PTS | 202412 | "PTS: H4 Pullback \[LONG/SHORT\]" |

## 5\. EMA STRATEGY (CURRENT - To Be Refactored)

### 5.1 Current Logic (As Coded)

// Entry Conditions:

1\. Previous bar: EMA20 > EMA50 (crossover)

2\. Current bar: Close OR body midpoint > EMA20

// Exit Conditions:

1\. Current close < EMA20

// Timeframes: H1, H4, D1 (user selectable)

// Scanning: Every ScanIntervalSeconds

### 5.2 Refactoring Requirements

- Extend StrategyBase class
- Maintain backward compatibility
- Add toggle support
- Separate configuration from logic

## 6\. PTS STRATEGY (NEW - Based on PTS Spec)

### 6.1 Core Logic

// TWO-LAYER SYSTEM:

// LAYER 1: Daily Filter (00:05 GMT)

1\. Check D1 EMA50 trend (price above/below)

2\. Check volatility (ATR > 50% of average)

3\. Output: QualifiedPairs.csv

// LAYER 2: 4-Hour Entry (6 times daily)

1\. Read qualified pairs from CSV

2\. Check Bollinger Band touch

3\. Check reversal candle pattern

4\. Enter with 1:2 risk-reward (2×ATR SL, 4×ATR TP)

6.2 Schedule

| Time (GMT) | Action |
| --- | --- |
| 00:05 | Daily Filter + Immediate H4 Scan |
| 04:00 | H4 Scan |
| 08:00 | H4 Scan |
| 12:00 | H4 Scan |
| 16:00 | H4 Scan |
| 20:00 | H4 Scan |

### 6.3 Entry Conditions

For LONG (Buy dips in uptrend):

- H4 price touches lower Bollinger Band
- Bullish reversal candle (Engulfing/Hammer/Strong Close)

For SHORT (Sell rallies in downtrend):

- H4 price touches upper Bollinger Band
- Bearish reversal candle (Engulfing/Shooting Star/Strong Close)

### 6.4 Risk Management

- Stop Loss: Entry ± 2×ATR
- Take Profit: Entry ± 4×ATR (1:2 ratio)
- Max Positions: 10 concurrent
- One position per pair

## 7\. CONFIGURATION SYSTEM

### 7.1 Input Parameter Groups

// Group 1: Global Settings (Apply to all strategies)

input group "=== GLOBAL SETTINGS ==="

input bool EnableTrading = false; // Master trading toggle

input int ScanIntervalSeconds = 60; // Base scan frequency

input double GlobalDailyLossLimit = 500.0; // Total daily loss limit

// Group 2: EMA Strategy

input group "=== EMA STRATEGY ==="

input bool Enable_EMA_Strategy = true;

// ... EMA-specific inputs

// Group 3: PTS Strategy

input group "=== PTS STRATEGY ==="

input bool Enable_PTS_Strategy = false;

// ... PTS-specific inputs

7.2 CSV Files Management

| File | Purpose | Strategy |
| --- | --- | --- |
| ScannerSignals.csv | All trade signals | Both |
| QualifiedPairs.csv | Daily qualified pairs | PTS only |
| TradeLog.csv | Executed trades | Both |

## 8\. RISK MANAGEMENT SYSTEM

### 8.1 Multi-Level Risk Controls

text

┌─────────────────────────────────────┐

│ GLOBAL RISK MANAGER │

│ • Total daily loss limit │

│ • Max total positions (20) │

│ • Symbol blacklisting │

└───────────────┬─────────────────────┘

│

┌───────────┼───────────┐

▼ ▼ ▼

┌───────┐ ┌───────┐ ┌───────┐

│ EMA │ │ PTS │ │ Future│

│ Risk │ │ Risk │ │ Risk │

└───────┘ └───────┘ └───────┘

• Daily • Daily • Daily

loss loss loss

• Max • Max • Max

positions positions positions

### 8.2 Position Counting

// Per Strategy: Count by magic number

int EMA_Positions = CountPositionsByMagic(12345);

int PTS_Positions = CountPositionsByMagic(202412);

// Global: Sum of all strategies

int Total_Positions = EMA_Positions + PTS_Positions;

### 8.3 Loss Tracking

// Separate tracking per strategy

double EMA_DailyLoss = 0.0;

double PTS_DailyLoss = 0.0;

// Global tracking

double Global_DailyLoss = EMA_DailyLoss + PTS_DailyLoss;

## 9\. EXECUTION FLOW

### 9.1 Initialization Sequence

mql5

OnInit()

↓

Load SymbolList.mqh

↓

Initialize TradeLogger

↓

Initialize StrategyManager

↓

IF Enable_EMA_Strategy → Load EMAStrategy

↓

IF Enable_PTS_Strategy → Load PTSStrategy

↓

Set Timer (ScanIntervalSeconds)

↓

Start Strategies

9.2 Timer Execution Flow

mql5

OnTimer()

↓

StrategyManager.OnTimer()

↓

├── IF 00:05 GMT → PTS.DailyFilter()

│ └── Create QualifiedPairs.csv

│

├── IF H4 Scan Time → PTS.H4Scan()

│ └── Check qualified pairs for entries

│

├── EMA Strategy Scan

│ └── Check all symbols on selected timeframes

│

└── Update Statistics & Chart Comment

### 9.3 Trade Execution Flow

Strategy Generates Signal

↓

Check: Is strategy enabled? (Toggle)

↓

Check: Daily loss limit not exceeded

↓

Check: Max positions not reached

↓

Check: No existing position on symbol

↓

Execute Trade via TradeLogger

↓

Log to CSV & Update Statistics

## 10\. ERROR HANDLING

### 10.1 Error Categories

| Category | Examples | Response |
| --- | --- | --- |
| Configuration | Invalid period, lot size | Log error, disable strategy |
| Market Data | Symbol not available | Skip symbol, log warning |
| File I/O | Cannot open CSV | Retry, log error |
| Trade Execution | Order rejected | Log error, no retry |

### 10.2 Recovery Procedures

- CSV File Missing: Recreate file on next daily filter
- Indicator Failure: Release handles, recreate
- Broker Disconnect: Pause trading until reconnected
- Memory Issue: Clear cache, restart timer

## 11\. PERFORMANCE MONITORING

### 11.1 Real-time Statistics

// Per Strategy Metrics

struct StrategyMetrics {

string name;

int signals_today;

int trades_today;

int wins_today;

int losses_today;

double pnl_today;

double pnl_total;

};

// Global Metrics

int TotalScans = 0;

int TotalSignals = 0;

int TotalTrades = 0;

datetime LastScanTime = 0;

11.2 Chart Comment Display

Solara Scanner v2.0

\====================

Mode: TRADING | SCANNING: ON

Strategies: EMA\[ON\] PTS\[OFF\]

Symbols: 40 | Scans: 1245

Signals: 45 | Trades: 12

Daily P&L: EMA: +\$45 | PTS: \$0

Total P&L: +\$320

Last Scan: 14:32:05

Next Scan: 14:33:05

## 12\. TESTING REQUIREMENTS

### 12.1 Unit Tests

- EMA Strategy: Verify crossover logic, exit conditions
- PTS Strategy: Verify daily filter, H4 entry logic
- Toggle System: Verify enable/disable functionality
- Risk Management: Verify position counting, loss limits

### 12.2 Integration Tests

- Both Strategies ON: Verify no interference
- CSV Operations: Verify file creation/reading
- Timer Accuracy: Verify 00:05 GMT execution
- Trade Execution: Verify correct magic numbers

### 12.3 Backtesting Requirements

| Strategy | Minimum Period | Pairs | Win Rate Target |
| --- | --- | --- | --- |
| EMA | 2 years | All in SymbolList | \>35% |
| PTS | 3 years | All in SymbolList | \>35% |
| Combined | 2 years | All in SymbolList | \>35% |

## 13\. MIGRATION PATH

### 13.1 Phase 1: Preparation (Week 1)

- ✅ Analyze current code (DONE)
- ✅ Update functional specs (THIS DOCUMENT)
- Create StrategyBase.mqh
- Create StrategyManager.mqh
- Create Configuration.mqh

### 13.2 Phase 2: Refactoring (Week 2)

- Refactor EMAStrategy to extend StrategyBase
- Update TradeLogger for multi-strategy support
- Add toggle system to Solara.mq5
- Test EMA strategy still works

### 13.3 Phase 3: PTS Development (Week 3)

- Create PTSStrategy.mqh
- Implement daily filter (00:05 GMT)
- Implement H4 scanning schedule
- Implement 1:2 risk-reward exits

### 13.4 Phase 4: Integration (Week 4)

- Integrate PTS into StrategyManager
- Test both strategies together
- Verify risk management across strategies
- Demo testing (2 weeks minimum)

### 13.5 Phase 5: Optimization (Future)

- Add advanced risk management
- Add performance reporting
- Add additional strategies

## 14\. SUCCESS CRITERIA

### 14.1 Functional Requirements

- EMA strategy works exactly as before
- Users can toggle strategies on/off
- PTS strategy executes per specification
- Both strategies can run simultaneously
- Risk limits are enforced per strategy
- CSV logging works for both strategies

### 14.2 Performance Requirements

- No degradation in scanning speed
- Memory usage within limits
- Accurate 00:05 GMT execution for PTS
- Trade execution within 5 seconds

### 14.3 Quality Requirements

- No crashes in 30-day demo test
- Backtest shows positive expectancy
- All errors properly logged
- Configuration persists across restarts

## 15\. GLOSSARY

| Term | Definition |
| --- | --- |
| EMA Strategy | Existing EMA 20/50 crossover system |
| PTS Strategy | Pullback Trading System (new) |
| Qualified Pairs | Pairs that pass daily trend filter (PTS) |
| Magic Number | Unique ID for strategy's trades |
| Toggle System | On/Off switch for each strategy |
| Daily Filter | PTS process that runs at 00:05 GMT |
| H4 Scan | PTS entry check that runs 6x daily |

## 16\. APPENDICES

Appendix A: Current Code Summary

- Solara.mq5: 500+ lines, timer-based, working
- EMAStrategy.mqh: 300+ lines, crossover logic
- TradeLogger.mqh: 400+ lines, CSV and execution
- ScannerCore.mqh: 100+ lines, utilities
- SymbolList.mqh: 50+ lines, 40+ symbols

Appendix B: PTS Specification Summary

- Strategy: Pullback trading in trends
- Timeframes: D1 for trend, H4 for entry
- Entry: BB touch + reversal candle
- Exit: Fixed 1:2 risk-reward ratio
- Schedule: Daily filter at 00:05, H4 scans every 4 hours