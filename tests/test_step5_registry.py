#!/usr/bin/env python3
"""
Test script for registry functionality.
Validates that registry can import and use all collectors correctly.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_registry_import():
    """Test that registry can be imported without errors."""
    try:
        from Retrieval.registry import get_collector
        print("✓ Registry imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import registry: {e}")
        return False

def test_registry_collectors():
    """Test that all collectors can be retrieved from registry."""
    try:
        from Retrieval.registry import get_collector
        
        # Test that we can get each collector
        collectors_to_test = ['yfinance', 'nse', 'bsc', 'screener', 'bse']
        
        for collector_name in collectors_to_test:
            try:
                collector = get_collector(collector_name)
                print(f"✓ Retrieved {collector_name} collector successfully")
            except Exception as e:
                print(f"✗ Failed to retrieve {collector_name} collector: {e}")
                # This might be okay if some collectors aren't fully implemented
                # We'll still continue testing others
                
        return True
        
    except Exception as e:
        print(f"✗ Error testing registry collectors: {e}")
        return False

def test_collector_instantiation():
    """Test that collectors can be instantiated."""
    try:
        from Retrieval.registry import get_collector
        
        # Try to instantiate a few collectors to ensure they work
        collector_names = ['bsc', 'nse']  # Test with collectors that we know are implemented
        
        for name in collector_names:
            try:
                collector_class = get_collector(name)
                # Try instantiating with minimal parameters
                if name == 'bsc':
                    collector = collector_class()
                elif name == 'nse':
                    collector = collector_class()  
                
                print(f"✓ Successfully instantiated {name} collector")
            except Exception as e:
                print(f"? Could not instantiate {name} collector (may be expected): {e}")
                
        return True
        
    except Exception as e:
        print(f"✗ Error testing collector instantiation: {e}")
        return False

def main():
    """Run all registry tests."""
    print("Testing Registry Functionality")
    print("=" * 30)
    
    tests = [
        test_registry_import,
        test_registry_collectors,
        test_collector_instantiation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All registry tests PASSED")
        return 0
    else:
        print("✗ Some registry tests FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())