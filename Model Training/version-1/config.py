"""
Configuration file for Bollinger Band Reversal Trading Model
"""

CONFIG = {
    # Data settings
    'data': {
        'file_path': 'Meta Model Stacking XGBoost/GBPUSD_Stacking_Data.csv',
        'timestamp_col': 'timestamp',
        'label_col': 'label',
        'train_test_split': 0.8,  # 80% train, 20% test
    },
    
    # Features to use from your CSV
    'features': [
        # Core BB Features
        'bb_touch_strength',      # How close to lower BB (low/lower_band)
        'bb_position',            # Position in BB channel ((close-lower)/(upper-lower))
        
        # RSI Features
        'rsi_value',              # RSI value
        'rsi_divergence',         # Bullish divergence (0/1)
        
        # Volume & Candle Features
        'candle_rejection',       # Lower wick / candle body
        'candle_body_pct',        # (close-open)/close*100
        
        # Previous Candle Context (CRITICAL!)
        'prev_candle_body_pct',   # Previous candle body %
        'prev_volume_ratio',      # Previous volume ratio
        'price_momentum',         # New low momentum

        # Support & History
        'time_since_last_touch',  # Candles since last touch

        # Volatility & Trend
        # 'atr_pct',                # ATR as % of price
        # 'trend_strength',         # Higher timeframe trend
        # 'volume_ratio',           # Current volume / 20-period average
        # 'bb_width_pct',           # BB width as % ((upper-lower)/middle*100)
        # 'gap_from_prev_close',    # Gap from previous close
        # 'prev_was_selloff',       # Was previous a selloff? (0/1)
        # 'previous_touches',       # Recent BB touches count
        # 'support_distance_pct',   # Distance to support
        # 'session',                # Trading session

    ],
    
    # Model settings
    'model': {
        'type': 'random_forest',

        # # Version 3
        # 'params': {
        #     'n_estimators': 300,
        #     'max_depth': 4,
        #     'min_samples_split': 15,
        #     'class_weight': {0: 1, 1: 1.3},
        #     'random_state': 42,
        #     'min_samples_leaf': 8,
        #     'max_features': 'log2'  # Try log2 for 10 features
        # }

        # Version 2
        'params': {
            'n_estimators': 200,
            'max_depth': 5,
            'min_samples_split': 20,
            'class_weight': 'balanced_subsample',
            'random_state': 42,
            'min_samples_leaf': 5,
            'max_features': 'sqrt'
        }


        # Version 1
        # 'params': {
        #     'n_estimators': 100,
        #     'max_depth': 3,
        #     'min_samples_split': 30,
        #     'class_weight': 'balanced',
        #     'random_state': 42,
        #     'min_samples_leaf': 10
        # }
    },
    
    # Trading rules
    'trading': {
        'min_confidence': 0.65,      # Only trade if probability > 65%
        'reward_risk_ratio': 3.0,    # Assume 3:1 reward:risk (BB width)
        'max_daily_trades': 2,
        'position_size_pct': 2.0,    # Risk 2% per trade
    },
    
    # Validation thresholds
    'thresholds': {
        'min_precision': 0.45,       # At least 40% of signals should win
        'min_recall': 0.55,          # Catch at least 50% of opportunities
        'min_accuracy': 0.60,        # At least 55% overall accuracy
    }
}