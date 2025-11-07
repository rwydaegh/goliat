"""Machine ID detection utility."""

import socket
from typing import Optional
from logging import Logger


class MachineIdDetector:
    """Detects machine ID (public IP or local IP) for web monitoring.

    Tries external service first with retries, then falls back to local IP.
    Matches the logic in run_worker.py to ensure consistency.
    """

    @staticmethod
    def detect(verbose_logger: Logger) -> Optional[str]:
        """Auto-detects machine ID (public IP or local IP).

        Args:
            verbose_logger: Logger for verbose messages.

        Returns:
            Machine ID string, or None if detection failed.
        """
        try:
            import requests

            # Try external service first with retries (matches run_worker.py)
            public_ip = None
            for attempt in range(3):  # Try up to 3 times
                try:
                    response = requests.get("https://api.ipify.org", timeout=10)
                    if response.status_code == 200:
                        public_ip = response.text.strip()
                        if public_ip:
                            break
                except Exception:
                    if attempt < 2:  # Not the last attempt
                        continue
                    # Last attempt failed, will fall through to local IP

            if public_ip:
                verbose_logger.info(f"Auto-detected public IP: {public_ip}")
                return public_ip
            else:
                # Fallback to local IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                verbose_logger.info(f"Auto-detected local IP: {local_ip}")
                return local_ip
        except Exception as e:
            verbose_logger.warning(f"Could not auto-detect machine ID: {e}")
            return None
