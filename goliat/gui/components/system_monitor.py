"""System resource monitoring component for GUI."""

import subprocess
from typing import Tuple, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class SystemMonitor:
    """Monitors system resource utilization (CPU, RAM, GPU).

    Provides methods to get current CPU usage percentage, RAM usage in GB,
    and GPU utilization percentage (via nvidia-smi). Gracefully handles
    missing dependencies (psutil) and unavailable GPU.
    """

    @staticmethod
    def get_cpu_utilization() -> float:
        """Gets current CPU utilization percentage.

        Uses non-blocking approach by calling cpu_percent() without interval,
        which returns utilization since last call. First call returns 0.0.

        Returns:
            CPU usage percentage (0-100), or 0.0 if psutil unavailable.
        """
        if not PSUTIL_AVAILABLE:
            return 0.0
        try:
            # Non-blocking call - returns utilization since last call
            # psutil is guaranteed to be available here due to PSUTIL_AVAILABLE check
            cpu_percent = psutil.cpu_percent(interval=None)  # type: ignore[possibly-unbound]
            return cpu_percent
        except Exception:
            return 0.0

    @staticmethod
    def get_ram_utilization() -> Tuple[float, float]:
        """Gets current RAM usage and total RAM.

        Returns:
            Tuple of (used_GB, total_GB), or (0.0, 0.0) if psutil unavailable.
        """
        if not PSUTIL_AVAILABLE:
            return (0.0, 0.0)
        try:
            # psutil is guaranteed to be available here due to PSUTIL_AVAILABLE check
            memory = psutil.virtual_memory()  # type: ignore[possibly-unbound]
            used_gb = memory.used / (1024**3)
            total_gb = memory.total / (1024**3)
            return (used_gb, total_gb)
        except Exception:
            return (0.0, 0.0)

    @staticmethod
    def get_gpu_utilization() -> Optional[float]:
        """Gets current GPU utilization percentage via nvidia-smi.

        Returns:
            GPU usage percentage (0-100), or None if nvidia-smi unavailable.
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Get first GPU's utilization
                utilization_str = result.stdout.strip().split("\n")[0].strip()
                return float(utilization_str)
            return None
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError):
            return None

    @staticmethod
    def get_gpu_name() -> Optional[str]:
        """Gets GPU name via nvidia-smi.

        Returns:
            GPU name (e.g., "RTX 4090"), or None if nvidia-smi unavailable.
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Get first GPU's name and clean it up
                gpu_name = result.stdout.strip().split("\n")[0].strip()
                # Remove common prefixes like "NVIDIA " and clean up
                gpu_name = gpu_name.replace("NVIDIA ", "").strip()
                return gpu_name
            return None
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return None

    @staticmethod
    def get_cpu_cores() -> int:
        """Gets number of CPU cores.

        Returns:
            Number of CPU cores, or 0 if psutil unavailable.
        """
        if not PSUTIL_AVAILABLE:
            return 0
        try:
            return psutil.cpu_count(logical=True) or 0  # type: ignore[possibly-unbound]
        except Exception:
            return 0

    @staticmethod
    def get_total_ram_gb() -> float:
        """Gets total RAM in GB.

        Returns:
            Total RAM in GB, or 0.0 if psutil unavailable.
        """
        if not PSUTIL_AVAILABLE:
            return 0.0
        try:
            memory = psutil.virtual_memory()  # type: ignore[possibly-unbound]
            return memory.total / (1024**3)
        except Exception:
            return 0.0

    @staticmethod
    def is_gpu_available() -> bool:
        """Checks if GPU is available via nvidia-smi.

        Returns:
            True if nvidia-smi is available and returns successfully, False otherwise.
        """
        return SystemMonitor.get_gpu_utilization() is not None
