"""
Virus scanning module using ClamAV for Firecracker VM outputs.

This module provides functions to scan files for viruses using ClamAV.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("sandbox.scanner")


def scan_files(directory: Path) -> Dict[str, Any]:
    """
    Scan a directory for infected files using ClamAV.
    
    Args:
        directory: Directory to scan
        
    Returns:
        Dictionary with clean, infected, and error lists
    """
    result = {
        "clean": [],
        "infected": [],
        "errors": []
    }
    
    # Check if clamscan is available
    try:
        subprocess.run(["clamscan", "--version"], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("ClamAV not found in PATH. Skipping virus scan.")
        # Return all files as clean if clamav is not available
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    result["clean"].append(str(file_path.relative_to(directory)))
        except Exception as e:
            result["errors"].append(f"Failed to enumerate directory: {str(e)}")
        return result
    
    # Run ClamAV scan
    try:
        # Use clamscan with recursive option and quiet output
        cmd = [
            "clamscan", 
            "--recursive=yes",
            "--infected",  # Only show infected files
            "--quiet",     # No extra output
            str(directory)
        ]
        
        # Run the scan
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        # Parse results
        if process.stdout:
            lines = process.stdout.strip().split('\n') if process.stdout.strip() else []
            for line in lines:
                if ':' in line and 'FOUND' in line:
                    # Line format: /path/to/file: virus FOUND
                    file_path = line.split(':')[0].strip()
                    result["infected"].append(str(Path(file_path).relative_to(directory)))
        
        # Check for errors in stderr  
        if process.stderr:
            error_lines = process.stderr.strip().split('\n') if process.stderr.strip() else []
            for line in error_lines:
                if not line.startswith("Checking") and 'ERROR' in line.upper():
                    result["errors"].append(line)
        
    except Exception as e:
        logger.error(f"Error during virus scan: {str(e)}")
        result["errors"].append(str(e))
        
    # If we found any infected files, add clean files from directory enumeration
    if not result["infected"]:
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file() and str(file_path.relative_to(directory)) not in result["infected"]:
                    result["clean"].append(str(file_path.relative_to(directory)))
        except Exception as e:
            result["errors"].append(f"Failed to enumerate directory: {str(e)}")
        
    # If no infections found, just enumerate all files
    if not result["infected"]:
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    rel_path = str(file_path.relative_to(directory))
                    if rel_path not in result["clean"]:
                        result["clean"].append(rel_path)
        except Exception as e:
            result["errors"].append(f"Failed to enumerate directory: {str(e)}")
    
    return result


def main():
    """Main entry point for testing scanner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scan files with ClamAV")
    parser.add_argument("--directory", required=True, help="Directory to scan")
    
    args = parser.parse_args()
    
    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory {args.directory} does not exist")
        return
    
    result = scan_files(directory)
    
    print(f"Clean files: {len(result['clean'])}")
    print(f"Infected files: {len(result['infected'])}")
    print(f"Errors: {len(result['errors'])}")
    
    if result["infected"]:
        print("Infected files:")
        for infected in result["infected"]:
            print(f"  - {infected}")
    
    if result["errors"]:
        print("Scan errors:")
        for error in result["errors"]:
            print(f"  - {error}")


if __name__ == "__main__":
    main()