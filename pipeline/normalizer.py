"""
Normalizer for pipeline - normalizes document data for vectorization.
"""
import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import logging

# Configure logging
logger = logging.getLogger(__name__)

class Normalizer:
    """Normalizer for pipeline that handles document normalization and assembly."""
    
    def __init__(self):
        """Initialize the normalizer with configuration."""
        pass
    
    def run(self, symbol: str, mode: str) -> None:
        """
        Run normalization process for a symbol in either numeric or document mode.
        
        Args:
            symbol: Company ticker symbol
            mode: Either 'numeric' or 'document'
        """
        if mode == "numeric":
            # Skip normalization for numeric data
            logger.info(f"[normalizer] [{symbol}] mode=numeric — skipped")
            return
        elif mode == "document":
            self._normalize_document(symbol)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        logger.info(f"[normalizer] [{symbol}] mode=document — done")
    
    def _normalize_document(self, symbol: str) -> None:
        """Normalize document text files for vectorization."""
        # Input and output paths
        cleaned_dir = Path(f"data/cleaned/documents/{symbol}")
        processed_dir = Path(f"data/trans/documents/{symbol}")
        output_file = Path(f"data/processed/documents/{symbol}_Document.md")
        
        # Create output directory if needed
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Process each cleaned JSON file in the directory
        json_files = list(cleaned_dir.glob("*.json"))
        if not json_files:
            logger.warning(f"No JSON files found in {cleaned_dir}")
            return
            
        # Sort files for consistent processing order 
        json_files.sort()
    
        # Process each document and append to output file
        for json_file in json_files:
            self._process_single_document(json_file, output_file, symbol)
    
    def _process_single_document(self, json_file: Path, output_file: Path, symbol: str) -> None:
        """
        Process a single document JSON file and append it to the master file.
        
        Args:
            json_file: Path to the cleaned JSON file
            output_file: Path to the master output file
            symbol: Company ticker symbol
        """
        try:
            # Read the cleaned IR blocks
            with open(json_file, 'r') as f:
                ir_blocks = json.load(f)
            
            # Get source filename (without path)
            source_filename = json_file.name
            
            # Step 1: Classification using document template classifier 
            doc_type = self._classify_document(ir_blocks, symbol, source_filename)
            
            # Step 2: Metadata assembly
            metadata = self._assemble_metadata(ir_blocks, symbol, source_filename, doc_type)
            
            # Step 3: Markdown rendering
            markdown_body = self._render_markdown(ir_blocks)
            
            # Step 4: Assembly and aggregation
            payload = self._assemble_payload(source_filename, metadata, markdown_body)
            
            # Write to output file in append mode
            with open(output_file, 'a') as f:
                f.write(payload)
                
        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
            raise
    
    def _classify_document(self, ir_blocks: List[Dict[str, Any]], symbol: str, source_filename: str) -> str:
        """
        Classify document type using pipeline/document_template/classifier.
        
        Args:
            ir_blocks: List of IR blocks from cleaned document
            symbol: Company ticker symbol  
            source_filename: Name of source file
            
        Returns:
            Document type string (e.g., '10-K', '10-Q', 'annual_report', etc.)
        """
        try:
            # Import classifier from document_template package
            from pipeline.document_template.classifier import DocumentClassifier
            
            # Create classifier instance 
            classifier = DocumentClassifier()
            
            # Build classification context using filename and text content from first pages
            text_context = self._build_classification_context(ir_blocks, source_filename)
            
            # Classify using the existing classifier system
            doc_type = classifier.classify(source_filename, text_context)
            
            # If classifier returns unknown, handle gracefully 
            if not doc_type or doc_type == 'unknown':
                logger.warning(f"Document classification returned 'unknown' for {source_filename}")
                return "unknown_filing"
                
            return doc_type
            
        except ImportError as e:
            # Fallback if classifier is not available - shouldn't happen in proper setup
            logger.error(f"Document classifier import failed: {e}")
            return "unknown_filing"
        except Exception as e:
            logger.error(f"Error in document classification: {e}")
            return "unknown_filing"
    
    def _build_classification_context(self, ir_blocks: List[Dict[str, Any]], 
                                    source_filename: str) -> str:
        """
        Build classification context using filename and text content from first pages.
        
        Args:
            ir_blocks: List of IR blocks from cleaned document
            source_filename: Name of source file
            
        Returns:
            String containing classification context
        """
        # Start with the filename (the classifier will be able to use this)
        context = f"{source_filename}\n"
        
        # Add text content from first two pages (if available)
        page1_text = ""
        page2_text = ""
        
        for block in ir_blocks:
            if block.get('page_number') == 1 and block.get('content'):
                page1_text += block['content'] + "\n"
            elif block.get('page_number') == 2 and block.get('content'):
                page2_text += block['content'] + "\n"
            # Stop after collecting text from first two pages
            if page1_text and page2_text:
                break
        
        context += page1_text + page2_text
        
        return context
    
    def _assemble_metadata(self, ir_blocks: List[Dict[str, Any]], symbol: str, 
                          source_filename: str, doc_type: str) -> Dict[str, Any]:
        """
        Assemble metadata dictionary for the document.
        
        Args:
            ir_blocks: List of IR blocks 
            symbol: Company ticker symbol
            source_filename: Name of source file
            doc_type: Classified document type
            
        Returns:
            Dictionary containing structured metadata
        """
        # Calculate stats from IR blocks
        page_count = 0
        ocr_pages = 0
        
        for block in ir_blocks:
            page_num = block.get('page_number', 1)
            page_count = max(page_count, page_num)
            
            # Check if this block has OCR flags (placeholder - would be set by parser)
            # For now, we'll track basic count as a placeholder
        # In a real implementation, this would integrate with actual parser output
        
        # Build metadata dictionary
        metadata = {
            'symbol': symbol,
            'source_filename': source_filename,
            'doc_type': doc_type,
            'downloaded_at': datetime.now().isoformat(),
            'page_count': page_count,
            'ocr_pages': ocr_pages  # Placeholder - need to be filled from parser in real implementation
        }
        
        return metadata
    
    def _render_markdown(self, ir_blocks: List[Dict[str, Any]]) -> str:
        """
        Render the IR blocks into continuous Markdown format.
        
        Args:
            ir_blocks: List of cleaned IR blocks
            
        Returns:
            String containing rendered Markdown content
        """
        markdown_lines = []
        
        for block in ir_blocks:
            block_type = block.get('type', 'paragraph')
            content = block.get('content', '')
            
            if block_type == 'header':
                level = block.get('hierarchical_level', 1)
                # Ensure level is within valid range (1-6 for Markdown headers)  
                level = max(1, min(6, level))
                header_prefix = '#' * level
                markdown_lines.append(f"{header_prefix} {content}")
            
            elif block_type == 'paragraph':
                if content.strip():  # Only add non-empty paragraphs
                    markdown_lines.append(content)
                    markdown_lines.append("")  # Double newline after paragraph
            
            elif block_type == 'table':
                # Tables are already in Markdown format from parser.py 
                if content.strip():
                    markdown_lines.append(content)
                    markdown_lines.append("")  # Double newline after table
                    
            # Skip unrecognized types but don't break processing
        
        # Join all lines with newlines
        return '\n'.join(markdown_lines)
    
    def _assemble_payload(self, source_filename: str, metadata: Dict[str, Any], 
                         markdown_body: str) -> str:
        """
        Assemble the complete payload for appending to master file.
        
        Args:
            source_filename: Name of the source file
            metadata: Metadata dictionary  
            markdown_body: Rendered Markdown content
            
        Returns:
            String containing complete payload to be appended
        """
        # Create YAML frontmatter 
        yaml_lines = [
            "---",
            f"symbol: {metadata['symbol']}",
            f"source_filename: {metadata['source_filename']}", 
            f"doc_type: {metadata['doc_type']}",
            f"downloaded_at: {metadata['downloaded_at']}",
            f"page_count: {metadata['page_count']}",
            f"ocr_pages: {metadata['ocr_pages']}",
            "---"
        ]
        
        # Combine all parts
        payload_sections = [
            f" Document: {source_filename}\n",
            "\n".join(yaml_lines) + "\n\n",
            markdown_body,
            "\n---\n\n"  # Trailing separator with padding
        ]
        
        return "".join(payload_sections)