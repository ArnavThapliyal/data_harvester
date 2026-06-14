#!/usr/bin/env python3
"""
Test script to verify document_crawler implementation structure works correctly.
This test verifies the code can be imported and structure is correct without 
making actual network requests or file downloads.
"""

import sys
import os

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all necessary modules can be imported"""
    try:
        from Retrieval.Document.document_crawler import (
            sanitize_filename,
            get_file_extension,
            determine_download_destination,
            is_url_downloadable,
            extract_links_with_beautifulsoup,
            create_manifest
        )
        print("✅ All core functions imported successfully")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_functions():
    """Test key functions with dummy data"""
    try:
        from Retrieval.Document.document_crawler import (
            sanitize_filename,
            get_file_extension,
            determine_download_destination
        )
        
        # Test sanitize_filename
        result = sanitize_filename("https://example.com/file.pdf")
        print(f"✅ sanitize_filename works: {result}")
        
        # Test get_file_extension  
        ext = get_file_extension("https://example.com/file.pdf")
        print(f"✅ get_file_extension works: {ext}")
        
        # Test determine_download_destination
        dest_type, path = determine_download_destination("https://example.com/report.pdf", "RELIANCE")
        print(f"✅ determine_download_destination works: {dest_type}, {path}")
        
        return True
    except Exception as e:
        print(f"❌ Function test failed: {e}")
        return False

def test_manifest_creation():
    """Test manifest creation function"""
    try:
        from Retrieval.Document.document_crawler import create_manifest
        
        files = [
            {
                "url": "https://example.com/file.pdf",
                "filename": "file.pdf",
                "size_bytes": 1024,
                "downloaded_at": "2026-06-12T11:36:00+00:00",
                "success": True,
                "error": None
            }
        ]
        
        manifest = create_manifest("RELIANCE", ["https://example.com"], "httpx", 1, files)
        print("✅ Manifest creation works")
        print(f"  Symbol: {manifest['symbol']}")
        print(f"  Files count: {manifest['total_files']}")
        return True
    except Exception as e:
        print(f"❌ Manifest test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing document_crawler implementation...")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_functions, 
        test_manifest_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests completed successfully!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())