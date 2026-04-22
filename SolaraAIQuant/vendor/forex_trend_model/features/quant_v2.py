"""Quant V2 Feature Set — 41 expert features for the universal trend model."""

import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def compute_adx_system(high, low, close, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    up_move, down_move = high.diff(), -low.diff()
    plus_dm  = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=close.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=close.index)
    atr_w    = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_w.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_w.replace(0, np.nan)
    dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val  = dx.ewm(alpha=1/period, adjust=False).mean()
    total_di = plus_di + minus_di
    out = pd.DataFrame(index=close.index)
    out[f'adx_{period}']       = adx_val.fillna(0) / 100.0
    out[f'plus_di_{period}']   = plus_di.fillna(0) / 100.0
    out[f'minus_di_{period}']  = minus_di.fillna(0) / 100.0
    out[f'di_spread_{period}'] = ((plus_di - minus_di) / total_di.replace(0, np.nan)).fillna(0)
    return out


def compute_ema_alignment(close, atr, periods=None):
    if periods is None:
        periods = [8, 21, 50, 200]
    out, emas = pd.DataFrame(index=close.index), {}
    for p in periods:
        emas[p] = close.ewm(span=p, adjust=False).mean()
        out[f'price_vs_ema_{p}'] = (close - emas[p]) / atr.replace(0, np.nan)
    for fast, slow in [(8, 21), (21, 50), (50, 200)]:
        if fast in emas and slow in emas:
            out[f'ema_{fast}_vs_{slow}'] = (emas[fast] - emas[slow]) / atr.replace(0, np.nan)
    for p in [8, 21, 50]:
        if p in emas:
            out[f'ema_slope_{p}'] = ((emas[p] - emas[p].shift(5)) / 5) / atr.replace(0, np.nan)
    return out


def compute_rsi_multi(close, periods=None):
    if periods is None:
        periods = [7, 14, 21]
    out = pd.DataFrame(index=close.index)
    for period in periods:
        delta = close.diff()
        avg_gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
        avg_loss = (-delta).clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        out[f'rsi_{period}'] = (100 - (100 / (1 + rs))).fillna(50) / 100.0
    return out


def compute_stochastic(close, high, low, k_period=14, d_period=3):
    low_n, high_n = low.rolling(k_period).min(), high.rolling(k_period).max()
    hl = high_n - low_n
    k  = ((close - low_n) / hl.replace(0, np.nan) * 100).fillna(50)
    d  = k.rolling(d_period).mean()
    out = pd.DataFrame(index=close.index)
    out[f'stoch_k_{k_period}'] = k / 100.0
    out[f'stoch_d_{k_period}'] = d / 100.0
    out['stoch_kd_cross']      = (k - d) / 100.0
    return out


def compute_cci(high, low, close, period=14):
    typical = (high + low + close) / 3
    sma_tp  = typical.rolling(period).mean()
    mad     = typical.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci_val = (typical - sma_tp) / (0.015 * mad.replace(0, np.nan))
    return (cci_val / 200.0).clip(-1, 1).rename(f'cci_{period}')


def compute_williams_r(high, low, close, period=14):
    high_n, low_n = high.rolling(period).max(), low.rolling(period).min()
    wr = ((high_n - close) / (high_n - low_n).replace(0, np.nan) * 100).fillna(50)
    return (wr / 100.0).rename(f'williams_r_{period}')


def compute_roc(close, n=10):
    return ((close / close.shift(n) - 1) * 100).clip(-20, 20).rename(f'roc_{n}')


def compute_macd_family(close, atr, fast=12, slow=26, signal=9):
    ema_f     = close.ewm(span=fast, adjust=False).mean()
    ema_s     = close.ewm(span=slow, adjust=False).mean()
    macd_line = (ema_f - ema_s) / atr.replace(0, np.nan)
    sig_line  = macd_line.ewm(span=signal, adjust=False).mean()
    hist      = macd_line - sig_line
    out = pd.DataFrame(index=close.index)
    out['macd_line']       = macd_line
    out['macd_signal']     = sig_line
    out['macd_hist']       = hist
    out['macd_hist_slope'] = hist - hist.shift(3)
    return out


def compute_volatility_features_v2(close, high, low, atr):
    out = pd.DataFrame(index=close.index)
    out['atr_pct']        = atr / close.replace(0, np.nan) * 100
    out['vol_regime_pct'] = atr.rolling(100).rank(pct=True)
    sma20, std20 = close.rolling(20).mean(), close.rolling(20).std()
    out['bb_width_20'] = (4 * std20 / sma20.replace(0, np.nan))
    upper, lower = sma20 + 2 * std20, sma20 - 2 * std20
    out['bb_position']     = ((close - lower) / (upper - lower).replace(0, np.nan)).clip(0, 1)
    out['realized_vol_20'] = np.log(close / close.shift(1)).rolling(20).std() * 100
    out['vol_expansion']   = atr / atr.rolling(20).mean().replace(0, np.nan)
    ema20   = close.ewm(span=20, adjust=False).mean()
    k_upper = ema20 + 2 * atr
    k_lower = ema20 - 2 * atr
    out['keltner_position'] = ((close - k_lower) / (k_upper - k_lower).replace(0, np.nan)).clip(0, 1)
    return out


def compute_price_structure_v2(close, high, low, atr):
    out = pd.DataFrame(index=close.index)
    for n in [1, 3, 5, 10, 20]:
        out[f'log_return_{n}'] = (np.log(close / close.shift(n)) / atr.replace(0, np.nan)).clip(-5, 5)
    hl = high - low
    out['close_location']    = ((close - low) / hl.replace(0, np.nan)).clip(0, 1)
    high_20, low_20 = high.rolling(20).max(), low.rolling(20).min()
    out['range_position_20'] = ((close - low_20) / (high_20 - low_20).replace(0, np.nan)).clip(0, 1)
    x = np.arange(20)
    def _slope(y):
        return np.nan if np.isnan(y).any() else np.polyfit(x, y, 1)[0]
    raw_slope = close.rolling(20).apply(_slope, raw=True)
    out['regression_slope_20'] = (raw_slope / atr.replace(0, np.nan)).clip(-5, 5)
    return out


def compute_market_structure_v2(close, high, low):
    out = pd.DataFrame(index=close.index)
    for n in [10, 20]:
        net  = (close - close.shift(n)).abs()
        path = close.diff().abs().rolling(n).sum()
        out[f'efficiency_ratio_{n}'] = (net / path.replace(0, np.nan)).fillna(0)
    prev_close = close.shift(1)
    tr1 = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    tr_sum = tr1.rolling(14).sum()
    hl14   = high.rolling(14).max() - low.rolling(14).min()
    ci = 100 * np.log10(tr_sum / hl14.replace(0, np.nan)) / np.log10(14)
    out['choppiness_14'] = (ci.fillna(50) / 100.0).clip(0, 1)
    period = 25
    high_idx = high.rolling(period + 1).apply(lambda x: x.argmax(), raw=True)
    low_idx  = low.rolling(period + 1).apply(lambda x: x.argmin(), raw=True)
    out['aroon_osc_25'] = ((high_idx / period * 100 - low_idx / period * 100) / 100.0).fillna(0)
    return out


def compute_volume_features(close, volume):
    out = pd.DataFrame(index=close.index)
    if volume.isna().all():
        out['vol_ratio_20'] = 1.0
        out['obv_slope_10'] = 0.0
        return out
    avg_vol = volume.rolling(20).mean()
    out['vol_ratio_20'] = (volume / avg_vol.replace(0, np.nan)).clip(0, 10).fillna(1)
    obv = (np.sign(close.diff()) * volume).cumsum()
    out['obv_slope_10'] = ((obv - obv.shift(10)) / 10).clip(-1e6, 1e6).fillna(0)
    return out


QUANT_V2_FEATURES = [
    'adx_14', 'plus_di_14', 'minus_di_14', 'di_spread_14',
    'price_vs_ema_8', 'price_vs_ema_21', 'price_vs_ema_50', 'price_vs_ema_200',
    'ema_8_vs_21', 'ema_21_vs_50', 'ema_50_vs_200',
    'ema_slope_8', 'ema_slope_21', 'ema_slope_50',
    'rsi_7', 'rsi_14', 'rsi_21',
    'stoch_k_14', 'stoch_d_14', 'stoch_kd_cross',
    'cci_14', 'williams_r_14', 'roc_10',
    'macd_line', 'macd_signal', 'macd_hist', 'macd_hist_slope',
    'atr_pct', 'vol_regime_pct', 'bb_width_20', 'bb_position',
    'realized_vol_20', 'vol_expansion', 'keltner_position',
    'log_return_1', 'log_return_3', 'log_return_5', 'log_return_10', 'log_return_20',
    'close_location', 'range_position_20', 'regression_slope_20', 'open_gap_pct',
    'efficiency_ratio_10', 'efficiency_ratio_20', 'choppiness_14', 'aroon_osc_25',
    'vol_ratio_20', 'obv_slope_10',
    'tf_log_minutes', 'pair_encoded', 'base_ccy_encoded', 'quote_ccy_encoded',
]

QUANT_V2_CORE = [
    'adx_14', 'di_spread_14',
    'price_vs_ema_8', 'price_vs_ema_21', 'price_vs_ema_50',
    'ema_8_vs_21', 'ema_21_vs_50', 'ema_slope_8', 'ema_slope_21',
    'rsi_7', 'rsi_14', 'stoch_k_14', 'stoch_kd_cross', 'cci_14', 'roc_10',
    'macd_hist', 'macd_hist_slope',
    'atr_pct', 'vol_regime_pct', 'bb_width_20', 'bb_position',
    'realized_vol_20', 'vol_expansion',
    'log_return_1', 'log_return_3', 'log_return_5', 'log_return_10', 'log_return_20',
    'close_location', 'range_position_20', 'regression_slope_20', 'open_gap_pct',
    'efficiency_ratio_10', 'efficiency_ratio_20', 'choppiness_14', 'aroon_osc_25',
    'vol_ratio_20',
    'tf_log_minutes', 'pair_encoded', 'base_ccy_encoded', 'quote_ccy_encoded',
]


def compute_quant_v2_features(df: pd.DataFrame, timeframe: str, atr, feature_subset: str = 'core') -> pd.DataFrame:
    from .pipeline import TIMEFRAME_MINUTES, encode_timeframe

    close  = df['close']
    high   = df['high']
    low    = df['low']
    volume = df.get('tick_volume', pd.Series(np.nan, index=df.index))

    adx_feats   = compute_adx_system(high, low, close, period=14)
    ema_feats   = compute_ema_alignment(close, atr, periods=[8, 21, 50, 200])
    rsi_feats   = compute_rsi_multi(close, periods=[7, 14, 21])
    stoch_feats = compute_stochastic(close, high, low, k_period=14, d_period=3)
    cci_feat    = compute_cci(high, low, close, period=14).to_frame()
    wr_feat     = compute_williams_r(high, low, close, period=14).to_frame()
    roc_feat    = compute_roc(close, n=10).to_frame()
    macd_feats  = compute_macd_family(close, atr)
    vol_feats   = compute_volatility_features_v2(close, high, low, atr)
    price_feats = compute_price_structure_v2(close, high, low, atr)
    struct_feat = compute_market_structure_v2(close, high, low)
    volume_feat = compute_volume_features(close, volume)

    open_col = df['open'] if 'open' in df.columns else close
    open_gap = ((open_col - close.shift(1)) / atr.replace(0, np.nan)).clip(-5, 5)
    open_gap_feat = pd.Series(open_gap.fillna(0).values, index=df.index, name='open_gap_pct')

    tf_minutes = TIMEFRAME_MINUTES.get(timeframe, 240)
    tf_feat = pd.Series(np.full(len(df), np.log(tf_minutes)), index=df.index, name='tf_log_minutes')

    all_feats = pd.concat([
        adx_feats, ema_feats, rsi_feats, stoch_feats,
        cci_feat, wr_feat, roc_feat,
        macd_feats, vol_feats, price_feats,
        struct_feat, volume_feat,
        tf_feat.to_frame(), open_gap_feat.to_frame(),
    ], axis=1)

    for col in ('pair_encoded', 'base_ccy_encoded', 'quote_ccy_encoded'):
        if col not in all_feats.columns:
            all_feats[col] = 0

    target_cols = QUANT_V2_CORE if feature_subset == 'core' else QUANT_V2_FEATURES
    available   = [c for c in target_cols if c in all_feats.columns]
    all_feats   = all_feats[available]

    warmup = 200
    feature_valid = pd.Series(True, index=df.index)
    feature_valid.iloc[:warmup] = False
    for flag_col in ('is_weekend_gap', 'is_missing'):
        if flag_col in df.columns:
            feature_valid = feature_valid & (~df[flag_col])
    feature_valid = feature_valid & (~all_feats.isnull().any(axis=1))

    all_feats['feature_valid'] = feature_valid
    all_feats['atr']           = atr.values

    logger.info(
        f"V2 features computed: {feature_valid.sum()}/{len(df)} valid rows | "
        f"subset={feature_subset} | n_features={len(available)}"
    )
    return all_feats


def get_quant_v2_feature_names(subset: str = 'core') -> list:
    if subset == 'core':
        return QUANT_V2_CORE.copy()
    elif subset == 'full':
        return QUANT_V2_FEATURES.copy()
    raise ValueError(f"Unknown subset '{subset}'. Use 'core' or 'full'.")
