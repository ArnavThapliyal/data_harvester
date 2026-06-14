from pathlib import Path
import json

def save_raw(doc: dict, base_dir: Path) -> Path:
    """Save raw document and its metadata sidecar."""
    dest = base_dir / doc.source / doc.company_id / doc.doc_type
    dest.mkdir(parents=True, exist_ok=True)
    
    # Save content
    file_path = dest / f"{doc.metadata['date']}_{doc.metadata['accession']}.html"
    file_path.write_bytes(doc.raw_content)
    
    # Save metadata sidecar — same name, .meta.json extension
    meta_path = file_path.with_suffix('.meta.json')
    meta_path.write_text(json.dumps(doc.metadata, indent=2))
    
    return file_path