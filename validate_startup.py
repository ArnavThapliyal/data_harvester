#!/usr/bin/env python3
"""
Validation of pipeline startup using uv.
This script tests imports, environment setup, and logs startup behavior.
"""
import os
import sys
import logging
import importlib.util
from pathlib import Path

# Setup logging to capture startup info
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    print("=== STARTUP VALIDATION REPORT ===")
    
    # Set up the path properly (like what main.py does)
    project_root = str(Path(__file__).parent)
    sys.path.insert(0, project_root)
    
    print(f"Working directory: {os.getcwd()}")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Project root: {project_root}")
    
    startup_log = []
    
    try:
        # Test core imports that main.py would need 
        startup_log.append("Testing imports...")
        
        # Since we can't actually import main.py directly due to its structure, let's test key modules
        
        # Test retrieval imports  
        from Retrieval import registry
        startup_log.append("✓ Retrieval.registry imported successfully")
        
        # Test specific collectors - use try/except for each to capture failures individually
        collector_modules = [
            ('Retrieval.Numeric.yfinance_collector', 'YFinanceCollector'),
            ('Retrieval.Numeric.nse_collector', 'NSECollector'),
            ('Retrieval.Numeric.bsc_collector', 'BSCCollector'),
            ('Retrieval.Numeric.screener_collector', 'ScreenerCollector'),
        ]
        
        for module_path, class_name in collector_modules:
            try:
                module = importlib.import_module(module_path)
                startup_log.append(f"✓ {class_name} imported successfully from {module_path}")
            except Exception as e:
                startup_log.append(f"⚠ Failed to import {class_name} from {module_path}: {e}")

        # Test pipeline components
        pipeline_modules = [
            ('pipeline.collectors', 'BaseCollector, NumericCollector'),
            ('converter.file_extractor', 'FileExtractor'),
            ('pipeline.cleaner', 'Cleaner'),
            ('pipeline.chunker', 'Chunker'), 
            ('pipeline.normalizer', 'Normalizer'),
        ]
        
        for module_path, class_names in pipeline_modules:
            try:
                module = importlib.import_module(module_path)
                startup_log.append(f"✓ {class_names} imported successfully from {module_path}")
            except Exception as e:
                startup_log.append(f"⚠ Failed to import from {module_path}: {e}")

        # Test registry functionality if possible without execution
        try:
            from Retrieval.registry import get_collectors, get_collector
            collectors = get_collectors()
            startup_log.append(f"✓ Retrieved {len(collectors)} collector classes from registry")
            
            # Try accessing some specific collectors to make sure they load properly
            try:
                yf_cls = get_collector('yfinance')
                startup_log.append("✓ Successfully retrieved yfinance collector")
            except Exception as e:
                startup_log.append(f"⚠ Failed to retrieve yfinance collector: {e}")
                
        except Exception as e:
            startup_log.append(f"⚠ Failed to access registry: {e}")

        # Check environment variables (if any are required)
        startup_log.append("Checking for required environment variables...")
        required_env_vars = ['YFINANCE_API_KEY', 'OPENAI_API_KEY']  # Example - adjust if needed
        missing_env_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_env_vars.append(var)
                startup_log.append(f"⚠ Environment variable {var} is not set")
        
        if missing_env_vars:
            startup_log.append(f"Missing environment variables: {', '.join(missing_env_vars)}")
        else:
            startup_log.append("✓ All required environment variables are present")

        # Check dependencies
        startup_log.append("Checking key dependencies...")
        key_packages = ['yfinance', 'pandas', 'httpx']
        missing_deps = []
        for pkg in key_packages:
            try:
                importlib.import_module(pkg)
                startup_log.append(f"✓ {pkg} dependency available")
            except ImportError:
                missing_deps.append(pkg)
                startup_log.append(f"✗ Missing dependency: {pkg}")

        if missing_deps:
            startup_log.append(f"Missing dependencies: {', '.join(missing_deps)}")

        # Summary
        print("\n=== VALIDATION SUMMARY ===")
        for log_msg in startup_log:
            print(log_msg)
            
        # Write everything to report file  
        with open('startup_validation_report.txt', 'w') as f:
            f.write("=== STARTUP VALIDATION REPORT ===\n")
            f.write(f"Execution time: {importlib.import_module('datetime').datetime.now().isoformat()}\n\n")
            f.write("=== STARTUP LOG ===\n")
            for log_msg in startup_log:
                f.write(log_msg + "\n")
                
            f.write("\n=== IMPORT FAILURES ===\n")
            # Check if we had any import failures by looking at the log
            import_failures = [line for line in startup_log if line.startswith('⚠')]
            if import_failures:
                for failure in import_failures:
                    f.write(failure + "\n")
            else:
                f.write("No import failures detected.\n")
                
            f.write("\n=== MISSING ENVIRONMENT VARIABLES ===\n")
            if missing_env_vars:
                for var in missing_env_vars:
                    f.write(f"- {var}\n")
            else:
                f.write("All required environment variables are set.\n")
                
            f.write("\n=== MISSING DEPENDENCIES ===\n")  
            if missing_deps:
                for dep in missing_deps:
                    f.write(f"- {dep}\n")
            else:
                f.write("All key dependencies are satisfied.\n")
                
            f.write("\n=== STACK TRACES ===\n")
            # No stack traces since this is a dry-run validation
            
        print("\nValidation report saved to startup_validation_report.txt")
        return 0
        
    except Exception as e:
        logger.error(f"Validation test failed: {e}")
        import traceback
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        # Write error report
        with open('startup_validation_report.txt', 'w') as f:
            f.write("=== STARTUP VALIDATION REPORT ===\n")
            f.write(f"Execution time: {importlib.import_module('datetime').datetime.now().isoformat()}\n\n")
            f.write("=== ERROR ENCOUNTERED ===\n")
            f.write(f"Error during validation: {e}\n")
            f.write(f"Exception type: {type(e).__name__}\n")
            f.write("Traceback:\n")
            f.write(traceback.format_exc())
            
        print("\nError report saved to startup_validation_report.txt") 
        return 1

if __name__ == "__main__":
    sys.exit(main())