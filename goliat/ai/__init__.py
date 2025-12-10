"""GOLIAT AI Assistant module.

Provides AI-powered assistance for GOLIAT using code embeddings and LLMs.
Supports both OpenAI Assistants API and local alternatives.

Quick start:
    # CLI usage
    goliat ask "How does tissue grouping work?"
    goliat chat  # Interactive mode
    goliat recommend logs/session.log  # Analyze logs for issues

    # Programmatic usage
    from goliat.ai import GOLIATAssistant
    assistant = GOLIATAssistant()
    answer = assistant.ask("What does the power balance check do?")
"""

from .assistant import GOLIATAssistant, get_assistant
from .config import AIConfig, get_default_config, set_default_config
from .error_advisor import ErrorAdvisor, diagnose_on_error, setup_log_monitoring
from .types import BackendType, ComplexityType, SeverityType

__all__ = [
    "GOLIATAssistant",
    "get_assistant",
    "AIConfig",
    "get_default_config",
    "set_default_config",
    "ErrorAdvisor",
    "diagnose_on_error",
    "setup_log_monitoring",
    "BackendType",
    "ComplexityType",
    "SeverityType",
]
