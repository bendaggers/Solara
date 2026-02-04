"""
Volume Manager - Calculates trade volume based on confidence levels.
"""

class VolumeManager:
    """
    Simple volume calculator for trading signals.
    Maps confidence levels to volume sizes.
    """
    
    def __init__(self):
        """
        Initialize with default volume rules.
        Rules format: (min_threshold, volume)
        """
        # Your exact rules from the requirements
        self.volume_rules = [
            (0.95, 0.05),  # > 95% = 0.05
            (0.90, 0.04),  # 90-95% = 0.04  
            (0.86, 0.03),  # 86-90% = 0.03
            (0.81, 0.02),  # 81-85% = 0.02
            (0.75, 0.01),  # 75-80% = 0.01
        ]
        # Sorted highest to lowest for efficient lookup
    
    def calculate_volume(self, confidence):
        """
        Calculate volume for a single confidence value.
        
        Args:
            confidence (float): Prediction confidence (0.0 to 1.0)
            
        Returns:
            float: Volume size (0.00 to 0.05)
                  Returns 0.0 if confidence < 0.75
        """
        # Convert to float and clamp between 0-1
        try:
            conf = float(confidence)
            if conf < 0 or conf > 1:
                return 0.0  # Invalid confidence
        except (ValueError, TypeError):
            return 0.0  # Invalid input
        
        # Apply rules (check from highest threshold down)
        for threshold, volume in self.volume_rules:
            if conf >= threshold:
                return volume
        
        # Confidence below 0.75 gets no volume
        return 0.0