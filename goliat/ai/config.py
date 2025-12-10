"""Configuration for GOLIAT AI module.

All magic numbers, constants, and tunable parameters are centralized here.
This makes the codebase more maintainable and allows easy customization.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import BackendType


@dataclass
class ModelConfig:
    """Configuration for AI models."""

    simple: str = "gpt-5-mini"
    complex: str = "gpt-5"
    embedding: str = "text-embedding-3-large"


@dataclass
class RAGConfig:
    """Configuration for RAG (Retrieval Augmented Generation) parameters."""

    top_k_chunks: int = 15
    chunk_size: int = 1500
    chunk_overlap: int = 300


@dataclass
class LLMConfig:
    """Configuration for LLM parameters."""

    temperature_simple: float = 0.2
    temperature_complex: float = 0.1
    max_output_tokens: int = 4000
    temperature_default_gpt5: float = 1.0  # GPT-5 only supports default temperature


@dataclass
class ProcessingConfig:
    """Configuration for processing parameters."""

    embedding_batch_size: int = 50
    max_retries: int = 3
    chat_history_messages: int = 6
    hash_length: int = 16

    # Rate limiting and retry behavior
    rate_limit_wait_multiplier: int = 2  # Wait time = (attempt + 1) * multiplier seconds
    rate_limit_status_code: int = 429  # HTTP status code for rate limits

    # Progress reporting
    progress_print_interval: int = 100  # Print progress every N chunks


@dataclass
class PricingConfig:
    """Configuration for model pricing (per 1M tokens)."""

    models: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "gpt-5-mini": {"input": 0.25, "output": 2.00},
            "gpt-5": {"input": 1.25, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "text-embedding-3-large": {"input": 0.13},
            "text-embedding-3-small": {"input": 0.02},
        }
    )


@dataclass
class QueryClassificationConfig:
    """Configuration for query complexity classification.

    Classification is done by AI model itself, not by heuristics.
    """


@dataclass
class ErrorAdvisorConfig:
    """Configuration for error advisor."""

    default_monitoring_interval_seconds: int = 60
    thread_join_timeout_seconds: int = 5
    print_separator_length: int = 60
    max_log_chars: int = 3000

    warning_keywords: list[str] = field(
        default_factory=lambda: [
            "ERROR",
            "FATAL",
            "Exception",
            "Traceback",
            "retry attempt",
            "failed",
            "timeout",
            "memory",
            "convergence",
            "Power balance",
        ]
    )


@dataclass
class IndexingConfig:
    """Configuration for codebase indexing."""

    # Directories to index
    index_directories: list[str] = field(default_factory=lambda: ["goliat", "cli", "docs", "configs"])

    # File patterns to include
    python_patterns: list[str] = field(default_factory=lambda: ["*.py"])
    markdown_patterns: list[str] = field(default_factory=lambda: ["*.md"])
    config_files: list[str] = field(default_factory=lambda: ["base_config.json", "near_field_config.json", "far_field_config.json"])

    # Directories/files to exclude
    exclude_dirs: list[str] = field(default_factory=lambda: ["__pycache__", ".git"])

    # Cache file location (relative to base_dir)
    cache_file: str = "data/.goliat_ai_cache.json"

    # Pricing config file location (relative to base_dir)
    pricing_config_file: str = "data/.goliat_pricing.json"


@dataclass
class AIConfig:
    """Main configuration class for GOLIAT AI module.

    This class centralizes all configuration and can be loaded from JSON files
    for easy customization. All magic numbers should be defined here.
    """

    backend: BackendType = "openai"
    models: ModelConfig = field(default_factory=ModelConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    pricing: PricingConfig = field(default_factory=PricingConfig)
    query_classification: QueryClassificationConfig = field(default_factory=QueryClassificationConfig)
    error_advisor: ErrorAdvisorConfig = field(default_factory=ErrorAdvisorConfig)
    indexing: IndexingConfig = field(default_factory=IndexingConfig)

    system_prompt: str = """You are an expert assistant for GOLIAT, a Python framework for
electromagnetic field (EMF) dosimetry simulations using Sim4Life.

GOLIAT automates:
- Near-field simulations: Device exposure (phones near head/body)
- Far-field simulations: Environmental plane wave exposure
- SAR (Specific Absorption Rate) extraction and analysis
- Paper/report generation with plots

Key concepts you understand:
- Phantoms: Digital human models (thelonious=6yo boy, eartha=adult female)
- Placements: by_cheek, front_of_eyes, by_belly
- Tissue groups: eyes, brain, skin, genitals
- SAR metrics: head_SAR, trunk_SAR, psSAR10g (peak spatial-average over 10g)
- Power balance: Energy conservation check (~100% is good)
- Config inheritance: study configs extend base_config.json

When answering:
1. Reference specific files and line numbers when relevant
2. Provide code examples when helpful
3. Explain *why* not just *what*
4. For errors, suggest specific fixes
5. Be concise but thorough

You have access to relevant code snippets from the GOLIAT codebase."""

    @classmethod
    def from_file(cls, config_path: Path | str) -> "AIConfig":
        """Load configuration from a JSON file.

        Args:
            config_path: Path to JSON configuration file

        Returns:
            AIConfig instance with values from file (missing values use defaults)
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            data = json.load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIConfig":
        """Create config from dictionary.

        Args:
            data: Dictionary with configuration values

        Returns:
            AIConfig instance
        """
        config = cls()

        # Update backend if provided
        if "backend" in data:
            config.backend = data["backend"]

        # Update nested configs
        if "models" in data:
            config.models = ModelConfig(**data["models"])
        if "rag" in data:
            config.rag = RAGConfig(**data["rag"])
        if "llm" in data:
            config.llm = LLMConfig(**data["llm"])
        if "processing" in data:
            config.processing = ProcessingConfig(**data["processing"])
        if "pricing" in data:
            config.pricing = PricingConfig(models=data["pricing"].get("models", {}))
        if "query_classification" in data:
            # Query classification config is empty now (AI-based), but keep for backwards compatibility
            config.query_classification = QueryClassificationConfig()
        if "indexing" in data:
            config.indexing = IndexingConfig(**data["indexing"])
        if "error_advisor" in data:
            config.error_advisor = ErrorAdvisorConfig(**data["error_advisor"])
        if "system_prompt" in data:
            config.system_prompt = data["system_prompt"]

        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for serialization.

        Returns:
            Dictionary representation of config
        """
        return {
            "backend": self.backend,
            "models": {
                "simple": self.models.simple,
                "complex": self.models.complex,
                "embedding": self.models.embedding,
            },
            "rag": {
                "top_k_chunks": self.rag.top_k_chunks,
                "chunk_size": self.rag.chunk_size,
                "chunk_overlap": self.rag.chunk_overlap,
            },
            "llm": {
                "temperature_simple": self.llm.temperature_simple,
                "temperature_complex": self.llm.temperature_complex,
                "max_output_tokens": self.llm.max_output_tokens,
            },
            "processing": {
                "embedding_batch_size": self.processing.embedding_batch_size,
                "max_retries": self.processing.max_retries,
                "chat_history_messages": self.processing.chat_history_messages,
                "hash_length": self.processing.hash_length,
            },
            "pricing": {"models": self.pricing.models},
            "query_classification": {},
            "indexing": {
                "index_directories": self.indexing.index_directories,
                "python_patterns": self.indexing.python_patterns,
                "markdown_patterns": self.indexing.markdown_patterns,
                "config_files": self.indexing.config_files,
                "exclude_dirs": self.indexing.exclude_dirs,
                "cache_file": self.indexing.cache_file,
                "pricing_config_file": self.indexing.pricing_config_file,
            },
            "error_advisor": {
                "default_monitoring_interval_seconds": self.error_advisor.default_monitoring_interval_seconds,
                "thread_join_timeout_seconds": self.error_advisor.thread_join_timeout_seconds,
                "print_separator_length": self.error_advisor.print_separator_length,
                "max_log_chars": self.error_advisor.max_log_chars,
                "warning_keywords": self.error_advisor.warning_keywords,
            },
            "system_prompt": self.system_prompt,
        }

    def save(self, config_path: Path | str) -> None:
        """Save configuration to JSON file.

        Args:
            config_path: Path where to save the configuration
        """
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# Default global config instance
_default_config: AIConfig | None = None


def get_default_config() -> AIConfig:
    """Get the default global configuration instance.

    Returns:
        Default AIConfig instance
    """
    global _default_config
    if _default_config is None:
        _default_config = AIConfig()
    return _default_config


def set_default_config(config: AIConfig) -> None:
    """Set the default global configuration instance.

    Args:
        config: Configuration instance to use as default
    """
    global _default_config
    _default_config = config
