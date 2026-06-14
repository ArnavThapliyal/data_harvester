#!/usr/bin/env python3
"""Debug script to test imports."""

import sys
import os

# Add the current directory to Python path if not already there
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

print("Python path:")
for p in sys.path[:5]:  # Show first 5 entries
    print(f"  {p}")

try:
    print("\nTrying to import Retrieval.registry...")
    from Retrieval.registry import get_collector
    print("SUCCESS: Import was successful!")
    
    # Test that we can create collectors
    collector = get_collector('yfinance')
    print(f"SUCCESS: Created YFinanceCollector: {collector}")
    
except Exception as e:
    print(f"FAILED to import: {e}")
    import traceback
    traceback.print_exc()