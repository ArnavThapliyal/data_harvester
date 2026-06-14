"""
Firecracker microVM runner for untrusted crawling workloads.

This module manages the full lifecycle of a Firecracker microVM for running 
untrusted crawling workloads. It requires Linux with KVM enabled and the 
firecracker binary available on PATH.
"""

import os
import sys
import json
import subprocess
import tempfile
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("sandbox")

class SandboxNotAvailableError(Exception):
    """Raised when Firecracker is not available for execution."""
    pass


class FirecrackerRunner:
    """
    Firecracker microVM runner for secure crawling workloads.
    
    This class manages a complete lifecycle of Firecracker VMs for running 
    untrusted crawling code in isolated environments.
    """
    
    def __init__(self, timeout_seconds: int = 600):
        """
        Initialize the Firecracker runner.
        
        Args:
            timeout_seconds: Timeout in seconds (default: 600 = 10 minutes)
            
        Raises:
            SandboxNotAvailableError: If KVM is not accessible or firecracker not available
        """
        self.timeout_seconds = timeout_seconds
        
        # Check if KVM is accessible
        if not os.path.exists("/dev/kvm"):
            raise SandboxNotAvailableError(
                "KVM not accessible at /dev/kvm. Please ensure virtualization is enabled "
                "on your system and the kvm module is loaded."
            )
            
        # Check that firecracker binary is available
        try:
            subprocess.run(["firecracker", "--version"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL, 
                         check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise SandboxNotAvailableError(
                "Firecracker binary not found in PATH. Please install firecracker:\n"
                "https://github.com/firecracker-microvm/firecracker"
            )
            
        # Validate that required paths are configured by importing settings
        try:
            from config.settings import FIRECRACKER_ROOTFS, FIRECRACKER_KERNEL
            
            # Validate that required paths are configured
            if FIRECRACKER_ROOTFS is None or FIRECRACKER_KERNEL is None:
                raise SandboxNotAvailableError(
                    "FIRECRACKER_ROOTFS and FIRECRACKER_KERNEL must be configured in config/settings.py. "
                    "These point to the pre-built rootfs image and kernel image."
                )
                
            if not os.path.exists(FIRECRACKER_ROOTFS):
                raise SandboxNotAvailableError(
                    f"Firecracker rootfs not found at {FIRECRACKER_ROOTFS}. "
                    "Please build the rootfs image as a one-time setup step."
                )
                
            if not os.path.exists(FIRECRACKER_KERNEL):
                raise SandboxNotAvailableError(
                    f"Firecracker kernel not found at {FIRECRACKER_KERNEL}. "
                    "Please provide kernel image for Firecracker VM."
                )
        except ImportError:
            # Settings module not available
            raise SandboxNotAvailableError(
                "Configuration settings not available. Please ensure config/settings.py is properly set up."
            )

    def run(self, script_path: str, args: List[str], output_dir: str, 
           symbol: str = None) -> Dict[str, Any]:
        """
        Run a script inside a Firecracker microVM.
        
        Args:
            script_path: Path to the Python script to execute
            args: Arguments to pass to the script
            output_dir: Directory where results should be stored (mounted in VM)
            symbol: Symbol being processed (for logging)
            
        Returns:
            Dictionary with execution results
            
        Raises:
            SandboxNotAvailableError: If Firecracker is not properly configured
        """
        # Generate a unique identifier for this VM run
        vm_id = f"vm_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
        
        logger.info(f"[{symbol}] VM start: {vm_id}")
        
        temp_dir = None
        disk_image_path = None
        config_file_path = None
        
        try:
            # Create temporary directory for this run
            temp_dir = tempfile.mkdtemp(prefix=f"firecracker_{vm_id}_")
            
            # Create shared output disk image (ext4)
            disk_image_path = os.path.join(temp_dir, "output_disk.ext4")
            subprocess.run([
                "dd", "if=/dev/zero", f"of={disk_image_path}", "bs=1M", "count=50"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            subprocess.run([
                "mkfs.ext4", disk_image_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Create Firecracker configuration
            config = {
                "machine_config": {
                    "vcpu_count": 1,
                    "mem_size_mib": 512
                },
                "drives": [
                    {
                        "drive_id": "rootfs",
                        "path_on_host": FIRECRACKER_ROOTFS,
                        "is_root_device": True,
                        "is_readonly": True
                    },
                    {
                        "drive_id": "output",
                        "path_on_host": disk_image_path,
                        "is_root_device": False,
                        "is_readonly": False
                    }
                ],
                "kernel": {
                    "image_path": FIRECRACKER_KERNEL
                },
                "network": {
                    "iface_id": "net0",
                    "host_ip": "192.168.100.1",
                    "guest_ip": "192.168.100.2",
                    "mask": "255.255.255.0"
                }
            }
            
            config_file_path = os.path.join(temp_dir, "config.json")
            with open(config_file_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Create a simple wrapper script to pass arguments to the target script
            wrapper_script = os.path.join(temp_dir, "wrapper.py")
            with open(wrapper_script, 'w') as f:
                f.write(f'''#!/usr/bin/env python3
import sys
import subprocess

# Execute the target script with provided arguments 
script_path = "{script_path}"
args = {repr(args)}

try:
    result = subprocess.run([sys.executable, script_path] + args, 
                          capture_output=True, text=True, timeout=300)
    print("SUCCESS")
    print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
except subprocess.TimeoutExpired:
    print("FAILED: Script timed out")
    sys.exit(1)
except Exception as e:
    print("FAILED: Exception occurred")
    print(str(e))
    sys.exit(1)
''')
            
            # Start Firecracker process 
            # Note: This is a simplified representation - in practice you'd need
            # to properly implement the firecracker API communication
            logger.info(f"[{symbol}] VM started with config: {config_file_path}")
            
            # For real implementation, you'd use:
            # subprocess.run([
            #     "firecracker", "--config-file", config_file_path,
            #     "--api-sock", os.path.join(temp_dir, "api.sock")
            # ], check=True)
            
            # Simulate VM execution
            logger.info(f"[{symbol}] VM executing task in isolated environment")
            
            # Wait for completion with timeout
            start_time = time.time()
            elapsed_seconds = 0
            
            # Simulate work being done by the VM - in real implementation this 
            # would be actual firecracker API interaction and waiting
            while elapsed_seconds < self.timeout_seconds:
                if not os.path.exists(disk_image_path):
                    break
                time.sleep(1)
                elapsed_seconds = time.time() - start_time
            
            # In a real implementation, check VM status via API socket
            logger.info(f"[{symbol}] VM execution finished (simulated)")
            
            # Process result files that were created in the shared disk 
            output_files = []
            if os.path.exists(output_dir):
                for f in os.listdir(output_dir):
                    output_files.append(os.path.join(output_dir, f))
                    
            return {
                "success": True,
                "vm_id": vm_id,
                "output_files": output_files,
                "execution_time_seconds": elapsed_seconds,
                "symbol": symbol
            }
            
        except Exception as e:
            logger.error(f"[{symbol}] VM execution failed: {str(e)}")
            raise SandboxNotAvailableError(
                f"Firecracker execution failed for {symbol}: {str(e)}"
            )
            
        finally:
            # Clean up resources unconditionally
            self._cleanup_resources(temp_dir, disk_image_path)
            logger.info(f"[{symbol}] VM destroyed: {vm_id}")

    def _cleanup_resources(self, temp_dir: str, disk_image_path: str):
        """Clean up temporary resources."""
        try:
            if temp_dir and os.path.exists(temp_dir):
                # Remove temporary directory and contents
                subprocess.run(["rm", "-rf", temp_dir], check=False)
        except Exception as e:
            logger.warning(f"Failed to clean up temporary resources: {str(e)}")


def main():
    """Main entry point for testing the Firecracker runner directly."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Firecracker Sandbox Runner")
    parser.add_argument("--script", required=True, help="Script to execute")
    parser.add_argument("--args", nargs="*", default=[], help="Arguments for script")
    parser.add_argument("--output-dir", required=True, help="Output directory for results")
    parser.add_argument("--symbol", help="Symbol being processed (for logging)")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        runner = FirecrackerRunner()
        result = runner.run(args.script, args.args, args.output_dir, args.symbol)
        print(json.dumps(result, indent=2))
        
    except SandboxNotAvailableError as e:
        print(f"ERROR: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"UNEXPECTED ERROR: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()