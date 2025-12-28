# **SOLARA MULTI-STRATEGY SCANNER**
## **Functional Specification v2.0**

---

### **Document Control**
- **Document Title:** Solara Multi-Strategy Scanner Specification
- **Version:** 2.0
- **Date:** December 2024
- **Status:** Active Development
- **Based On:** Current working Solara.mq5 codebase
- **Target:** Integration with Pullback Trading System (PTS)

---

## **1. EXECUTIVE SUMMARY**

**Solara** is a multi-strategy trading scanner for MetaTrader 5 that operates in two modes:

1. **SCANNING MODE**: Screen symbols for trading signals and log to CSV
2. **TRADING MODE**: Automatically execute trades based on signals

**Current Status**: Solara.mq5 is operational with EMA crossover strategy.
**New Integration**: Adding Pullback Trading System (PTS) as a second strategy.

**Key Features (Current + Planned):**

- ✅ **EMA 20/50 Crossover Strategy** (Existing)
- ✅ **Multi-symbol scanning** (40+ forex pairs)
- ✅ **Multi-timeframe scanning** (H1, H4, D1)
- ✅ **CSV logging** of all signals
- ✅ **Daily loss limits**
- 🔄 **PULLBACK TRADING STRATEGY** (New)
- 🔄 **Strategy toggle system** (On/Off per strategy)
- 🔄 **Independent configuration** per strategy

---

## **2. CURRENT ARCHITECTURE (As Built)**

### **2.1 File Structure (ACTUAL)**

Solara/
├── Solara.mq5 (MAIN EA - Working)
├── EMAStrategy.mqh (EMA Crossover Strategy)
├── TradeLogger.mqh (CSV Logging & Trade Execution)
├── ScannerCore.mqh (Utility Functions)
└── SymbolList.mqh (Symbol Definitions)


### **2.2 Current Component Overview**

| Component | Status | Purpose |
|-----------|--------|---------|
| **Solara.mq5** | ✅ Working | Main EA with timer-based scanning |
| **EMAStrategy.mqh** | ✅ Working | EMA 20/50 crossover logic |
| **TradeLogger.mqh** | ✅ Working | CSV logging & trade execution |
| **ScannerCore.mqh** | ✅ Working | Symbol validation & new bar detection |
| **SymbolList.mqh** | ✅ Working | List of symbols to scan |

---

## **3. TARGET ARCHITECTURE (After PTS Integration)**

### **3.1 Revised File Structure**

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


### **3.2 Component Relationships**

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


---

## **4. STRATEGY TOGGLE SYSTEM (NEW FEATURE)**

### **4.1 User Interface Design**
```mql5
// In Solara.mq5 Input Parameters
input group "=== STRATEGY SELECTION ==="
input bool   Enable_EMA_Strategy = true;       // [✔] Enable EMA Crossover
input bool   Enable_PTS_Strategy = false;      // [ ] Enable Pullback Trading

input group "=== EMA STRATEGY SETTINGS ==="
input int    EMA_FastPeriod = 20;
input int    EMA_SlowPeriod = 50;
// ... existing EMA inputs

input group "=== PTS STRATEGY SETTINGS ==="
input double PTS_LotSize = 0.01;
input int    PTS_MaxPositions = 10;
input string PTS_CSVFile = "QualifiedPairs.csv";
// ... PTS-specific inputs