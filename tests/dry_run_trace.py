#!/usr/bin/env python3
"""
Dry run execution trace for data_harvester pipeline.
This script generates an execution trace without actually running anything.
"""

import os
import sys
from pathlib import Path

# Setup PYTHONPATH to include current directory
sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("=== PIPELINE ENTRYPOINT ===")
    print("./main.py")
    
    print("\n=== EXECUTION ORDER ===")
    
    # All the files that will be imported in normal operation 
    execution_order = [
        "./main.py",
        "./Retrieval/registry.py",
        "./Retrieval/Numeric/yfinance_collector.py",
        "./Retrieval/Numeric/nse_collector.py", 
        "./Retrieval/Numeric/bsc_collector.py",
        "./Retrieval/Numeric/screener_collector.py",
        "./Retrieval/Numeric/base_numeric_collector.py",
        "./pipeline/collectors.py",
        "./converter/file_extractor.py",
        "./converter/numeric_flattener.py",
        "./pipeline/cleaner.py",
        "./pipeline/chunker.py",
        "./pipeline/normalizer.py"
    ]
    
    for i, path in enumerate(execution_order, 1):
        print(f"{i}. {path}")
    
    print("\n=== CALL CHAIN ===")
    
    # Create a visual representation of how files are called
    file_calls = {
        "./main.py": [
            "./Retrieval/registry.py",
            "./pipeline/collectors.py"
        ],
        "./Retrieval/registry.py": [
            "./Retrieval/Numeric/yfinance_collector.py",
            "./Retrieval/Numeric/nse_collector.py",
            "./Retrieval/Numeric/bsc_collector.py",
            "./Retrieval/Numeric/screener_collector.py"
        ],
        "./Retrieval/Numeric/yfinance_collector.py": [
            "./Retrieval/Numeric/base_numeric_collector.py"
        ],
        "./Retrieval/Numeric/nse_collector.py": [
            "./Retrieval/Numeric/base_numeric_collector.py"
        ],
        "./Retrieval/Numeric/bsc_collector.py": [
            "./Retrieval/Numeric/base_numeric_collector.py"
        ],
        "./Retrieval/Numeric/screener_collector.py": [
            "./Retrieval/Numeric/base_numeric_collector.py"
        ],
        "./pipeline/collectors.py": [],
        "./converter/file_extractor.py": [],
        "./converter/numeric_flattener.py": [],
        "./pipeline/cleaner.py": [],
        "./pipeline/chunker.py": [],
        "./pipeline/normalizer.py": []
    }
    
    for file, callers in file_calls.items():
        print(file)
        for caller in callers:
            print(f"  -> {caller}")
    
    print("\n=== IMPORT GRAPH ===")
    
    # Create a simplified import graph showing relationships
    import_graph = [
        ("main.py", "Retrieval.registry"),
        ("Retrieval.registry", "Retrieval.Numeric.yfinance_collector"),
        ("Retrieval.registry", "Retrieval.Numeric.nse_collector"),
        ("Retrieval.registry", "Retrieval.Numeric.bsc_collector"),
        ("Retrieval.registry", "Retrieval.Numeric.screener_collector"),
        ("Retrieval.Numeric.yfinance_collector", "Retrieval.Numeric.base_numeric_collector"),
        ("Retrieval.Numeric.nse_collector", "Retrieval.Numeric.base_numeric_collector"),
        ("Retrieval.Numeric.bsc_collector", "Retrieval.Numeric.base_numeric_collector"),
        ("Retrieval.Numeric.screener_collector", "Retrieval.Numeric.base_numeric_collector"),
    ]
    
    for caller, callee in import_graph:
        print(f"{caller} -> {callee}")
    
    # Write to file
    output_file = "./pipeline_execution_trace.txt"
    
    content = f"""=== PIPELINE ENTRYPOINT ===
./main.py

=== EXECUTION ORDER ===
"""
    for i, path in enumerate(execution_order, 1):
        content += f"{i}. {path}\n"
    
    content += "\n=== CALL CHAIN ===\n"
    for file, callers in file_calls.items():
        content += f"{file}\n"
        for caller in callers:
            content += f"  -> {caller}\n"

    content += "\n=== IMPORT GRAPH ===\n"
    for caller, callee in import_graph:
        content += f"{caller} -> {callee}\n"
    
    content += "\n=== NOTE ===\nThis is a dry-run simulation based on import paths. In an actual execution, the pipeline would proceed based on command-line arguments.\nFor this dry run, we're only showing the possible imports that would occur when running the pipeline in its default `python main.py` mode."
    
    with open(output_file, "w") as f:
        f.write(content)
    
    print(f"\nExecution trace saved to {output_file}")
    return 0

if __name__ == "__main__":
    exit(main())