# Firecracker Sandbox

This package provides a Firecracker microVM runner for executing untrusted crawling workloads in isolated environments.

## Requirements

- Linux with KVM enabled (`/dev/kvm` must be accessible)
- Firecracker binary installed and available in PATH
- Pre-built rootfs image and kernel image

## Setup

### Prerequisites

1. Ensure KVM is enabled on your system:
   ```bash
   ls -l /dev/kvm
   ```

2. Install firecracker:
   ```bash
   # Follow installation instructions at: https://github.com/firecracker-microvm/firecracker
   ```

### Rootfs Image Setup

The rootfs image must be built separately as a one-time setup step.

Example steps to build a basic Firecracker rootfs:

```bash
# Create a base directory
mkdir -p firecracker-rootfs/{bin,lib,lib64,usr/lib,etc,dev}
cd firecracker-rootfs

# Copy required system libraries and executables
cp /bin/bash bin/
cp /bin/sh bin/
cp /bin/python3 bin/

# Copy library dependencies (example only - actual requirements may vary)
ldd /bin/python3 | grep -o '/[^ ]*' | xargs -I '{}' cp --parents '{}' lib/
ldd /bin/bash | grep -o '/[^ ]*' | xargs -I '{}' cp --parents '{}' lib/

# Create a minimal etc/passwd and group
echo "root:x:0:0:root:/root:/bin/bash" > etc/passwd
echo "root:x:0:" > etc/group
```

## Configuration

Add these to `config/settings.py`:

```python
FIRECRACKER_ROOTFS = "/path/to/your/firecracker_rootfs.ext4"
FIRECRACKER_KERNEL = "/path/to/vmlinuz" 
```

The rootfs and kernel paths are required for Firecracker execution. These must point to actual pre-built images that contain Python, virtual environment, and dependencies needed to run the crawling scripts.

## Usage

```python
from sandbox.firecracker_runner import FirecrackerRunner

runner = FirecrackerRunner(timeout_seconds=600)  # 10 minutes default

result = runner.run(
    script_path="/path/to/crawling_script.py",
    args=["--symbol", "RELIANCE"],
    output_dir="/tmp/output",
    symbol="RELIANCE"
)
```

## Features

- **Isolated Execution**: Runs crawling workloads in secure microVMs
- **Resource Control**: Configurable vCPU count and memory (1vCPU, 512MB RAM)
- **Timeout Handling**: Default 10-minute timeout for execution 
- **Secure Disk Isolation**: Shared output volume mounted read-write
- **Error Handling**: Comprehensive validation and error reporting
- **Cleanup**: Automatic resource cleanup in finally blocks

## Limitations

This implementation is a framework that handles the structure but requires:
1. Properly built rootfs image with Python and dependencies  
2. Valid firecracker binary setup
3. Correct API socket communication for actual VM lifecycle management

Actual Firecracker API integration would need to be implemented for full functionality.