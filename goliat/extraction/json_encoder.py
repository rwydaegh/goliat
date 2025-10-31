import json
from typing import Any

import numpy as np


class NumpyArrayEncoder(json.JSONEncoder):
    """JSON encoder that handles NumPy types.

    Converts numpy arrays and numeric types to Python built-ins so they can
    be serialized to JSON.
    """

    def default(self, o: Any) -> Any:
        """Converts NumPy types to JSON-serializable Python types."""
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        return super().default(o)
