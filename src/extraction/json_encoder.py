import json
from typing import Any

import numpy as np


class NumpyArrayEncoder(json.JSONEncoder):
    """A JSON encoder for NumPy data types."""

    def default(self, obj: Any) -> Any:
        """Converts NumPy types to standard Python types for JSON serialization."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return json.JSONEncoder.default(self, obj)
