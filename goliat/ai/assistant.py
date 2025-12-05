"""GOLIAT AI Assistant - Codebase-aware AI for debugging and assistance.

This module provides an AI assistant that understands the entire GOLIAT codebase
through embeddings, enabling natural language queries about the code, debugging
assistance, and intelligent recommendations.

Uses a simple RAG (Retrieval Augmented Generation) approach:
1. Index codebase with embeddings
2. Search for relevant chunks on query
3. Send context + query to LLM
"""

import os
from pathlib import Path
from typing import Optional

from .chat_handler import ChatHandler
from .config import AIConfig, get_default_config
from .cost_tracker import CostTracker
from .embedding_indexer import EmbeddingIndexer
from .query_processor import QueryProcessor
from .types import BackendType

# Singleton instance
_assistant_instance: Optional["GOLIATAssistant"] = None


def get_assistant() -> "GOLIATAssistant":
    """Get or create the singleton GOLIAT assistant instance."""
    global _assistant_instance
    if _assistant_instance is None:
        _assistant_instance = GOLIATAssistant()
    return _assistant_instance


class GOLIATAssistant:
    """AI Assistant for GOLIAT with codebase understanding.

    Uses a simple but effective RAG approach:
    1. Embed all code/docs into a local vector store
    2. On query, find relevant chunks via semantic search
    3. Send retrieved context + query to appropriate LLM based on complexity

    Model Selection:
    - Simple questions → gpt-5-mini (fast, $0.25/$2.00 per 1M tokens)
    - Complex/debugging → gpt-5 (smart, $1.25/$10.00 per 1M tokens)

    Example usage:
        assistant = GOLIATAssistant()

        # One-shot question
        answer = assistant.ask("How does tissue grouping work?")

        # Interactive chat
        assistant.chat()

        # Debug an error
        diagnosis = assistant.debug(error_message, log_context)
    """

    def __init__(
        self,
        backend: BackendType = "openai",
        base_dir: Optional[str] = None,
        config: Optional[AIConfig] = None,
    ):
        """Initialize the GOLIAT assistant.

        Args:
            backend: Which backend to use ("openai" uses OpenAI embeddings + GPT)
            base_dir: Base directory of GOLIAT project. Auto-detected if None.
            config: Configuration instance. Uses default if None.
        """
        self.config = config or get_default_config()
        self.config.backend = backend  # Override backend from config
        self.base_dir = base_dir or self._find_base_dir()

        # Initialize OpenAI client
        self.client = self._init_openai()

        # Initialize components
        self.cost_tracker = CostTracker(self.config, self.base_dir)
        self.indexer = EmbeddingIndexer(self.config, self.base_dir, self.client)
        self.query_processor = QueryProcessor(self.config, self.client)
        self.chat_handler = ChatHandler(self.config, self.indexer, self.query_processor, self.cost_tracker, self.client)

        # Build or load the index
        self.indexer.ensure_index()

    def _find_base_dir(self) -> str:
        """Find the GOLIAT base directory."""
        # Try relative to this file
        current = Path(__file__).parent.parent.parent
        if (current / "goliat").exists() and (current / "docs").exists():
            return str(current)

        # Try current working directory
        cwd = Path.cwd()
        if (cwd / "goliat").exists():
            return str(cwd)

        raise ValueError("Could not find GOLIAT base directory. Please specify base_dir.")

    def _init_openai(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            # Try loading from .env file
            env_path = os.path.join(self.base_dir, ".env")
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OPENAI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip("\"'")
                            break

        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Set it in environment or .env file.")

        return OpenAI(api_key=api_key)

    def get_cost_summary(self) -> dict:
        """Get cost summary for current session.

        Returns:
            Dictionary with total_cost, call_count, breakdown, and pricing info.
        """
        return self.cost_tracker.get_summary()

    def ask(self, question: str, context: str = "", force_complex: Optional[bool] = None) -> str:
        """Ask a one-shot question about GOLIAT.

        Automatically selects the appropriate model:
        - Simple questions → gpt-5-mini (fast, cheap)
        - Complex questions → gpt-5 (smart, thorough)

        Args:
            question: The question to ask.
            context: Optional additional context (e.g., error logs).
            force_complex: None (auto-select), False (force simple), True (force complex)

        Returns:
            The assistant's response.
        """
        self.indexer.ensure_index()

        # Select model based on query complexity (single call to avoid duplicate classification)
        model, complexity = self.query_processor.select_model_with_complexity(question, force_complex=force_complex)

        # Search for relevant chunks (cost tracking handled inside)
        relevant_chunks = self.indexer.search(question, cost_tracker=self.cost_tracker)

        # Build context from retrieved chunks
        retrieved_context = "\n\n---\n\n".join(chunk["content"] for chunk in relevant_chunks)

        # Build the prompt
        user_message = f"""Based on the following code/documentation from the GOLIAT codebase:

{retrieved_context}

{f"Additional context provided by user: {context}" if context else ""}

Question: {question}

Please provide a helpful, accurate answer based on the GOLIAT codebase."""

        # Build API call kwargs
        create_kwargs = {
            "model": model,
            "messages": [{"role": "system", "content": self.config.system_prompt}, {"role": "user", "content": user_message}],
        }
        # Use max_completion_tokens for GPT-5, max_tokens for older models
        if model.startswith("gpt-5"):
            create_kwargs["max_completion_tokens"] = self.config.llm.max_output_tokens
            # GPT-5 only supports default temperature (1), don't set it
        else:
            create_kwargs["max_tokens"] = self.config.llm.max_output_tokens
            # Set temperature for older models
            temperature = self.config.llm.temperature_complex if complexity == "complex" else self.config.llm.temperature_simple
            create_kwargs["temperature"] = temperature

        # Make API call
        response = self.client.chat.completions.create(**create_kwargs)

        # Track cost
        if hasattr(response, "usage"):
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            cost = self.cost_tracker.calculate_cost(model, usage)
            self.cost_tracker.track_call(
                {
                    "type": "chat",
                    "model": model,
                    "complexity": complexity,
                    "input_tokens": usage["prompt_tokens"],
                    "output_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                    "cost": cost,
                }
            )

        content = response.choices[0].message.content
        if not content or not content.strip():
            return "The AI model returned an empty response. This may indicate an API issue or the query was too complex."
        return content

    def chat(self) -> None:
        """Start an interactive chat session."""
        self.chat_handler.start_chat()

    def debug(self, error_message: str, log_context: str = "", config_snippet: str = "", model_selection: str = "auto") -> str:
        """Debug an error with AI assistance.

        Args:
            error_message: The error message or exception.
            log_context: Recent log output, shell context, or other debugging context.
            config_snippet: Relevant config if applicable.
            model_selection: Model selection mode - "simple", "complex", or "auto" (default).

        Returns:
            Diagnosis and suggested fixes.
        """
        context_parts = []

        if log_context:
            context_parts.append(log_context)

        if config_snippet:
            context_parts.append(f"Config:\n```json\n{config_snippet}\n```")

        question = f"""I encountered this error while running GOLIAT:

```
{error_message}
```

Please diagnose the issue and suggest specific fixes. Reference relevant code files if helpful.
If shell context is provided, use it to understand what commands were run and what might have gone wrong."""

        # Determine force_complex based on model_selection
        if model_selection == "simple":
            force_complex = False
        elif model_selection == "complex":
            force_complex = True
        else:  # "auto"
            force_complex = None  # Let ask() decide based on query complexity

        return self.ask(question, "\n\n".join(context_parts), force_complex=force_complex)

    def recommend(self, log_output: str) -> Optional[str]:
        """Analyze logs and provide recommendations if issues are detected.

        Args:
            log_output: Recent log output to analyze.

        Returns:
            Recommendations if issues detected, None otherwise.
        """
        warning_keywords = ["WARNING", "ERROR", "FATAL", "retry", "failed", "timeout"]
        has_issues = any(kw.lower() in log_output.lower() for kw in warning_keywords)

        if not has_issues:
            return None

        question = f"""Analyze these GOLIAT logs and identify any issues that need attention:

```
{log_output[-self.config.error_advisor.max_log_chars :]}
```

If there are concerning patterns (errors, excessive retries, warnings), explain what's wrong and how to fix it.
If the logs look normal, just say "Logs look healthy."
Be concise."""

        # Use complex model for log analysis
        return self.ask(question, force_complex=True)

    def reindex(self) -> None:
        """Force reindex of the codebase."""
        self.indexer.clear_cache()
        print(f"Rebuilding index with {self.config.models.embedding}...")
        self.indexer.ensure_index()
