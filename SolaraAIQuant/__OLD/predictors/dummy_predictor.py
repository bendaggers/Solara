"""
predictors/dummy_predictor.py — Dummy Random Predictor for Testing
===================================================================
A simple predictor that randomly generates signals for testing the SAQ pipeline.
No ML model required — just random signal generation.
"""
import random
import pandas as pd
import structlog
from predictors.base_predictor import BasePredictor
from signals.signal_models import RawSignal

log = structlog.get_logger(__name__)

# Features that would be available in v3 feature set
DUMMY_FEATURE_LIST = [
    "ret", "ret_lag1", "ret_lag2", "ret_lag3",
    "body_size", "candle_body_pct",
    "rsi_value", "rsi_slope", "rsi_slope_lag1", "rsi_slope_lag2",
    "rsi_slope_lag3", "RSI_slope_3",
    "dist_bb_upper", "dist_bb_lower",
    "dist_bb_upper_lag1", "dist_bb_upper_lag2", "dist_bb_upper_lag3",
    "price_momentum",
]


class DummyRandomPredictor(BasePredictor):
    """
    Dummy predictor for testing SAQ pipeline.
    
    Features:
    - Randomly selects 0-2 symbols from available data
    - Generates random confidence between min_confidence and 1.0
    - Respects model_type (LONG/SHORT) from registry
    - Can be configured for any timeframe
    - No .pkl file required
    """
    
    def __init__(self, entry) -> None:
        super().__init__(entry)
        # Don't try to load a model file for dummy predictor
        # Just log that we're using dummy mode
        log.info("dummy_predictor_loaded", 
                 model=entry.name, 
                 model_type=entry.model_type,
                 timeframe=entry.timeframe,
                 dummy_mode=True)
        
    def get_feature_list(self) -> list[str]:
        """Return the feature list this 'model' expects."""
        return DUMMY_FEATURE_LIST
    
    def predict(self, featured_df: pd.DataFrame) -> list[RawSignal]:
        """
        Generate random signals for testing.
        
        Logic:
        1. Randomly select 0-2 symbols from available data
        2. Generate random confidence above min_confidence
        3. Create signals based on model_type (LONG/SHORT)
        """
        signals = []
        
        if featured_df.empty:
            return signals
        
        # Get available symbols
        available_symbols = featured_df["symbol"].unique().tolist()
        
        if not available_symbols:
            return signals
        
        # Randomly decide how many signals to generate (0, 1, or 2)
        num_signals = random.choices([0, 1, 2], weights=[0.3, 0.5, 0.2])[0]
        
        # Randomly select symbols (without replacement)
        selected_symbols = random.sample(available_symbols, 
                                        min(num_signals, len(available_symbols)))
        
        for symbol in selected_symbols:
            # Get the row for this symbol
            symbol_row = featured_df[featured_df["symbol"] == symbol].iloc[0]
            
            # Generate random confidence between min_confidence and 1.0
            min_conf = self._entry.min_confidence
            confidence = random.uniform(min_conf, 1.0)
            
            # Get price from the data
            price = float(symbol_row.get("price", symbol_row.get("close", 1.0)))
            
            # Create signal based on model_type
            signals.append(RawSignal(
                symbol=str(symbol),
                direction=self._entry.model_type,  # "LONG" or "SHORT"
                confidence=confidence,
                model_name=self._entry.name,
                model_type=self._entry.model_type,
                timeframe=self._entry.timeframe,
                magic=self._entry.magic,
                weight=self._entry.weight,
                price=price,
                comment=f"{self._entry.comment} {confidence:.2f} (DUMMY)",
            ))
            
            log.debug("dummy_signal_generated",
                     symbol=symbol,
                     direction=self._entry.model_type,
                     confidence=confidence,
                     model=self._entry.name)
        
        log.info("dummy_predictor_completed",
                model=self._entry.name,
                signals_generated=len(signals),
                symbols=selected_symbols if signals else [])
        
        return signals