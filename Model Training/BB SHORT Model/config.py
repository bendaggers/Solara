"""
Configuration for Bollinger Bands Reversal Short Model
"""

# Lag periods
LAGS = [1, 2, 3]

# Feature groups to create
FEATURE_GROUPS = {
    'price': ['close', 'open', 'high', 'low', 'volume'],
    'returns': ['ret'],
    'bb': ['bb_position', 'bb_width_pct', 'dist_bb_upper', 'bb_upper_touch', 'bb_mid_rejection'],
    'rsi': ['rsi_value', 'rsi_slope', 'rsi_overbought'],
    'candle': ['body_size', 'upper_wick', 'lower_wick', 'wick_ratio', 
               'close_pos_in_candle', 'upper_rejection', 'lower_high',
               'atr_norm', 'ema_50_slope', 'price_below_ema50',
               'candle_vs_bb', 'body_vs_bb']
}