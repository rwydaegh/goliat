"""Type definitions for GOLIAT AI module."""

from typing import Literal

# Backend types
BackendType = Literal["openai", "local"]

# Query complexity types
ComplexityType = Literal["simple", "complex"]

# Recommendation severity types
SeverityType = Literal["info", "warning", "error"]
