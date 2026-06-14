"""CollectedDocument model definition."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

@dataclass
class CollectedDocument:
    """Data model for stored collected documents."""
    
    # Document identifier (UUID)
    id: str
    
    # Pipeline run ID that this document was part of
    run_id: str
    
    # Source collector name
    source: str
    
    # Original source document identifier (if applicable)
    original_id: Optional[str] = None
    
    # Collected data (structured)
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Raw content (unstructured)
    raw_content: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Collection timestamp
    collected_at: datetime = field(default_factory=datetime.utcnow)
    
    # Processing status
    status: str = "collected"  # 'collected', 'processed', 'failed'
    
    # Path to raw storage location
    raw_path: Optional[Path] = None
    
    # Path to processed storage location
    processed_path: Optional[Path] = None
