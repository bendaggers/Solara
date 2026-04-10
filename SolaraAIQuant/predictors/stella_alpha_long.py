"""
Solara AI Quant - Stella Alpha Long Predictor

Multi-timeframe trend following LONG strategy.
Uses H4 + D1 confluence for entry signals.

Model Details:
- Algorithm: LightGBM
- Features: 25 (selected via RFE from ~215)
- Threshold: 0.45
- Direction: LONG only
- TP: 100 pips, SL: 50 pips
- Max Hold: 72 bars (12 days)
- Target: 1,179 pips/year

Signal Logic:
- H4 trend up (close > EMA21)
- D1 trend up (D1 close > D1 EMA21)
- Model probability >= 0.45
"""

from typing import List, Dict, Optional
import logging

import pandas as pd
import numpy as np

from .base_predictor import BasePredictor, PredictionSignal

logger = logging.getLogger(__name__)


class StellaAlphaLongPredictor(BasePredictor):
    """
    Stella Alpha Long - MTF Trend Following
    
    Trained on EURUSD H4 data with D1 confluence.
    Uses 25 features selected via RFE.
    """
    
    # Features selected by RFE during training
    SELECTED_FEATURES = [
        # RSI features
        'rsi_value',
        'rsi_slope_3',
        'rsi_slope_5',
        'rsi_percentile',
        
        # Bollinger Band features
        'bb_position',
        'bb_width_pct',
        'bb_touch_strength',
        
        # Trend features
        'trend_strength',
        'trend_direction',
        'ema_8',
        'ema_21',
        
        # Volatility
        'atr_pct',
        'atr_percentile',
        
        # Volume
        'volume_ratio',
        
        # Session
        'hour',
        'is_london_session',
        'is_ny_session',
        
        # D1 features
        'd1_rsi_value',
        'd1_bb_position',
        'd1_trend_strength',
        'd1_trend_direction',
        
        # Cross-timeframe
        'mtf_rsi_aligned',
        'mtf_trend_aligned',
        'mtf_confluence_score',
    ]
    
    def get_required_features(self) -> List[str]:
        """Return features required by this model."""
        return self.SELECTED_FEATURES.copy()
    
    def predict(
        self,
        df_features: pd.DataFrame,
        config
    ) -> List[Dict]:
        """
        Generate LONG predictions from features.
        
        Args:
            df_features: DataFrame with computed features
            config: ModelConfig
            
        Returns:
            List of prediction dictionaries
        """
        predictions = []
        
        # Check model loaded
        if not self.model_loaded or self.model is None:
            logger.warning(f"Model not loaded: {config.name}")
            return predictions
        
        # Filter to allowed symbols
        df = self.filter_by_symbols(df_features)
        
        if df.empty:
            logger.debug("No symbols to process after filtering")
            return predictions
        
        # Validate features
        if not self.validate_features(df, self.SELECTED_FEATURES):
            return predictions
        
        # Process each symbol
        for _, row in df.iterrows():
            try:
                signal = self._predict_row(row, config)
                if signal:
                    predictions.append(signal.to_dict())
            except Exception as e:
                logger.error(f"Error predicting for {row.get('symbol', 'unknown')}: {e}")
        
        if predictions:
            logger.info(f"Stella Alpha Long: {len(predictions)} signals generated")
        
        return predictions
    
    def _predict_row(
        self,
        row: pd.Series,
        config
    ) -> Optional[PredictionSignal]:
        """
        Generate prediction for a single row/symbol.
        
        Args:
            row: Series with feature values
            config: ModelConfig
            
        Returns:
            PredictionSignal or None
        """
        symbol = row.get('symbol', 'EURUSD')
        
        # 1. Check MTF alignment (pre-filter)
        # H4 trend should be up
        h4_trend_up = row.get('trend_direction', 0) > 0
        
        # D1 trend should be up  
        d1_trend_up = row.get('d1_trend_direction', 0) > 0
        
        # MTF confluence check
        mtf_aligned = row.get('mtf_trend_aligned', 0) == 1
        
        # Skip if trends not aligned
        if not (h4_trend_up and d1_trend_up):
            logger.debug(f"{symbol}: Trends not aligned (H4={h4_trend_up}, D1={d1_trend_up})")
            return None
        
        # 2. Prepare features for model
        try:
            X = self._prepare_features(row)
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return None
        
        # 3. Get model prediction
        try:
            # Handle different model types
            if hasattr(self.model, 'predict_proba'):
                # Scikit-learn style (LightGBM, RandomForest, etc.)
                proba = self.model.predict_proba(X)
                confidence = float(proba[0][1])  # Probability of class 1 (win)
            elif hasattr(self.model, 'predict'):
                # Direct prediction (might return probability)
                pred = self.model.predict(X)
                confidence = float(pred[0])
            else:
                logger.error("Model has no predict method")
                return None
        except Exception as e:
            logger.error(f"Model prediction error: {e}")
            return None
        
        # 4. Check threshold
        threshold = config.threshold or 0.45
        min_confidence = config.min_confidence or 0.45
        
        if confidence < min_confidence:
            logger.debug(f"{symbol}: Below min_confidence ({confidence:.3f} < {min_confidence})")
            return None
        
        if confidence < threshold:
            logger.debug(f"{symbol}: Below threshold ({confidence:.3f} < {threshold})")
            return None
        
        # 5. Create signal
        entry_price = row.get('close', row.get('price', 0))
        
        # Log key features for analysis
        key_features = {
            'rsi_value': float(row.get('rsi_value', 0)),
            'bb_position': float(row.get('bb_position', 0)),
            'trend_strength': float(row.get('trend_strength', 0)),
            'd1_trend_direction': float(row.get('d1_trend_direction', 0)),
            'mtf_confluence_score': float(row.get('mtf_confluence_score', 0)),
        }
        
        signal = self.create_signal(
            symbol=symbol,
            direction="LONG",
            confidence=confidence,
            entry_price=entry_price,
            features=key_features
        )
        
        logger.info(
            f"SIGNAL: {symbol} LONG @ {entry_price:.5f}, "
            f"confidence={confidence:.3f}, "
            f"RSI={key_features['rsi_value']:.1f}, "
            f"MTF={key_features['mtf_confluence_score']:.2f}"
        )
        
        return signal
    
    def _prepare_features(self, row: pd.Series) -> np.ndarray:
        """
        Prepare feature array for model input.
        
        Args:
            row: Series with feature values
            
        Returns:
            2D numpy array (1, n_features)
        """
        features = []
        
        for feat in self.SELECTED_FEATURES:
            value = row.get(feat, 0)
            
            # Handle NaN/inf
            if pd.isna(value) or np.isinf(value):
                value = 0
            
            features.append(float(value))
        
        return np.array([features])
    
    def get_metadata(self) -> Dict:
        """Get predictor metadata."""
        base = super().get_metadata()
        base.update({
            'strategy': 'MTF Trend Following',
            'direction': 'LONG',
            'n_features': len(self.SELECTED_FEATURES),
            'expected_annual_pips': 1179,
            'expected_trades_per_year': 154,
        })
        return base
