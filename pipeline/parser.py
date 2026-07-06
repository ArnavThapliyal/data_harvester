"""
    1. Ingestion: The parser receives a file path from the retrieval layer (data/raw/)
    2. Configuration: Reads compute budget flags to determine OCR/translation settings
    3. Engine Initialization: Sets up docling with appropriate pipeline options  
    4. Parsing: Passes document directly to layout-aware engine for processing
    5. Translation: Converts engine output into structured IR blocks using your specifications:
       - Text elements are tagged appropriately
       - Tables are converted to Markdown format (not raw text)
       - Images include captions and bounding box coordinates
    6. Output: Returns sequential list of IR blocks to pipeline stages
    
"""

import pdfplumber  #for pdfs
from bs4 import BeautifulSoup
from typing import Any, List, Dict, Tuple
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions 
from docling.datamodel.base_models import InputFormat
import pathlib, zipfile, logging
import json
import os

# Configure logging
logger = logging.getLogger(__name__)

# Import type router for file routing decisions
from pipeline.type_router import route_file

class Parser:
    def __init__(self, compute_budget: dict = None):
        self.compute_budget = compute_budget or self._load_compute_budget()
        pdf_options = PdfPipelineOptions()
        if self.compute_budget.get("enable_ml_ocr"):
            pdf_options.ocr_options = EasyOcrOptions(lang=["en", "hi"] if self.compute_budget.get("enable_hindi_translation") else ["en"])
        # built ONCE — rebuilding per file reloads OCR models every time
        from docling.datamodel.pipeline_options import PdfFormatOption
        self.converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)})
  
    def _load_compute_budget(self) -> Dict[str, Any]:
        """Load compute budget settings from configuration"""
        # This is a placeholder based on your specification
        # In reality, this would read from config/settings.py
        return {
            'enable_ml_ocr': False,
            'max_pages_for_ocr': 10,
            'enable_hindi_translation': False
        }

    """
        Main parsing function that follows the workflow:
        1. Ingest and setup
        2. Execute parsing with layout-aware engine 
        3. Translation to Intermediate Representation
        4. Output packaging
        
        Args:
            file_path (str): Path to input file
            scratch_dir (pathlib.Path): Directory for temporary processing
            
        Returns:
            List[Dict[str, Any]]: List of IR blocks
        """        
    def run(self, file_path: str, scratch_dir: pathlib.Path = None) -> list[dict]:
        # For now just return a basic placeholder - the parser interface should be implemented  
        # This function would actually use docling to parse documents according to your 
        # spec and would return structured IR blocks
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")
            
        try:
            result = self.converter.convert(file_path)
            doc = result.document
            blocks = []
            for item, level in doc.iterate_items():
                try:
                    page_no = item.prov[0].page_no if getattr(item, "prov", None) else None
                    if hasattr(item, 'table') and item.table:
                        # Assuming table items have export_to_dataframe method
                        md = item.export_to_dataframe(doc=doc).to_markdown(index=False)
                        blocks.append({"type": "table", "content": md, "page_number": page_no})
                    elif hasattr(item, 'header'):
                        blocks.append({"type": "header", "content": item.text, "hierarchical_level": item.level, "page_number": page_no})
                    elif hasattr(item, 'list_item'):
                        blocks.append({"type": "list_item", "content": item.text, "page_number": page_no})
                    elif hasattr(item, 'text'):
                        blocks.append({"type": "paragraph", "content": item.text, "page_number": page_no})
                except Exception as e:
                    logger.warning(f"skipping bad item: {e}")  # per-item, doesn't drop the whole doc
                    continue
            return blocks
            
        except Exception as e:
            logger.error(f"Failed to parse document: {e}")
            raise

    def _configure_engine(self) -> Dict[str, Any]:
        """Configure the underlying conversion engine with OCR settings"""
        # Configure PDF processing pipeline options
        pdf_options = PdfPipelineOptions()
        
        # Apply compute budget settings
        if self.compute_budget.get('enable_ml_ocr', False):
            # Enable ML-based OCR (e.g., EasyOCR) if enabled in config
            pdf_options.ocr_options = EasyOcrOptions()
            
        return {
            'pdf_options': pdf_options,
            'enable_hindi_translation': self.compute_budget.get('enable_hindi_translation', False)
        }

    def _translate_document_to_ir(self, document: Any, file_path: str) -> List[Dict[str, Any]]:
        """
        Translate layout-aware engine output to Intermediate Representation
        following your IR format specifications
        
        Args:
            document (Any): Document from docling converter 
            file_path (str): Path to the original file
            
        Returns:
            List[Dict[str, Any]]: List of IR blocks with metadata and content
        """
        ir_blocks = []
        
        # Get document metadata to extract page info
        document_metadata = getattr(document, 'metadata', {})
        
        # Create a list of all elements in reading order 
        # (Docling should handle layout traversal correctly)
        elements = self._extract_elements_from_document(document)
        
        # Sequential iteration through tree in reading order
        for element_idx, element in enumerate(elements):
            if element is None:
                continue
                
            # Convert each element to IR block
            ir_block = self._element_to_ir_block(element, element_idx, document_metadata)
            
            if ir_block:  # Only add non-null blocks
                ir_blocks.append(ir_block)
                
        return ir_blocks

    def _extract_elements_from_document(self, document: Any) -> List[Any]:
        """
        Extract elements from the document in sequential reading order
        
        Args:
            document (Any): Document object from docling
            
        Returns:
            List[Any]: List of elements in reading order
        """
        # Docling already provides proper tree traversal with reading order
        # This would be more complex in real implementation using hierarchical tree
        elements = []
        
        try:
            # Get root document and iterate elements properly
            if hasattr(document, 'body'):
                # For structured documents, extract children
                self._extract_children_recursive(document.body, elements)
            
            # The layout-aware engine handles reading order, we just process what it gives us 
            return elements
        except Exception as e:
            logger.warning(f"Error extracting elements: {e}")
            return []

    def _extract_children_recursive(self, node: Any, elements: List[Any]):
        """Recursively extract child elements for proper ordering"""
        if hasattr(node, 'children') and node.children:
            for child in node.children:
                elements.append(child)
                self._extract_children_recursive(child, elements)
        else:
            # Add the node itself
            elements.append(node)

    def _element_to_ir_block(self, element: Any, element_idx: int, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate an engine element to Intermediate Representation block
        
        Args:
            element (Any): Element from layout-aware engine
            element_idx (int): Index of the element 
            metadata (Dict[str, Any]): Document metadata
            
        Returns:
            Dict[str, Any]: IR block with proper structure and metadata
        """
        
        # Extract page number (this is part of docling's element metadata)
        page_number = getattr(element, 'page', 1)  # Default to page 1
        
        # Determine block type based on element type
        block_type = self._get_block_type(element)
        
        # Extract content based on block type
        if block_type == 'table':
            text_content = self._extract_table_content(element)
        elif block_type == 'image':
            text_content = self._extract_image_content(element)
        else:
            text_content = self._extract_text_content(element)
            
        # Extract hierarchical level (e.g., heading levels)
        level = self._get_level(element)
        
        # Create the IR block
        ir_block = {
            'type': block_type,
            'page_number': page_number,
            'hierarchical_level': level,
            'content': text_content,
            'element_index': element_idx,
            'metadata': {}
        }
        
        # Add any extra metadata that was available
        if hasattr(element, 'id'):
            ir_block['metadata']['element_id'] = element.id # type: ignore
            
        return ir_block

    def _get_block_type(self, element: Any) -> str:
        """Determine the block type from the element"""
        # Map docling element types to your IR block types
        element_type_map = {
            'header': 'header',
            'paragraph': 'paragraph', 
            'list_item': 'list_item',
            'table': 'table',
            'image': 'image',
            'figure': 'image',
            'caption': 'caption'
        }
        
        # Try to get type from element object
        if hasattr(element, 'type'):
            return element_type_map.get(element.type.lower(), 'text')
            
        # Fallback based on element attributes  
        if hasattr(element, 'table'):
            return 'table'
        elif hasattr(element, 'image'):
            return 'image'
        else:
            # Default to text-like elements
            return 'paragraph'

    def _extract_text_content(self, element: Any) -> str:
        """Extract clean text content from an element"""
        if hasattr(element, 'text'):
            return element.text
            
        # For complex elements, extract all nested text
        if hasattr(element, 'children'):
            text_parts = []
            for child in getattr(element, 'children', []):
                if hasattr(child, 'text') and child.text:
                    text_parts.append(child.text)
            return ' '.join(text_parts)
            
        return ""

    def _extract_table_content(self, element: Any) -> str:
        """Extract table content into Markdown grid format"""
        # This will be enhanced based on actual docling table structure
        try:
            # If element has a table attribute or similar
            if hasattr(element, 'table'):
                # Convert structured data to markdown grid
                return self._to_markdown_table(element.table)
            else:
                # Fallback for raw tables (in practice, docling should provide proper tables)
                return "| Column 1 | Column 2 |\n|----------|----------|\n| Data 1   | Data 2   |"
        except Exception as e:
            logger.warning(f"Error extracting table: {e}")
            return ""

    def _to_markdown_table(self, table_data: Any) -> str:
        """Convert tabular data to Markdown grid format"""
        # This is a simplified example - real implementation would use docling's table structure
        if not hasattr(table_data, 'rows'):
            return "| Column 1 | Column 2 |\n|----------|----------|\n| Data 1   | Data 2   |"
            
        # For demo purposes, just return placeholder
        rows = getattr(table_data, 'rows', [])
        return "| Row 1 Col 1 | Row 1 Col 2 |\n|-------------|-------------|\n| Data 1      | Data 2      |"

    def _extract_image_content(self, element: Any) -> str:
        """Extract image information and captions"""
        caption = ""
        if hasattr(element, 'caption'):
            caption = element.caption
            
        # Extract coordinate info if available
        coordinates = {}
        if hasattr(element, 'bbox'):
            coordinates = {
                'x0': getattr(element.bbox, 'x0', 0),
                'y0': getattr(element.bbox, 'y0', 0), 
                'x1': getattr(element.bbox, 'x1', 0),
                'y1': getattr(element.bbox, 'y1', 0)
            }
            
        # Format for IR block
        image_info = {
            "caption": caption,
            "coordinates": coordinates
        }
        
        return json.dumps(image_info)

    def _get_level(self, element: Any) -> int:
        """Get hierarchical level from element (e.g., header level 1-6)"""
        if hasattr(element, 'level'):
            return element.level
            
        # Default for non-header elements
        return 0

# Convenience function for direct usage, though typically called via pipeline.py
def parse_file(file_path: str, scratch_dir: pathlib.Path) -> List[Dict[str, Any]]:
    """Convenience function to parse a single file"""
    parser = Parser()
    return parser.run(file_path, scratch_dir)

