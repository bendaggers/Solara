"""
Volume Manager - Calculates trade volume based on confidence levels.
"""

class VolumeManager:
    """
    Simple volume calculator for trading signals.
    Maps confidence levels to volume sizes.
    """
    
    def __init__(self, predictor_config=None, magic=None):
        """
        Initialize volume manager.
        
        Args:
            predictor_config (dict): Predictor configuration dict
            magic (int): Magic number to identify predictor
        """
        # Load predictor configs
        from config import PREDICTOR_CONFIGS
        
        # Find predictor config
        config = None
        if predictor_config:
            config = predictor_config
        elif magic:
            for cfg in PREDICTOR_CONFIGS:
                if cfg.get('magic') == magic:
                    config = cfg
                    break
        
        # Get volume rules from config
        if config and 'volume_matrix' in config:
            # Use custom volume matrix from predictor config
            volume_rules = config['volume_matrix']
            if volume_rules == 'default' or volume_rules is None:
                self.volume_rules = self.get_default_rules()
            else:
                # Validate and use custom matrix
                self.volume_rules = self._validate_volume_matrix(volume_rules)
        else:
            # No custom matrix, use default
            self.volume_rules = self.get_default_rules()
        
        # Sort highest to lowest for efficient lookup
        self.volume_rules = sorted(self.volume_rules, key=lambda x: x[0], reverse=True)
    
    @staticmethod
    def get_default_rules():
        """Return default volume rules."""
        return [
            (0.95, 0.05),  # > 95% = 0.05
            (0.90, 0.04),  # 90-95% = 0.04  
            (0.86, 0.03),  # 86-90% = 0.03
            (0.81, 0.02),  # 81-85% = 0.02
            (0.75, 0.01),  # 75-80% = 0.01
        ]
    
    def _validate_volume_matrix(self, matrix):
        """
        Validate and normalize volume matrix.
        
        Handles edge cases like (0, 0.1) for all confidence levels.
        
        Args:
            matrix: List of (threshold, volume) tuples
            
        Returns:
            List: Validated and potentially modified matrix
        """
        if not matrix or not isinstance(matrix, list):
            return self.get_default_rules()
        
        # Check for single threshold of 0 (match all)
        if len(matrix) == 1 and matrix[0][0] == 0:
            # For (0, 0.1) case, return as is but add high threshold for sorting
            return [(0, matrix[0][1])]
        
        # Validate all entries
        validated = []
        for threshold, volume in matrix:
            try:
                t = float(threshold)
                v = float(volume)
                if 0 <= t <= 1 and v >= 0:
                    validated.append((t, v))
            except (ValueError, TypeError):
                continue
        
        if not validated:
            return self.get_default_rules()
        
        return validated
    
    def calculate_volume(self, confidence):
        """
        Calculate volume for a single confidence value.
        
        Args:
            confidence (float): Prediction confidence (0.0 to 1.0)
            
        Returns:
            float: Volume size (0.00 to max from rules)
                  Returns 0.0 if confidence below lowest threshold
        """
        # Validate input
        try:
            conf = float(confidence)
            if conf < 0 or conf > 1:
                return 0.0
        except (ValueError, TypeError):
            return 0.0
        
        # Special case: single threshold of 0 matches all
        if len(self.volume_rules) == 1 and self.volume_rules[0][0] == 0:
            if conf >= 0:  # Always true
                return self.volume_rules[0][1]
            return 0.0
        
        # Normal case: check thresholds
        for threshold, volume in self.volume_rules:
            if conf >= threshold:
                return volume
        
        return 0.0