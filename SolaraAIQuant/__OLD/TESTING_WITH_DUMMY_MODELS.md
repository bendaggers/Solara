# Testing Solara AI Quant with Dummy Models

This guide explains how to test the Solara AI Quant system using dummy models that generate random signals, without requiring actual ML model files or live MT5 connection.

## What We've Created

We've added 3 dummy models to the system:

1. **Dummy Random Long M5** - Generates random LONG signals on M5 timeframe
2. **Dummy Random Short M15** - Generates random SHORT signals on M15 timeframe  
3. **Dummy Random Long H1** - Generates random LONG signals on H1 timeframe

## Quick Start Testing

### Step 1: Install Dependencies
```bash
cd SolaraAIQuant
pip install -r requirements.txt
```

### Step 2: Verify Dummy Models Work
```bash
# Test the dummy predictor logic
python test_dummy_simple.py

# Expected output:
# - Dummy predictor generates random signals
# - Model registry loads successfully
# - 3 dummy models found and enabled
```

### Step 3: Test System Startup (Without MT5)
```bash
# Create a test .env file (copy from example)
cp .env.example .env.test

# Edit .env.test with dummy values (no real MT5 needed for initial test)

# Try running main.py - it will fail on MT5 connection but show other components work
python main.py
```

## Full System Testing (With MT5)

### Prerequisites
1. **MetaTrader 5** installed and running
2. **Demo account** created in MT5
3. **MarketDataExporter EA** compiled and attached to a chart

### Step 1: Configure Environment
Copy `.env.example` to `.env` and update:
```env
# Real MT5 credentials from your demo account
MT5_LOGIN=your_demo_account_number
MT5_PASSWORD=your_demo_password
MT5_SERVER=your_broker_server
MT5_TERMINAL_PATH=C:\Users\YourName\AppData\Roaming\MetaQuotes\Terminal\YourTerminalHash

# Environment
SAQ_ENV=development
SAQ_LOG_LEVEL=DEBUG
```

### Step 2: Setup MT5 Expert Advisor
1. Copy `MQL5/Production/MarketDataExporter.mq5` to MT5's `MQL5/Experts/` folder
2. Open MetaEditor (F4 in MT5) and compile the EA
3. Attach the EA to any chart (e.g., EURUSD H1)
4. Enable "Allow Algo Trading" in EA settings

### Step 3: Run Solara AI Quant
```bash
cd SolaraAIQuant
python main.py
```

### Expected Startup Sequence
```
INFO: saq_starting - System starting
INFO: config_validated - Configuration OK
INFO: mt5_connected - Connected to MT5
INFO: database_initialized - Database ready
INFO: registry_loaded - Models loaded (should show 3 enabled dummy models)
INFO: survivor_started - Position manager started
INFO: watchdog_starting - Watching for CSV files...
```

## How Dummy Models Work

### Signal Generation Logic
Each dummy model:
1. Randomly selects 0-2 symbols from available market data
2. Generates random confidence between `min_confidence` and 1.0
3. Creates signals based on model type (LONG/SHORT)
4. Logs each signal with details

### Model Registry Configuration
Dummy models are configured in `model_registry.yaml` with:
- `model_file: ""` (empty - no .pkl file required)
- `class_path: "predictors.dummy_predictor.DummyRandomPredictor"`
- `enabled: true`
- Specific magic numbers (503000, 502000, 501000)

### Testing Different Scenarios

#### 1. Test Signal Aggregation
Dummy models will generate conflicting signals (LONG vs SHORT) to test the conflict checker.

#### 2. Test Risk Management
Signals will go through all 5 risk checks before execution.

#### 3. Test Trade Execution
If all checks pass, trades will be placed via MT5 API.

#### 4. Test Survivor Engine
Open positions will be managed by the 22-stage trailing stop system.

## Monitoring & Logs

### Key Log Entries to Watch For
```
dummy_predictor_loaded - Dummy model loaded
dummy_signal_generated - Individual signal created
dummy_predictor_completed - Model run completed
engine_cycle_complete - All models processed
signal_aggregated - Signals combined
risk_check_passed/failed - Risk management results
trade_executed - Order placed (if all checks pass)
```

### Log Location
- Console output (structured JSON)
- `logs/` directory (if configured)

## Troubleshooting

### Common Issues & Solutions

#### 1. MT5 Connection Failed
```
CRITICAL: mt5_connection_failed
```
**Solution:** Verify MT5 is running, credentials are correct, and terminal path exists.

#### 2. CSV Files Not Created
System waits forever for CSV files
```
INFO: watchdog_starting - Watching for CSV files...
```
**Solution:** Ensure MarketDataExporter EA is attached to chart and exporting data.

#### 3. No Signals Generated
```
INFO: dummy_predictor_completed - signals_generated=0
```
**Solution:** This is normal - dummy models randomly generate 0-2 signals. Wait for next cycle.

#### 4. Database Errors
```
ERROR: database_initialization_failed
```
**Solution:** Check write permissions in `state/` directory.

## Advanced Testing

### Modify Dummy Model Behavior
Edit `predictors/dummy_predictor.py` to:
- Change signal probability (adjust `random.choices` weights)
- Increase/decrease number of signals
- Add specific symbol filtering
- Simulate different market conditions

### Add More Dummy Models
Copy the template in `model_registry.yaml` to add:
- More timeframes
- Different model types
- Specific symbol whitelists
- Varying confidence thresholds

### Test Without MT5 (Simulation Mode)
For pure logic testing without MT5:
1. Create mock CSV files in `MQL5/Files/` directory
2. Manually trigger file modification events
3. Monitor pipeline execution without actual trades

## Next Steps After Testing

Once dummy models are working correctly:

1. **Enable real models** - Set `enabled: true` for BB Reversal models in registry
2. **Verify ML models** - Ensure `.pkl` files exist in `Models/` directory
3. **Test with small risk** - Use minimal lot sizes in demo account
4. **Monitor performance** - Run for 24-48 hours before considering live trading
5. **Review logs** - Check for any errors or unexpected behavior

## Safety Notes

⚠️ **Always test with demo account first!**
- Start with minimum position sizes
- Monitor system closely for first few days
- Have manual stop-loss plans ready
- Never risk more than you can afford to lose

## Support

If you encounter issues:
1. Check logs for error messages
2. Verify all prerequisites are met
3. Review configuration files
4. Test components individually using provided test scripts