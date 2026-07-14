import re
import yaml
from pathlib import Path

class DocumentClassifier:
    def __init__(self):
        """Initialize the document classifier with loaded rules."""
        self.rules = self._load_rules()
        self.fallback_type = self._load_fallback()
    
    def _load_rules(self):
        """Load document classification rules from YAML file."""
        rules_file = Path(__file__).parent / "rules.yaml"
        if not rules_file.exists():
            return []
        
        try:
            with open(rules_file, 'r') as f:
                config = yaml.safe_load(f)
                
            rules = []
            if 'rules' in config:
                for rule_config in config['rules']:
                    rules.append({
                        'pattern': rule_config['pattern'],
                        'doc_type': rule_config['type']
                    })
            
            return rules
        except Exception as e:
            print(f"Error loading rules: {e}")
            return []
    
    def _load_fallback(self):
        """Load fallback document type from YAML configuration."""
        rules_file = Path(__file__).parent / "rules.yaml"
        if not rules_file.exists():
            return "unknown_filing"
        
        try:
            with open(rules_file, 'r') as f:
                config = yaml.safe_load(f)
            
            return config.get('fallback', 'unknown_filing')
        except Exception as e:
            print(f"Error loading fallback: {e}")
            return "unknown_filing"
    
    def classify(self, filename: str, text: str) -> str:
        """Classify document type based on filename and content."""
        search_text = f"{filename}\n{text}"
        
        # Check each rule
        for rule in self.rules:
            try:
                if re.search(rule['pattern'], search_text, re.I):
                    return rule['doc_type']
            except Exception as e:
                # Skip invalid patterns
                print(f"Error matching pattern {rule['pattern']}: {e}")
                continue
        
        return self.fallback_type