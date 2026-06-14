
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
RAW_NUMERIC = BASE_DIR / "data" / "raw" / "numeric"
RAW_DOCUMENTS = BASE_DIR / "data" / "raw" / "documents"
RAW_DOCUMENTS_OTHER = BASE_DIR / "data" / "raw" / "documents" / "other"
TRANS_NUMERIC = BASE_DIR / "data" / "transient" / "numeric"
TRANS_DOCUMENTS = BASE_DIR / "data" / "transient" / "documents"
CLEANED_NUMERIC = BASE_DIR / "data" / "cleaned" / "numeric"
CLEANED_DOCUMENTS = BASE_DIR / "data" / "cleaned" / "documents"
CHUNKED = BASE_DIR / "data" / "chunked"
DONE = BASE_DIR / "data" / "done"
COMPANY_UNIVERSE_CSV = CONFIG_DIR / "company_universe.csv"
COMPANY_METADATA_JSON = CONFIG_DIR / "company_metadata.json"
COMPANY_URLS_JSON = CONFIG_DIR / "company_urls.json"

# Firecracker configuration
FIRECRACKER_ROOTFS = None  # Path to pre-built rootfs image
FIRECRACKER_KERNEL = None  # Path to kernel image

# Ensure all directories are created on import
for path in [
    RAW_NUMERIC,
    RAW_DOCUMENTS,
    RAW_DOCUMENTS_OTHER,
    TRANS_NUMERIC,
    TRANS_DOCUMENTS,
    CLEANED_NUMERIC,
    CLEANED_DOCUMENTS,
    CHUNKED,
    DONE,
]:
    path.mkdir(parents=True, exist_ok=True)