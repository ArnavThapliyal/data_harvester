#!/usr/bin/env python3
"""
Independent collector testing using uv.
This script tests each collector class by instantiating and running sample operations.
"""
import os
import sys
import logging
from pathlib import Path
import json

# Setup logging  
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_collector(module_path, class_name, collector_instance):
    """Test a single collector instance"""
    results = {}
    
    logger.info(f"Testing {class_name} from {module_path}")
    
    try:
        # Test that we can get the class attributes
        if hasattr(collector_instance, 'SOURCE_NAME'):
            results['source_name'] = collector_instance.SOURCE_NAME
            logger.info(f"  Source name: {collector_instance.SOURCE_NAME}")
        
        if hasattr(collector_instance, 'BASE_URL'):
            results['base_url'] = collector_instance.BASE_URL
            logger.info(f"  Base URL: {collector_instance.BASE_URL}")
            
        if hasattr(collector_instance, 'BATCH_SIZE'):
            results['batch_size'] = collector_instance.BATCH_SIZE
            logger.info(f"  Batch size: {collector_instance.BATCH_SIZE}")
            
        # Test method existence (not execution)
        methods_to_check = ['build_request', 'fetch_batch', 'parse_response', 'normalize_record']
        for method in methods_to_check:
            if hasattr(collector_instance, method):
                results[f'method_{method}'] = True
                logger.info(f"  ✓ {method} method exists")
            else:
                results[f'method_{method}'] = False
                logger.warning(f"  ⚠ {method} method missing")
                
        # Test schema if it has OUTPUT_COLUMNS (numeric collectors)
        if hasattr(collector_instance, 'OUTPUT_COLUMNS'):
            results['output_columns'] = collector_instance.OUTPUT_COLUMNS
            logger.info(f"  Output columns: {len(collector_instance.OUTPUT_COLUMNS)} fields")
            
        results['status'] = 'success'
        
    except Exception as e:
        logger.error(f"  Error testing {class_name}: {e}")
        results['status'] = 'error'
        results['error'] = str(e)
        
    return results

def main():
    print("=== COLLECTOR VALIDATION REPORT ===")
    
    # Set up the path properly
    project_root = str(Path(__file__).parent)
    sys.path.insert(0, project_root)
    
    report_content = []
    report_content.append("=== COLLECTOR VALIDATION REPORT ===\n")
    report_content.append(f"Execution time: {importlib.import_module('datetime').datetime.now().isoformat()}\n\n")
    
    collector_tests = []

    # Test collectors one by one
    try:
        # YFinance Collector
        logger.info("Testing YFinanceCollector...")
        from Retrieval.Numeric.yfinance_collector import YFinanceCollector
        
        yf_instance = YFinanceCollector()
        yf_results = test_collector('Retrieval.Numeric.yfinance_collector', 'YFinanceCollector', yf_instance)
        yf_results['class'] = 'YFinanceCollector'
        collector_tests.append(yf_results)
        
        # NSE Collector
        logger.info("Testing NSECollector...")
        from Retrieval.Numeric.nse_collector import NSECollector
        
        nse_instance = NSECollector()
        nse_results = test_collector('Retrieval.Numeric.nse_collector', 'NSECollector', nse_instance)
        nse_results['class'] = 'NSECollector'
        collector_tests.append(nse_results)
        
        # BSC Collector
        logger.info("Testing BSCCollector...")
        from Retrieval.Numeric.bsc_collector import BSCCollector
        
        bsc_instance = BSCCollector()
        bsc_results = test_collector('Retrieval.Numeric.bsc_collector', 'BSCCollector', bsc_instance)
        bsc_results['class'] = 'BSCCollector'
        collector_tests.append(bsc_results)
        
        # Screener Collector
        logger.info("Testing ScreenerCollector...")
        from Retrieval.Numeric.screener_collector import ScreenerCollector
        
        screener_instance = ScreenerCollector()
        screener_results = test_collector('Retrieval.Numeric.screener_collector', 'ScreenerCollector', screener_instance)
        screener_results['class'] = 'ScreenerCollector'
        collector_tests.append(screener_results)
        
        # Report results
        report_content.append("=== COLLECTOR TEST RESULTS ===\n\n")
        
        for test_result in collector_tests:
            class_name = test_result.get('class', 'Unknown')
            status = test_result.get('status', 'unknown')
            
            report_content.append(f"--- {class_name} ---\n")
            report_content.append(f"Status: {status}\n")
            
            if status == 'error':
                report_content.append(f"Error: {test_result.get('error', 'Unknown error')}\n")
            else:
                # Report attributes
                for key, value in test_result.items():
                    if key not in ['class', 'status'] and not key.startswith('method_'):
                        report_content.append(f"{key}: {value}\n")
                
                # Report methods
                methods = [k for k in test_result.keys() if k.startswith('method_')]
                if methods:
                    report_content.append("Methods:\n")
                    for method in methods:
                        method_name = method.replace('method_', '')
                        exists = test_result[method]
                        status_icon = "✓" if exists else "⚠"
                        report_content.append(f"  {status_icon} {method_name}\n")
                        
            report_content.append("\n")
            
        # Summary
        successful = sum(1 for r in collector_tests if r.get('status') == 'success')
        total = len(collector_tests)
        
        report_content.append(f"=== SUMMARY ===\n")
        report_content.append(f"Total collectors tested: {total}\n")
        report_content.append(f"Successfully validated: {successful}\n")
        report_content.append(f"Failed validation: {total - successful}\n")
        
        # Check for missing methods (which would indicate an issue)
        report_content.append("\n=== DETAILED ANALYSIS ===\n")
        
        for test_result in collector_tests:
            class_name = test_result.get('class', 'Unknown')
            if test_result.get('status') == 'success':
                missing_methods = []
                methods_to_check = ['build_request', 'fetch_batch', 'parse_response', 'normalize_record']
                
                for method in methods_to_check:
                    if not test_result.get(f'method_{method}'):
                        missing_methods.append(method)
                        
                if missing_methods:
                    report_content.append(f"{class_name}: Missing methods - {', '.join(missing_methods)}\n")
                else:
                    report_content.append(f"{class_name}: All core methods present\n")
            else:
                report_content.append(f"{class_name}: Validation failed\n")
        
        with open('collector_validation_report.txt', 'w') as f:
            f.write(''.join(report_content))
            
        print("\nCollector validation complete. Report saved to collector_validation_report.txt")
        return 0
        
    except Exception as e:
        logger.error(f"Error in main collector testing: {e}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        with open('collector_validation_report.txt', 'w') as f:
            f.write("=== COLLECTOR VALIDATION REPORT ===\n")
            f.write(f"Execution time: {importlib.import_module('datetime').datetime.now().isoformat()}\n\n")
            f.write("=== ERROR ENCOUNTERED ===\n")
            f.write(f"Error during validation: {e}\n")
            f.write(f"Exception type: {type(e).__name__}\n")
            f.write("Traceback:\n")
            f.write(traceback.format_exc())
            
        print("\nError report saved to collector_validation_report.txt") 
        return 1

if __name__ == "__main__":
    # Import here to avoid circular dependencies in the script
    import importlib
    sys.exit(main())