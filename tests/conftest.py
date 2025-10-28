import sys
import os

# Add stubs to path if running in CI
if os.environ.get("CI") == "true":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'stubs')))