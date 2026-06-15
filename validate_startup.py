     1|#!/usr/bin/env python3
     2|"""
     3|Validation of pipeline startup using uv.
     4|This script tests imports, environment setup, and logs startup behavior.
     5|"""
     6|import os
     7|import sys
     8|import logging
     9|import importlib.util
    10|from pathlib import Path
    11|
    12|# Setup logging to capture startup info
    13|logging.basicConfig(
    14|    level=logging.INFO,
    15|    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    16|    handlers=[
    17|        logging.StreamHandler(sys.stdout)
    18|    ]
    19|)
    20|logger = logging.getLogger(__name__)
    21|
    22|def main():
    23|    print("=== STARTUP VALIDATION REPORT ===")
    24|    
    25|    # Set up the path properly (like what main.py does)
    26|    project_root = str(Path(__file__).parent)
    27|    sys.path.insert(0, project_root)
    28|    
    29|    print(f"Working directory: {os.getcwd()}")
    30|    print(f"Python executable: {sys.executable}")
    31|    print(f"Python version: {sys.version}")
    32|    print(f"Project root: {project_root}")
    33|    
    34|    startup_log = []
    35|    
    36|    try:
    37|        # Test core imports that main.py would need 
    38|        startup_log.append("Testing imports...")
    39|        
    40|        # Since we can't actually import main.py directly due to its structure, let's test key modules
    41|        
    42|        # Test retrieval imports  
    43|        from Retrieval import registry
    44|        startup_log.append("✓ Retrieval.registry imported successfully")
    45|        
    46|        # Test specific collectors - use try/except for each to capture failures individually
    47|        collector_modules = [
    48|            ('Retrieval.Numeric.yfinance_collector', 'YFinanceCollector'),
    49|            ('Retrieval.Numeric.nse_collector', 'NSECollector'),
    50|            ('Retrieval.Numeric.bsc_collector', 'BSCCollector'),
    51|            ('Retrieval.Numeric.screener_collector', 'ScreenerCollector'),
    52|        ]
    53|        
    54|        for module_path, class_name in collector_modules:
    55|            try:
    56|                module = importlib.import_module(module_path)
    57|                startup_log.append(f"✓ {class_name} imported successfully from {module_path}")
    58|            except Exception as e:
    59|                startup_log.append(f"⚠ Failed to import {class_name} from {module_path}: {e}")
    60|
    61|        # Test pipeline components
    62|        pipeline_modules = [
    63|            ('pipeline.collectors', 'BaseCollector, NumericCollector'),
    64|            ('pipeline.converter', 'FileExtractor'),
    65|            ('pipeline.cleaner', 'Cleaner'),
    66|            ('pipeline.chunker', 'Chunker'), 
    67|            ('pipeline.normalizer', 'Normalizer'),
    68|        ]
    69|        
    70|        for module_path, class_names in pipeline_modules:
    71|            try:
    72|                module = importlib.import_module(module_path)
    73|                startup_log.append(f"✓ {class_names} imported successfully from {module_path}")
    74|            except Exception as e:
    75|                startup_log.append(f"⚠ Failed to import from {module_path}: {e}")
    76|
    77|        # Test registry functionality if possible without execution
    78|        try:
    79|            from Retrieval.registry import get_collectors, get_collector
    80|            collectors = get_collectors()
    81|            startup_log.append(f"✓ Retrieved {len(collectors)} collector classes from registry")
    82|            
    83|            # Try accessing some specific collectors to make sure they load properly
    84|            try:
    85|                yf_cls = get_collector('yfinance')
    86|                startup_log.append("✓ Successfully retrieved yfinance collector")
    87|            except Exception as e:
    88|                startup_log.append(f"⚠ Failed to retrieve yfinance collector: {e}")
    89|                
    90|        except Exception as e:
    91|            startup_log.append(f"⚠ Failed to access registry: {e}")
    92|
    93|        # Check environment variables (if any are required)
    94|        startup_log.append("Checking for required environment variables...")
    95|        required_env_vars = ['YFINANCE_API_KEY', 'OPENAI_API_KEY']  # Example - adjust if needed
    96|        missing_env_vars = []
    97|        for var in required_env_vars:
    98|            if not os.getenv(var):
    99|                missing_env_vars.append(var)
   100|                startup_log.append(f"⚠ Environment variable {var} is not set")
   101|        
   102|        if missing_env_vars:
   103|            startup_log.append(f"Missing environment variables: {', '.join(missing_env_vars)}")
   104|        else:
   105|            startup_log.append("✓ All required environment variables are present")
   106|
   107|        # Check dependencies
   108|        startup_log.append("Checking key dependencies...")
   109|        key_packages = ['yfinance', 'pandas', 'httpx']
   110|        missing_deps = []
   111|        for pkg in key_packages:
   112|            try:
   113|                importlib.import_module(pkg)
   114|                startup_log.append(f"✓ {pkg} dependency available")
   115|            except ImportError:
   116|                missing_deps.append(pkg)
   117|                startup_log.append(f"✗ Missing dependency: {pkg}")
   118|
   119|        if missing_deps:
   120|            startup_log.append(f"Missing dependencies: {', '.join(missing_deps)}")
   121|
   122|        # Summary
   123|        print("\n=== VALIDATION SUMMARY ===")
   124|        for log_msg in startup_log:
   125|            print(log_msg)
   126|            
   127|        # Write everything to report file  
   128|        with open('startup_validation_report.txt', 'w') as f:
   129|            f.write("=== STARTUP VALIDATION REPORT ===\n")
   130|            f.write(f"Execution time: {importlib.import_module('datetime').datetime.now().isoformat()}\n\n")
   131|            f.write("=== STARTUP LOG ===\n")
   132|            for log_msg in startup_log:
   133|                f.write(log_msg + "\n")
   134|                
   135|            f.write("\n=== IMPORT FAILURES ===\n")
   136|            # Check if we had any import failures by looking at the log
   137|            import_failures = [line for line in startup_log if line.startswith('⚠')]
   138|            if import_failures:
   139|                for failure in import_failures:
   140|                    f.write(failure + "\n")
   141|            else:
   142|                f.write("No import failures detected.\n")
   143|                
   144|            f.write("\n=== MISSING ENVIRONMENT VARIABLES ===\n")
   145|            if missing_env_vars:
   146|                for var in missing_env_vars:
   147|                    f.write(f"- {var}\n")
   148|            else:
   149|                f.write("All required environment variables are set.\n")
   150|                
   151|            f.write("\n=== MISSING DEPENDENCIES ===\n")  
   152|            if missing_deps:
   153|                for dep in missing_deps:
   154|                    f.write(f"- {dep}\n")
   155|            else:
   156|                f.write("All key dependencies are satisfied.\n")
   157|                
   158|            f.write("\n=== STACK TRACES ===\n")
   159|            # No stack traces since this is a dry-run validation
   160|            
   161|        print("\nValidation report saved to startup_validation_report.txt")
   162|        return 0
   163|        
   164|    except Exception as e:
   165|        logger.error(f"Validation test failed: {e}")
   166|        import traceback
   167|        logger.error(f"Exception type: {type(e).__name__}")
   168|        logger.error(f"Traceback:\n{traceback.format_exc()}")
   169|        
   170|        # Write error report
   171|        with open('startup_validation_report.txt', 'w') as f:
   172|            f.write("=== STARTUP VALIDATION REPORT ===\n")
   173|            f.write(f"Execution time: {importlib.import_module('datetime').datetime.now().isoformat()}\n\n")
   174|            f.write("=== ERROR ENCOUNTERED ===\n")
   175|            f.write(f"Error during validation: {e}\n")
   176|            f.write(f"Exception type: {type(e).__name__}\n")
   177|            f.write("Traceback:\n")
   178|            f.write(traceback.format_exc())
   179|            
   180|        print("\nError report saved to startup_validation_report.txt") 
   181|        return 1
   182|
   183|if __name__ == "__main__":
   184|    sys.exit(main())