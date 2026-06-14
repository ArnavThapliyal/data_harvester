#!/usr/bin/env python3
"""
Comprehensive test script for all numeric collectors.
This validates that all collector classes properly implement 
the BaseNumericCollector interface.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_collector_imports():
    """Test that all collector modules can be imported without errors."""
    collectors = [
        'yfinance_collector',
        'nse_collector', 
        'bsc_collector',
        'screener_collector',
        'bse_collector'
    ]
    
    print("Testing Collector Imports")
    print("-" * 30)
    
    all_passed = True
    for collector in collectors:
        try:
            module = f"Retrieval.Numeric.{collector}"
            __import__(module)
            print(f"✓ {collector} imported successfully")
        except Exception as e:
            print(f"✗ Failed to import {collector}: {e}")
            all_passed = False
    
    return all_passed

def test_collector_interface(collector_name, collector_class):
    """Test that a specific collector implements BaseNumericCollector interface."""
    try:
        from Retrieval.Numeric.base_numeric_collector import BaseNumericCollector
        
        # Check if it inherits from BaseNumericCollector
        if issubclass(collector_class, BaseNumericCollector):
            print(f"✓ {collector_name} correctly inherits from BaseNumericCollector")
        else:
            print(f"✗ {collector_name} does not inherit from BaseNumericCollector")
            return False
            
        # Check required class attributes
        required_attrs = ['SOURCE_NAME', 'BASE_URL', 'BATCH_SIZE', 'MAX_RETRIES', 'OUTPUT_COLUMNS']
        
        # Create instance to test attributes  
        collector = collector_class()
        
        for attr in required_attrs:
            if hasattr(collector, attr):
                print(f"✓ {collector_name} has {attr}: {getattr(collector, attr)}")
            else:
                print(f"✗ {collector_name} missing required attribute: {attr}")
                return False
                
        print(f"✓ All required attributes present for {collector_name}")
        return True
        
    except Exception as e:
        print(f"✗ Error testing {collector_name} interface: {e}")
        return False

def test_collector_methods(collector_name, collector_class):
    """Test that a specific collector has all required abstract methods implemented."""
    try:
        # Create instance
        collector = collector_class()
        
        # Check for all abstract methods that should be implemented
        required_methods = ['build_request', 'fetch_batch', 'parse_response', 'normalize_record']
        
        all_methods_exist = True
        for method in required_methods:
            if hasattr(collector, method) and callable(getattr(collector, method)):
                print(f"✓ {collector_name} implements {method}")
            else:
                print(f"✗ {collector_name} missing method: {method}")
                all_methods_exist = False
                
        if all_methods_exist:
            print(f"✓ All required methods implemented for {collector_name}")
            
        return all_methods_exist
        
    except Exception as e:
        print(f"✗ Error testing {collector_name} methods: {e}")
        return False

def main():
    """Run comprehensive tests for all collectors."""
    print("Comprehensive Collector Tests")
    print("=" * 40)
    
    # Import all collector classes
    try:
        from Retrieval.Numeric.yfinance_collector import YFinanceCollector
        from Retrieval.Numeric.nse_collector import NSECollector
        from Retrieval.Numeric.bsc_collector import BSCCollector
        from Retrieval.Numeric.screener_collector import ScreenerCollector
        from Retrieval.Numeric.bse_collector import BSECollector
        
        collectors = [
            ("YFinanceCollector", YFinanceCollector),
            ("NSECollector", NSECollector), 
            ("BSCCollector", BSCCollector),
            ("ScreenerCollector", ScreenerCollector),
            ("BSECollector", BSECollector)
        ]
        
        print("Testing All Collectors")
        print("-" * 30)
        
        all_tests_passed = True
        
        # Test imports
        if not test_collector_imports():
            all_tests_passed = False
            
        print()
        
        # Test each collector's interface
        for name, collector_class in collectors:
            print(f"\nTesting {name}")
            print("-" * 20)
            
            interface_test = test_collector_interface(name, collector_class)
            methods_test = test_collector_methods(name, collector_class)
            
            if not (interface_test and methods_test):
                all_tests_passed = False
                
        print("\n" + "=" * 40)
        if all_tests_passed:
            print("✓ All collector tests PASSED")
            return 0
        else:
            print("✗ Some collector tests FAILED")
            return 1
            
    except Exception as e:
        print(f"Error in main test function: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())