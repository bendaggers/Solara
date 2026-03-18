#!/usr/bin/env python3
"""
Simple script to fix mt5_manager.py
"""
import sys

# Read the file
with open('mt5/mt5_manager.py', 'r') as f:
    content = f.read()

# The exact text we want to replace
old_text = '''        initialized = mt5.initialize(
            path=str(config.MT5_TERMINAL_PATH),
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        )
        if not initialized:
            log.error("mt5_init_failed", error=mt5.last_error())
            return False'''

new_text = '''        # Try without path first (connects to running instance)
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
            return False'''

# Replace
if old_text in content:
    content = content.replace(old_text, new_text)
    with open('mt5/mt5_manager.py', 'w') as f:
        f.write(content)
    print('[OK] Fixed mt5_manager.py')
    sys.exit(0)
else:
    print('[ERROR] Could not find the text to replace')
    sys.exit(1)