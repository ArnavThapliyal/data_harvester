"""
File bridge for transferring files from Firecracker VM output disk to host.

This module handles mounting the microVM output disk image, copying files 
to their intended destinations, and performing virus scanning.
"""

import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("sandbox.file_bridge")


class FileBridge:
    """
    Handles transferring files from Firecracker VM output disk to host destination.
    
    Mounts the VM output disk image, copies files to their intended locations,
    scans for viruses, and unmounts cleanly.
    """

    def __init__(self):
        """Initialize the file bridge."""
        self.mount_point = None
        self.disk_image = None

    def transfer(self, disk_image_path: str, symbol: str, 
                destination_dir: str = None) -> Dict[str, Any]:
        """
        Transfer files from VM output disk to host destination.
        
        Args:
            disk_image_path: Path to the mounted VM output disk image
            symbol: Symbol being processed (for logging and quarantine paths)
            destination_dir: Optional directory for destination (default: data/raw/documents/{symbol}/)
            
        Returns:
            Dictionary with transfer statistics
        """
        self.disk_image = disk_image_path
        self.mount_point = None
        
        try:
            # Determine destination directory 
            if destination_dir is None:
                destination_dir = f"data/raw/documents/{symbol}/"
            
            Path(destination_dir).mkdir(parents=True, exist_ok=True)
            
            # Mount the disk image using loop device
            self._mount_disk()
            
            # Scan files before transferring (if clamav available) - import locally to avoid circular
            infected_files = []
            if self.mount_point:
                try:
                    from .scanner import scan_files
                    scan_result = scan_files(Path(self.mount_point) / "output")
                    infected_files = scan_result.get("infected", [])
                    
                    if infected_files:
                        logger.warning(
                            f"Found {len(infected_files)} infected files for symbol {symbol}"
                        )
                        
                except Exception as e:
                    logger.warning(f"Virus scan failed: {str(e)}")
            
            # Copy files from mount point to destination
            transferred_files = []
            if self.mount_point:
                output_dir = Path(self.mount_point) / "output"
                if output_dir.exists():
                    for file_path in output_dir.rglob("*"):
                        if file_path.is_file():
                            # Skip infected files
                            if str(file_path.relative_to(output_dir)) in infected_files:
                                logger.info(f"Skipping infected file: {file_path}")
                                continue
                                
                            # Calculate destination path
                            rel_path = file_path.relative_to(output_dir)
                            dest_path = Path(destination_dir) / rel_path
                            
                            # Ensure destination directory exists
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Perform atomic copy: write to .tmp then rename
                            tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
                            try:
                                shutil.copy2(file_path, tmp_path)
                                os.rename(tmp_path, dest_path)
                                
                                file_size = file_path.stat().st_size
                                logger.info(f"Copied {file_path} ({file_size} bytes) to {dest_path}")
                                transferred_files.append({
                                    "source": str(file_path),
                                    "destination": str(dest_path),
                                    "size": file_size
                                })
                                
                            except Exception as e:
                                # If atomic copy fails, clean up .tmp file and log error
                                if tmp_path.exists():
                                    tmp_path.unlink()
                                logger.error(f"Failed to copy {file_path}: {str(e)}")
                                raise
                
            return {
                "symbol": symbol,
                "source_disk": disk_image_path,
                "destination_dir": destination_dir,
                "files_transferred": len(transferred_files),
                "transferred_files": transferred_files
            }
                
        finally:
            # Always unmount and cleanup
            self._unmount_disk()

    def _mount_disk(self):
        """Mount the VM output disk image using loop device."""
        if not os.path.exists(self.disk_image):
            raise FileNotFoundError(f"Disk image not found: {self.disk_image}")
            
        # Create temporary mount point
        import tempfile
        mount_point = tempfile.mkdtemp(prefix="firecracker_mount_")
        self.mount_point = mount_point
        
        # Mount the disk using loop device
        try:
            subprocess.run([
                "losetup", "-f", "--show", self.disk_image
            ], check=True, capture_output=True)
            
            # Try to mount ext4 filesystem (we're assuming it's ext4)
            subprocess.run([
                "mount", "-o", "ro", self.disk_image, mount_point
            ], check=True, capture_output=True)
            
        except subprocess.CalledProcessError as e:
            # Cleanup on failure
            if os.path.exists(mount_point):
                try:
                    subprocess.run(["umount", mount_point], check=False)
                    os.rmdir(mount_point)
                except:
                    pass
            raise RuntimeError(f"Failed to mount disk image: {e}")

    def _unmount_disk(self):
        """Unmount the VM output disk image and clean up."""
        if self.mount_point and os.path.exists(self.mount_point):
            try:
                subprocess.run(["umount", self.mount_point], check=True)
            except:
                pass  # Ignore cleanup errors
            
            try:
                os.rmdir(self.mount_point)
            except:
                pass  # Ignore cleanup errors
            
        self.mount_point = None


def main():
    """Main entry point for testing FileBridge."""
    import argparse
    
    parser = argparse.ArgumentParser(description="File bridge for Firecracker VM transfers")
    parser.add_argument("--disk-image", required=True, help="Path to output disk image")
    parser.add_argument("--symbol", required=True, help="Company symbol being processed")
    parser.add_argument("--destination", help="Destination directory (default: data/raw/documents/{symbol}/)")
    
    args = parser.parse_args()
    
    bridge = FileBridge()
    try:
        result = bridge.transfer(
            disk_image_path=args.disk_image,
            symbol=args.symbol,
            destination_dir=args.destination
        )
        print(f"Transfer completed: {result['files_transferred']} files transferred")
        return result
    except Exception as e:
        logger.error(f"Transfer failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()