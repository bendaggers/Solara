"""
labels.py - FIXED VERSION

Triple-Barrier labeling for OHLC data.

FIX #4: Use next-bar open as entry price to eliminate look-ahead bias.
Previously used current bar's close as entry price, which assumes you can
enter a trade at the close price of the signal bar - this is unrealistic.
In practice, the earliest you can enter is the NEXT bar's open.
"""

import numpy as np
import pandas as pd

class TripleBarrierLabeler:
    """
    Triple-Barrier labeling for OHLC data.
    Labels trades based on:
      - Take-Profit (TP) in pips
      - Stop-Loss (SL) in pips
      - Maximum holding period in bars
    
    FIXED: Now uses next-bar open as entry price by default.
    
    Assumes forex data where 1 pip = 0.0001 for most pairs.
    Adjust pip_factor for JPY pairs or other cases.
    """
    
    def __init__(self, tp_pips=None, sl_pips=None, max_bars=None, pip_factor=0.0001):
        """
        Parameters:
        -----------
        tp_pips : int
            Take-profit in pips
        sl_pips : int
            Stop-loss in pips
        max_bars : int
            Maximum holding period in bars
        pip_factor : float
            Multiplier to convert pips to price change.
            Default 0.0001 for EUR/USD, GBP/USD, etc.
            Use 0.01 for JPY pairs (e.g., USD/JPY).
        """
        self.tp_pips = tp_pips
        self.sl_pips = sl_pips
        self.max_bars = max_bars
        self.pip_factor = pip_factor
        
        # Convert pips to price units
        self.tp_distance = self.tp_pips * pip_factor
        self.sl_distance = self.sl_pips * pip_factor
    
    def _create_next_bar_open(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create next_bar_open column if it doesn't exist.
        This is the realistic entry price - you see a signal on bar N,
        and enter the trade at bar N+1's open.
        """
        df = df.copy()
        if 'next_bar_open' not in df.columns:
            df['next_bar_open'] = df['open'].shift(-1)
        return df
        
    def label_short_entries(self, df, entry_price_col='next_bar_open'):
        """
        Generates triple-barrier labels for SHORT entries.
        
        FIXED: Default entry_price_col is now 'next_bar_open' to avoid look-ahead bias.
        
        The logic:
        - Signal detected at bar i (based on features of bar i)
        - Entry at bar i+1's open (next_bar_open)
        - Look ahead from bar i+2 onwards for TP/SL hits
        - If entry_price_col='next_bar_open', lookahead starts at i+2
          (because we enter at i+1 open, and i+1's high/low could trigger
          before we actually enter at open - conservative approach starts at i+2)
        
        For backward compatibility, if entry_price_col='close', behavior is
        the same as before (but this introduces look-ahead bias).
        """
        # Create next_bar_open if needed
        df = self._create_next_bar_open(df)
        
        required = ['open', 'high', 'low', 'close', entry_price_col]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing columns in df: {missing}")
        
        labels = pd.Series(0, index=df.index, dtype=int)
        
        # Determine lookahead offset based on entry price column
        # If using next_bar_open: signal at i, entry at i+1 open, 
        # so first full bar to check is i+2 (bar i+1 open is our entry, 
        # but i+1 high/low could trigger before we enter at open)
        # Conservative: start checking from i+2
        if entry_price_col == 'next_bar_open':
            lookahead_offset = 2  # Skip the entry bar itself
        else:
            lookahead_offset = 1  # Original behavior
        
        for i in range(len(df) - lookahead_offset):
            entry_price = df[entry_price_col].iloc[i]
            
            # Skip if entry price is NaN (last row for next_bar_open)
            if pd.isna(entry_price):
                labels.iloc[i] = 0
                continue
            
            max_lookahead = min(self.max_bars, len(df) - i - lookahead_offset)
            
            if max_lookahead <= 0:
                labels.iloc[i] = 0
                continue
            
            tp_hit = False
            sl_hit = False
            
            # Calculate barrier levels for SHORT
            tp_level = entry_price - self.tp_distance  # SHORT TP is below entry
            sl_level = entry_price + self.sl_distance  # SHORT SL is above entry
            
            for j in range(lookahead_offset, max_lookahead + lookahead_offset):
                idx = i + j
                if idx >= len(df):
                    break
                    
                future_open = df['open'].iloc[idx]
                future_high = df['high'].iloc[idx]
                future_low = df['low'].iloc[idx]
                
                # Check if barriers were touched this bar
                tp_touched = future_low <= tp_level
                sl_touched = future_high >= sl_level
                
                if tp_touched and sl_touched:
                    # BOTH hit in same bar - use proximity to open as tiebreaker
                    dist_to_tp = abs(future_open - tp_level)
                    dist_to_sl = abs(future_open - sl_level)
                    
                    if dist_to_tp < dist_to_sl:
                        tp_hit = True
                    else:
                        sl_hit = True
                    break
                    
                elif tp_touched:
                    tp_hit = True
                    break
                    
                elif sl_touched:
                    sl_hit = True
                    break
            
            labels.iloc[i] = 1 if tp_hit else 0
        
        return labels      
    
    def label_long_entries(self, df, entry_price_col='next_bar_open'):
        """
        Triple-barrier labeling for LONG entries.
        TP = price increase, SL = price decrease.
        
        FIXED: Default entry_price_col is now 'next_bar_open'.
        """
        # Create next_bar_open if needed
        df = self._create_next_bar_open(df)
        
        labels = pd.Series(0, index=df.index, dtype=int)
        
        if entry_price_col == 'next_bar_open':
            lookahead_offset = 2
        else:
            lookahead_offset = 1
        
        for i in range(len(df) - lookahead_offset):
            entry_price = df[entry_price_col].iloc[i]
            
            if pd.isna(entry_price):
                labels.iloc[i] = 0
                continue
            
            max_lookahead = min(self.max_bars, len(df) - i - lookahead_offset)
            
            if max_lookahead <= 0:
                labels.iloc[i] = 0
                continue
            
            tp_hit = False
            sl_hit = False
            
            # Calculate barrier levels for LONG
            tp_level = entry_price + self.tp_distance  # LONG TP is above entry
            sl_level = entry_price - self.sl_distance  # LONG SL is below entry
            
            for j in range(lookahead_offset, max_lookahead + lookahead_offset):
                idx = i + j
                if idx >= len(df):
                    break
                
                future_open = df['open'].iloc[idx]
                future_high = df['high'].iloc[idx]
                future_low = df['low'].iloc[idx]
                
                tp_touched = future_high >= tp_level
                sl_touched = future_low <= sl_level
                
                if tp_touched and sl_touched:
                    dist_to_tp = abs(future_open - tp_level)
                    dist_to_sl = abs(future_open - sl_level)
                    
                    if dist_to_tp < dist_to_sl:
                        tp_hit = True
                    else:
                        sl_hit = True
                    break
                    
                elif tp_touched:
                    tp_hit = True
                    break
                    
                elif sl_touched:
                    sl_hit = True
                    break
            
            labels.iloc[i] = 1 if tp_hit else 0
        
        return labels