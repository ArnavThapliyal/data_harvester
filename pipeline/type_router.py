import pathlib.Path
import mimetypes 
#(stdlib fallback); optional 
import magic #(python-magic) for byte-sniffing

import logging
# Configure logging
logger = logging.getLogger(__name__)
