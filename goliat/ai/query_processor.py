"""Query processing and model selection logic."""

import re
from typing import Optional

from .config import AIConfig
from .types import ComplexityType


class QueryProcessor:
    """Handles query classification and model selection."""

    def __init__(self, config: AIConfig):
        """Initialize the query processor.

        Args:
            config: AI configuration
        """
        self.config = config

    def classify_complexity(self, query: str) -> ComplexityType:
        """Classify a query as simple or complex to select the right model.

        Simple queries → gpt-5-mini (fast, cheap)
        Complex queries → gpt-5 (smart, thorough)

        Args:
            query: The user's question or request

        Returns:
            "simple" or "complex"
        """
        query_lower = query.lower()

        # Check for complex indicators first (higher priority)
        for indicator in self.config.query_classification.complex_indicators:
            if re.search(indicator, query_lower):
                return "complex"

        # Check for simple indicators
        for indicator in self.config.query_classification.simple_indicators:
            if re.search(indicator, query_lower):
                return "simple"

        # Default based on query length
        # Short queries are usually simple lookups
        # Long queries usually need more reasoning
        word_count = len(query.split())
        if word_count <= self.config.query_classification.simple_word_threshold:
            return "simple"
        elif word_count >= self.config.query_classification.complex_word_threshold:
            return "complex"

        # Default to simple for cost efficiency
        return "simple"

    def select_model(self, query: str, force_complex: Optional[bool] = None) -> str:
        """Select the appropriate model based on query complexity.

        Args:
            query: The user's question
            force_complex: None (auto-select), False (force simple), True (force complex)

        Returns:
            Model name to use
        """
        if force_complex is True:
            return self.config.models.complex
        elif force_complex is False:
            return self.config.models.simple

        # Auto-select based on query complexity
        complexity = self.classify_complexity(query)

        if complexity == "simple":
            return self.config.models.simple
        else:
            return self.config.models.complex
