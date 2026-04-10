#!/usr/bin/env python3
"""
Quick fix for MT5 manager to connect without path parameter
"""
import sys
import os

# Read the mt5_manager.py file
with open('mt5/mt5_manager.py', 'r') as f:
    content = f.read()

# Find and replace the connect method
old_connect = '''    def connect(self) -> bool:
        """Initialize and connect to MT5 terminal."""
        if not MT5_AVAILABLE:
            log.warning("mt5_stub_mode", message="MT5 not available — stub mode active")
            self._connected = True   # allow dev testing without MT5
            return True

        initialized = mt5.initialize(
            path=str(config.MT5_TERMINAL_PATH),
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        )
        if not initialized:
            log.error("mt5_init_failed", error=mt5.last_error())
            return False

        self._connected = True
        return True'''

new_connect = '''    def connect(self) -> bool:
        """Initialize and connect to MT5 terminal."""
        if not MT5_AVAILABLE:
            log.warning("mt5_stub_mode", message="MT5 not available — stub mode active")
            self._connected = True   # allow dev testing without MT5
            return True

        # Try without path first (connects to running instance)
        # If that fails, try with path (starts new instance)
        initialized = mt5.initialize(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        )
        
        if not initialized:
            # Try with path as fallback
            initialized = mt5.initialize(
                path=str(config.MT5_TERMINAL_PATH),
                login=config.MT5_LOGIN,
                password=config.MT5_PASSWORD,
                server=config.MT5_SERVER,
            )
        
        if not initialized:
            log.error("mt5_init_failed", error=mt5.last_error())
            return False

        self._connected = True
        return True'''

# Replace the old connect method with the new one
content = content.replace(old_connect, new_connect)

# Write the updated content back
with open('mt5/mt5_manager.py', 'w') as f:
    f.write(content)

print('✅ Fixed mt5_manager.py - now tries to connect without path first')