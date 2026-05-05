import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Avoid real sleeps during tests
os.environ.setdefault('SKIP_PIPELINE_DELAYS', '1')
