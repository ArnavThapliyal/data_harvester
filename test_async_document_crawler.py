#!/usr/bin/env python3
"""
Test script to verify the async document crawler functionality.
"""

import asyncio
from pipeline.Retrieval.Document.document_crawler import run_batch

# Mock company URLs for testing
MOCK_COMPANY_URLS = {
    "TEST1": {
        "all_urls": [
            "https://example.com/test1",
            "https://example.com/test2"
        ]
    },
    "TEST2": {
        "all_urls": [
            "https://example.com/test3",
            "https://example.com/test4"
        ]
    }
}

async def test_run_batch():
    """Test the batch processing function."""
    print("Testing async batch processing...")
    
    # This would normally be called with real symbols
    # For now, we'll just verify the function signature works
    try:
        # Mock the company URLs file to test functionality
        import json
        from pathlib import Path
        from unittest.mock import patch, mock_open
        
        # Create a mock JSON file with test data
        mock_data = {
            "TEST1": {"all_urls": ["https://example.com/test1", "https://example.com/test2"]},
            "TEST2": {"all_urls": ["https://example.com/test3", "https://example.com/test4"]}
        }
        
        with patch('pipeline.Retrieval.Document.document_crawler.COMPANY_URLS_JSON', new_callable=lambda: Path('/tmp/test_company_urls.json')):
            with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
                # This should not crash
                result = await run_batch(["TEST1", "TEST2"])
                print("Batch processing completed successfully")
                print(f"Results: {result}")
                
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_run_batch())