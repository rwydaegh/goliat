"""GOLIAT AI Assistant - Codebase-aware AI for debugging and assistance.

This module provides an AI assistant that understands the entire GOLIAT codebase
through embeddings, enabling natural language queries about the code, debugging
assistance, and intelligent recommendations.

Uses a simple RAG (Retrieval Augmented Generation) approach:
1. Index codebase with embeddings
2. Search for relevant chunks on query
3. Send context + query to LLM

Model Tiering (December 2025):
- Simple queries: gpt-5-mini (fast, cheap)
- Complex queries: gpt-5.1-codex (smart, coding-focused)
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from .config import AIConfig, get_default_config
from .types import BackendType, ComplexityType

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
        self._embeddings_cache: dict = {}
        self._index_ready = False
        self._session_costs = []  # Track costs per call
        self._total_cost = 0.0

        # Load pricing configuration (allows custom/discounted rates)
        self.PRICING = self._load_pricing_config()

        # Initialize OpenAI client
        self._init_openai()

        # Build or load the index
        self._ensure_index()

    def _classify_query_complexity(self, query: str) -> ComplexityType:
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
        if word_count <= 10:
            return "simple"
        elif word_count >= 25:
            return "complex"

        # Default to simple for cost efficiency
        return "simple"

    def _select_model(self, query: str, force_complex: Optional[bool] = None) -> str:
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
        complexity = self._classify_query_complexity(query)

        if complexity == "simple":
            return self.config.models.simple
        else:
            return self.config.models.complex

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

        self.client = OpenAI(api_key=api_key)

    def _load_pricing_config(self) -> dict:
        """Load pricing configuration from file or environment, with defaults as fallback.

        Looks for:
        1. data/.goliat_pricing.json (project-specific pricing with your discounts)
        2. Environment variables (OPENAI_PRICING_*)
        3. Default pricing

        Returns:
            Pricing dictionary
        """
        pricing = self.config.pricing.models.copy()

        # Deep copy nested dicts
        for model in pricing:
            pricing[model] = pricing[model].copy()

        # Try to load from config file
        config_path = os.path.join(self.base_dir, "data", ".goliat_pricing.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, encoding="utf-8") as f:
                    file_pricing = json.load(f)
                    # Merge with defaults (file takes precedence)
                    for model, rates in file_pricing.items():
                        if model in pricing:
                            pricing[model].update(rates)
                        else:
                            pricing[model] = rates
            except Exception:
                pass

        # Override with environment variables if set
        # Format: OPENAI_PRICING_GPT5MINI_INPUT=0.25
        for key, value in os.environ.items():
            if key.startswith("OPENAI_PRICING_"):
                try:
                    parts = key.replace("OPENAI_PRICING_", "").lower().split("_")
                    if len(parts) >= 2:
                        model_raw = "_".join(parts[:-1])
                        rate_type = parts[-1]
                        # Normalize model names
                        model_map = {
                            "gpt4omini": "gpt-4o-mini",
                            "gpt4o": "gpt-4o",
                            "textembedding3large": "text-embedding-3-large",
                            "textembedding3small": "text-embedding-3-small",
                        }
                        model = model_map.get(model_raw, model_raw)

                        if model in pricing:
                            pricing[model][rate_type] = float(value)
                except Exception:
                    pass

        return pricing

    def get_cost_summary(self) -> dict:
        """Get cost summary for current session.

        Returns:
            Dictionary with total_cost, call_count, breakdown, and pricing info.
        """
        return {
            "total_cost": self._total_cost,
            "call_count": len(self._session_costs),
            "breakdown": self._session_costs.copy(),
            "pricing_config": self.PRICING.copy(),
        }

    def _calculate_cost(self, model: str, usage: dict) -> float:
        """Calculate cost from token usage using configured pricing.

        Args:
            model: Model name (e.g., "gpt-5-mini", "text-embedding-3-large")
            usage: Usage dict with prompt_tokens, completion_tokens, total_tokens

        Returns:
            Cost in USD
        """
        if model not in self.PRICING:
            return 0.0

        cost = 0.0
        pricing = self.PRICING[model]

        if "input" in pricing:
            input_tokens = usage.get("prompt_tokens", 0)
            cost += (input_tokens / 1_000_000) * pricing["input"]

        if "output" in pricing:
            output_tokens = usage.get("completion_tokens", 0)
            cost += (output_tokens / 1_000_000) * pricing["output"]

        return cost

    def _ensure_index(self):
        """Ensure the embedding index is ready."""
        if self._index_ready:
            return

        cache_path = os.path.join(self.base_dir, "data", ".goliat_ai_cache.json")
        current_hash = self._compute_codebase_hash()

        # Check if cached index exists and can be loaded
        if os.path.exists(cache_path):
            try:
                with open(cache_path, encoding="utf-8") as f:
                    cache = json.load(f)

                cached_hash = cache.get("index_hash")
                cached_model = cache.get("embedding_model", "text-embedding-3-small")
                has_embeddings = "embeddings" in cache and len(cache.get("embeddings", {})) > 0

                # Check if we need to rebuild due to model change
                if cached_model != self.config.models.embedding:
                    print(f"[INFO] Embedding model changed ({cached_model} → {self.config.models.embedding}), rebuilding index...")
                elif has_embeddings:
                    # Use cache even if hash mismatches
                    self._embeddings_cache = cache["embeddings"]
                    if cached_hash != current_hash:
                        print("[WARNING] Using cached index, but codebase has changed.")
                        print("         Run 'goliat ask --reindex' to rebuild with latest code.")
                    print(f"[INFO] Loaded cached index ({len(self._embeddings_cache)} chunks, model: {cached_model})")
                    self._index_ready = True
                    return
                else:
                    print("Cache has no embeddings, rebuilding index...")
            except json.JSONDecodeError:
                print("Cache file corrupted (JSON error), rebuilding index...")
            except Exception as e:
                print(f"Error loading cache ({type(e).__name__}), rebuilding index...")

        # Build new index
        print(f"Building codebase index with {self.config.models.embedding}...")
        self._build_index()

        # Save cache
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(
                {"index_hash": current_hash, "embedding_model": self.config.models.embedding, "embeddings": self._embeddings_cache}, f
            )

        print(f"[INFO] Index ready ({len(self._embeddings_cache)} chunks)")
        self._index_ready = True

    def _build_index(self):
        """Build the embedding index for the codebase."""
        files = self._collect_files_for_indexing()
        chunks = []

        for file_path in files:
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                rel_path = os.path.relpath(file_path, self.base_dir)
                file_chunks = self._chunk_file(content, rel_path)
                chunks.extend(file_chunks)
            except Exception as e:
                print(f"  Warning: Could not process {file_path}: {e}")

        print(f"  Embedding {len(chunks)} chunks with {self.config.models.embedding}...")

        # Embed in batches with retry logic
        batch_size = self.config.processing.embedding_batch_size
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["content"] for c in batch]

            for attempt in range(self.config.processing.max_retries):
                try:
                    response = self.client.embeddings.create(model=self.config.models.embedding, input=texts)

                    for j, embedding_data in enumerate(response.data):
                        chunk = batch[j]
                        chunk_id = f"{chunk['path']}:{i + j}"
                        self._embeddings_cache[chunk_id] = {
                            "content": chunk["content"],
                            "path": chunk["path"],
                            "embedding": embedding_data.embedding,
                        }
                    break
                except Exception as e:
                    error_str = str(e)
                    if "rate_limit" in error_str.lower() or "429" in error_str:
                        wait_time = (attempt + 1) * 2
                        if attempt < self.config.processing.max_retries - 1:
                            time.sleep(wait_time)
                            continue
                    print(f"  Warning: Embedding batch failed: {e}")
                    break

            if (i + batch_size) % 100 == 0:
                print(f"  Processed {min(i + batch_size, len(chunks))}/{len(chunks)}")

    def _compute_codebase_hash(self) -> str:
        """Compute hash of codebase to detect changes."""
        hasher = hashlib.md5()

        for file_path in sorted(self._collect_files_for_indexing()):
            try:
                with open(file_path, "rb") as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                hasher.update(f"{file_path}:{file_hash}".encode())
            except Exception:
                pass

        return hasher.hexdigest()[: self.config.processing.hash_length]

    def _collect_files_for_indexing(self) -> list[str]:
        """Collect all files to index."""
        files = []

        # Python files in goliat/
        goliat_dir = os.path.join(self.base_dir, "goliat")
        if os.path.exists(goliat_dir):
            for root, _, filenames in os.walk(goliat_dir):
                if "__pycache__" in root or ".git" in root:
                    continue
                for filename in filenames:
                    if filename.endswith(".py"):
                        files.append(os.path.join(root, filename))

        # Python files in cli/
        cli_dir = os.path.join(self.base_dir, "cli")
        if os.path.exists(cli_dir):
            for root, _, filenames in os.walk(cli_dir):
                if "__pycache__" in root:
                    continue
                for filename in filenames:
                    if filename.endswith(".py"):
                        files.append(os.path.join(root, filename))

        # Markdown docs
        docs_dir = os.path.join(self.base_dir, "docs")
        if os.path.exists(docs_dir):
            for root, _, filenames in os.walk(docs_dir):
                for filename in filenames:
                    if filename.endswith(".md"):
                        files.append(os.path.join(root, filename))

        # Config examples
        configs_dir = os.path.join(self.base_dir, "configs")
        if os.path.exists(configs_dir):
            for filename in ["base_config.json", "near_field_config.json", "far_field_config.json"]:
                path = os.path.join(configs_dir, filename)
                if os.path.exists(path):
                    files.append(path)

        # README
        readme = os.path.join(self.base_dir, "README.md")
        if os.path.exists(readme):
            files.append(readme)

        return files

    def _chunk_file(self, content: str, path: str) -> list[dict]:
        """Split a file into chunks for embedding with overlap.

        Uses CHUNK_SIZE and CHUNK_OVERLAP class parameters.
        Overlap helps preserve context across chunk boundaries.
        """
        chunks = []
        lines = content.split("\n")
        current_chunk = []
        current_size = 0
        overlap_buffer = []  # Lines to carry over for overlap

        for line in lines:
            current_chunk.append(line)
            current_size += len(line) + 1

            if current_size >= self.config.rag.chunk_size:
                chunk_text = "\n".join(current_chunk)
                chunks.append({"content": f"# File: {path}\n\n{chunk_text}", "path": path})

                # Keep last N chars worth of lines for overlap
                overlap_size = 0
                overlap_buffer = []
                for line in reversed(current_chunk):
                    overlap_size += len(line) + 1
                    overlap_buffer.insert(0, line)
                    if overlap_size >= self.config.rag.chunk_overlap:
                        break

                current_chunk = overlap_buffer.copy()
                current_size = sum(len(line) + 1 for line in current_chunk)

        # Don't forget remaining content
        if current_chunk and current_size > self.config.rag.chunk_overlap:
            chunk_text = "\n".join(current_chunk)
            chunks.append({"content": f"# File: {path}\n\n{chunk_text}", "path": path})

        return chunks if chunks else [{"content": f"# File: {path}\n\n{content}", "path": path}]

    def _search(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        """Search for relevant chunks using embedding similarity.

        Args:
            query: Search query
            top_k: Number of chunks to return (default: config.rag.top_k_chunks)
        """
        if top_k is None:
            top_k = self.config.rag.top_k_chunks
        response = self.client.embeddings.create(model=self.config.models.embedding, input=[query])

        # Track embedding cost
        if hasattr(response, "usage"):
            usage = {"prompt_tokens": response.usage.prompt_tokens, "total_tokens": response.usage.total_tokens}
            cost = self._calculate_cost(self.config.models.embedding, usage)
            self._total_cost += cost
            self._session_costs.append(
                {"type": "embedding", "model": self.config.models.embedding, "tokens": usage["total_tokens"], "cost": cost}
            )

        query_embedding = response.data[0].embedding

        # Compute similarities
        import math

        def cosine_similarity(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0

        scored = []
        for chunk_id, chunk_data in self._embeddings_cache.items():
            score = cosine_similarity(query_embedding, chunk_data["embedding"])
            scored.append((score, chunk_data))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

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
        self._ensure_index()

        # Select model based on query complexity
        model = self._select_model(question, force_complex=force_complex)
        complexity = self._classify_query_complexity(question)

        # Search for relevant chunks
        relevant_chunks = self._search(question)

        # Build context from retrieved chunks
        retrieved_context = "\n\n---\n\n".join(chunk["content"] for chunk in relevant_chunks)

        # Build the prompt
        user_message = f"""Based on the following code/documentation from the GOLIAT codebase:

{retrieved_context}

{f"Additional context provided by user: {context}" if context else ""}

Question: {question}

Please provide a helpful, accurate answer based on the GOLIAT codebase."""

        # Call the selected model
        # GPT-5 models use max_completion_tokens instead of max_tokens
        # GPT-5 models only support default temperature (1), so don't set it
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
            cost = self._calculate_cost(model, usage)
            self._total_cost += cost
            self._session_costs.append(
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

    def chat(self):
        """Start an interactive chat session."""
        print("\n" + "=" * 60)
        print("GOLIAT AI Assistant - Interactive Chat")
        print("=" * 60)
        print("Model selection: simple queries → gpt-5-mini, complex → gpt-5.1-codex")
        print("Ask anything about GOLIAT. Type 'exit' or 'quit' to end.\n")

        conversation_history = []

        while True:
            try:
                user_input = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            if user_input.lower() == "cost":
                summary = self.get_cost_summary()
                print(f"\n{'=' * 60}")
                print("Cost Summary:")
                print(f"  Total calls: {summary['call_count']}")
                print(f"  Total cost: ${summary['total_cost']:.6f}")
                if summary["breakdown"]:
                    print("\nBreakdown:")
                    for i, call in enumerate(summary["breakdown"], 1):
                        if call["type"] == "chat":
                            model_info = f"{call['model']} ({call.get('complexity', 'unknown')})"
                            print(f"  {i}. {model_info}: {call['input_tokens']} in + {call['output_tokens']} out = ${call['cost']:.6f}")
                        else:
                            print(f"  {i}. {call['model']}: {call['tokens']} tokens = ${call['cost']:.6f}")
                print(f"{'=' * 60}\n")
                continue

            # Select model and show which one is being used
            model = self._select_model(user_input)
            complexity = self._classify_query_complexity(user_input)
            print(f"\n[{complexity} query → {model}]")
            print("Assistant: ", end="", flush=True)

            # For chat, include conversation history
            self._ensure_index()
            relevant_chunks = self._search(user_input)
            retrieved_context = "\n\n---\n\n".join(chunk["content"] for chunk in relevant_chunks)

            messages = [{"role": "system", "content": self.config.system_prompt + f"\n\nRelevant code context:\n{retrieved_context}"}]
            messages.extend(conversation_history[-self.config.processing.chat_history_messages :])
            messages.append({"role": "user", "content": user_input})

            # GPT-5 models use max_completion_tokens instead of max_tokens
            # GPT-5 models only support default temperature (1), so don't set it
            create_kwargs = {
                "model": model,
                "messages": messages,
            }
            if model.startswith("gpt-5"):
                create_kwargs["max_completion_tokens"] = self.config.llm.max_output_tokens
                # GPT-5 only supports default temperature (1), don't set it
            else:
                create_kwargs["max_tokens"] = self.config.llm.max_output_tokens
                # Set temperature for older models
                temperature = self.config.llm.temperature_complex if complexity == "complex" else self.config.llm.temperature_simple
                create_kwargs["temperature"] = temperature

            response = self.client.chat.completions.create(**create_kwargs)

            # Track cost
            cost = 0.0
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                cost = self._calculate_cost(model, usage)
                self._total_cost += cost
                self._session_costs.append(
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

            answer = response.choices[0].message.content
            print(answer)

            # Show cost
            if cost > 0:
                print(f"\n[Cost: ${cost:.6f} | Total: ${self._total_cost:.6f}]")

            print()

            # Update history
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": answer})

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
{log_output[-3000:]}
```

If there are concerning patterns (errors, excessive retries, warnings), explain what's wrong and how to fix it.
If the logs look normal, just say "Logs look healthy."
Be concise."""

        # Use complex model for log analysis
        return self.ask(question, force_complex=True)

    def reindex(self):
        """Force reindex of the codebase."""
        cache_path = os.path.join(self.base_dir, "data", ".goliat_ai_cache.json")

        if os.path.exists(cache_path):
            os.remove(cache_path)
            print("✓ Cleared existing cache.")

        self._embeddings_cache = {}
        self._index_ready = False

        print(f"Rebuilding index with {self.config.models.embedding}...")
        self._ensure_index()
