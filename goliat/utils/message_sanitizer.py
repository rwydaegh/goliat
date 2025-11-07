"""Message sanitization for web bridge."""

from typing import Dict, Any


class MessageSanitizer:
    """Removes non-serializable objects from messages."""

    @staticmethod
    def sanitize(message: Dict[str, Any]) -> Dict[str, Any]:
        """Remove non-serializable objects from message.

        Args:
            message: GUI message dictionary that may contain non-serializable objects

        Returns:
            Sanitized message dictionary with only JSON-serializable values
        """
        sanitized = {}
        for key, value in message.items():
            if key == "profiler":
                # Extract only serializable data from profiler
                if hasattr(value, "eta_seconds"):
                    sanitized[key] = {"eta_seconds": getattr(value, "eta_seconds", None)}
                else:
                    # Skip profiler object if we can't extract data
                    continue
            elif isinstance(value, (str, int, float, bool, type(None))):
                sanitized[key] = value
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [
                    MessageSanitizer.sanitize(item) if isinstance(item, dict) else item
                    for item in value
                    if isinstance(item, (str, int, float, bool, type(None), dict))
                ]
            elif isinstance(value, dict):
                sanitized[key] = MessageSanitizer.sanitize(value)
            # Skip other non-serializable types
        return sanitized
