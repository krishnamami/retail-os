"""
pytest configuration for Evidence tests
Enables import of evidence_transformer from database/evidence/
"""
import sys
from pathlib import Path

# Add database/evidence to sys.path so evidence_transformer can be imported
evidence_dir = Path(__file__).parent.parent.parent / 'database' / 'evidence'
if evidence_dir not in sys.path:
    sys.path.insert(0, str(evidence_dir))
