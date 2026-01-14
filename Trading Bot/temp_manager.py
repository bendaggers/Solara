import tempfile
import shutil
import os
import time

class TempMarketData:
    def __init__(self, original_path):
        self.original_path = original_path
        self.temp_path = None
        
    def create_temp_copy(self):
        """Create unique temp file copy"""
        timestamp = int(time.time())
        random_id = os.urandom(4).hex()
        temp_name = f"marketdata_{timestamp}_{random_id}.json"
        
        self.temp_path = os.path.join(
            os.path.dirname(self.original_path),
            temp_name
        )
        
        # Copy file
        shutil.copy2(self.original_path, self.temp_path)
        return self.temp_path
    
    def cleanup(self):
        """Delete temp file"""
        if self.temp_path and os.path.exists(self.temp_path):
            try:
                os.remove(self.temp_path)
            except:
                pass