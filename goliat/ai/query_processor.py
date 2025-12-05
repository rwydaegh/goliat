"""Query processing and model selection logic."""

from typing import Optional

from .config import AIConfig
from .types import ComplexityType


class QueryProcessor:
    """Handles query classification and model selection."""

    def __init__(self, config: AIConfig, client=None):
        """Initialize the query processor.

        Args:
            config: AI configuration
            client: OpenAI client instance (required for AI-based classification)
        """
        self.config = config
        self.client = client

    def classify_complexity(self, query: str) -> ComplexityType:
        """Classify a query as simple or complex to select the right model.

        Uses AI model to intelligently classify queries:
        - Simple queries → gpt-5-mini (fast, cheap)
        - Complex queries → gpt-5 (smart, thorough)

        Args:
            query: The user's question or request

        Returns:
            "simple" or "complex"
        """
        if not self.client:
            # Fallback to simple if no client available
            return "simple"

        # Use AI to classify the query
        classification_prompt = f"""Classify the following query as either "simple" or "complex".

A simple query is a straightforward question that can be answered quickly with basic information, like:
- "What is X?"
- "Where is Y?"
- "List Z"
- Quick lookups or definitions

A complex query requires deeper reasoning, analysis, or multi-step problem solving, like:
- Debugging errors or issues
- Explaining how something works
- Code implementation or refactoring
- Architecture or design questions
- Multi-step problem solving

Query: {query}

Respond with only one word: "simple" or "complex"."""

        try:
            response = self.client.chat.completions.create(
                model=self.config.models.simple,  # Use simple model for classification to keep costs low
                messages=[
                    {"role": "system", "content": "You are a query classifier. Respond with only 'simple' or 'complex'."},
                    {"role": "user", "content": classification_prompt},
                ],
                max_tokens=10,
                temperature=0.0,  # Deterministic classification
            )

            result = response.choices[0].message.content.strip().lower()
            if "complex" in result:
                return "complex"
            else:
                return "simple"
        except Exception:
            # Fallback to simple on any error
            return "simple"

    def select_model(self, query: str, force_complex: Optional[bool] = None) -> str:
        """Select the appropriate model based on query complexity.

        Args:
            query: The user's question
            force_complex: None (auto-select), False (force simple), True (force complex)

        Returns:
            Model name to use
        """
        model, _ = self.select_model_with_complexity(query, force_complex)
        return model

    def select_model_with_complexity(self, query: str, force_complex: Optional[bool] = None) -> tuple[str, ComplexityType]:
        """Select the appropriate model and return both model and complexity.

        This avoids duplicate classification calls when both values are needed.

        Args:
            query: The user's question
            force_complex: None (auto-select), False (force simple), True (force complex)

        Returns:
            Tuple of (model_name, complexity_type)
        """
        if force_complex is True:
            return self.config.models.complex, "complex"
        elif force_complex is False:
            return self.config.models.simple, "simple"

        # Auto-select based on query complexity
        complexity = self.classify_complexity(query)

        if complexity == "simple":
            return self.config.models.simple, complexity
        else:
            return self.config.models.complex, complexity
