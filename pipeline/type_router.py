import pathlib
import mimetypes 
import magic  # python-magic for byte-sniffing
import zipfile
import tempfile
import shutil
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Handler mappings
STRUCTURED_DOC_HANDLERS = {
    '.pdf': 'structured_doc_handler',
    '.docx': 'structured_doc_handler', 
    '.pptx': 'structured_doc_handler',
    '.html': 'structured_doc_handler'
}

TABULAR_HANDLERS = {
    '.xlsx': 'tabular_handler',
    '.xls': 'tabular_handler',
    '.csv': 'tabular_handler'
}

# Combined lookup table
HANDLER_MAP = {**STRUCTURED_DOC_HANDLERS, **TABULAR_HANDLERS}

def get_file_type(file_path):
    path = pathlib.Path(file_path)
    
    # First check extension
    extension = path.suffix.lower()
    if extension and extension in HANDLER_MAP:
        return extension
    
    # Fallback to magic bytes for unknown extensions
    try:
        mime_type = magic.from_file(str(path), mime=True)
        if mime_type:
            return mime_type
    except Exception as e:
        logger.warning(f"Failed to detect file type with magic bytes: {e}")
        
    # If we still can't determine, return None  
    return None

def route_file(file_path, scratch_dir):
    path = pathlib.Path(file_path)
    
    # Check if file exists
    if not path.exists():
        logger.warning(f"File does not exist: {file_path}")
        return None
        
    # Skip directories
    if path.is_dir():
        logger.warning(f"Skipping directory: {file_path}")
        return None
    
    # Handle ZIP files by extracting and routing contents
    if path.suffix.lower() == '.zip':
        return route_zip_file(path, scratch_dir)
        
    # Determine file type
    file_type = get_file_type(file_path)
    
    # Route based on determined type
    if file_type in HANDLER_MAP:
        handler = HANDLER_MAP[file_type]
        logger.info(f"Routing {file_path} to {handler}")
        return [(handler, str(path))]
    else:
        # Unknown file type - log and skip
        logger.warning(f"Unknown file type for {file_path}: {file_type}")
        return None

def route_zip_file(zip_path, scratch_dir):
    logger.info(f"Processing ZIP file: {zip_path}")
    
    # Create a temporary directory for extraction
    temp_extract_dir = scratch_dir / f"extracted_{zip_path.stem}"
    temp_extract_dir.mkdir(exist_ok=True)
    
    try:
        # Extract all contents
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
        
        # Route each extracted member
        routed_files = []
        for member in temp_extract_dir.rglob('*'):
            if member.is_file():
                # Recursively route the extracted file through this same function
                nested_result = route_file(member, scratch_dir)
                if nested_result:
                    routed_files.extend(nested_result)
        
        return routed_files
        
    except Exception as e:
        logger.error(f"Error processing ZIP file {zip_path}: {e}")
        return None
    finally:
        # Clean up temporary directory
        if temp_extract_dir.exists():
            shutil.rmtree(temp_extract_dir)
