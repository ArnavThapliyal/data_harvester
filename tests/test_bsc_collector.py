#!/usr/bin/env python3
"""
Test script for BSC collector implementation.
This test validates that the BSCCollector class properly implements 
the BaseNumericCollector interface.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_bsc_collector_import():
    """Test that BSC collector can be imported without errors."""
    try:
        from Retrieval.Numeric.bsc_collector import BSCCollector
        print("✓ BSCCollector imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import BSCCollector: {e}")
        return False

def test_bsc_collector_interface():
    """Test that BSC collector implements BaseNumericCollector interface."""
    try:
        from Retrieval.Numeric.bsc_collector import BSCCollector
        from Retrieval.Numeric.base_numeric_collector import BaseNumericCollector
        
        # Check if it inherits from BaseNumericCollector
        if issubclass(BSCCollector, BaseNumericCollector):
            print("✓ BSCCollector correctly inherits from BaseNumericCollector")
        else:
            print("✗ BSCCollector does not inherit from BaseNumericCollector")
            return False
            
        # Check required class attributes
        required_attrs = ['SOURCE_NAME', 'BASE_URL', 'BATCH_SIZE', 'MAX_RETRIES', 'OUTPUT_COLUMNS']
        collector = BSCCollector()
        
        for attr in required_attrs:
            if hasattr(collector, attr):
                print(f"✓ BSCCollector has {attr}: {getattr(collector, attr)}")
            else:
                print(f"✗ BSCCollector missing required attribute: {attr}")
                return False
                
        print("✓ All required attributes present")
        return True
        
    except Exception as e:
        print(f"✗ Error testing BSC collector interface: {e}")
        return False

def test_bsc_collector_methods():
    """Test that BSC collector has all required abstract methods implemented."""
    try:
        from Retrieval.Numeric.bsc_collector import BSCCollector
        
        # Create instance
        collector = BSCCollector()
        
        # Check for all abstract methods that should be implemented
        required_methods = ['build_request', 'fetch_batch', 'parse_response', 'normalize_record']
        
        for method in required_methods:
            if hasattr(collector, method) and callable(getattr(collector, method)):
                print(f"✓ BSCCollector implements {method}")
            else:
                print(f"✗ BSCCollector missing method: {method}")
                return False
                
        print("✓ All required methods implemented")
        return True
        
    except Exception as e:
        print(f"✗ Error testing BSC collector methods: {e}")
        return False

def main():
    """Run all tests for BSC collector."""
    print("Testing BSC Collector Implementation")
    print("=" * 40)
    
    tests = [
        test_bsc_collector_import,
        test_bsc_collector_interface, 
        test_bsc_collector_methods
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All BSC collector tests PASSED")
        return 0
    else:
        print("✗ Some BSC collector tests FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())