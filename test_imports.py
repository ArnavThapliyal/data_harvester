
import sys
sys.path.insert(0, '.')
try:
    from pipeline.pipeline import PipelineRunner
    print("✓ PipelineRunner import successful")
except Exception as e:
    print(f"✗ PipelineRunner import failed: {e}")

try:
    from pipeline.parser import Parser
    print("✓ Parser import successful")
except Exception as e:
    print(f"✗ Parser import failed: {e}")
    
try:
    from pipeline.vector_store import VectorStore
    print("✓ VectorStore import successful")
except Exception as e:
    print(f"✗ VectorStore import failed: {e}")

try:
    from Retrieval.registry import get_collector
    print("✓ get_collector import successful")
except Exception as e:
    print(f"✗ get_collector import failed: {e}")

print("Import test completed.")
