import json
from typing import Any

import numpy as np


class NumpyArrayEncoder(json.JSONEncoder):
    """A JSON encoder for NumPy data types."""

    def default(self, o: Any) -> Any:
        """Converts NumPy types to standard Python types for JSON serialization."""
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        return super().default(o)
