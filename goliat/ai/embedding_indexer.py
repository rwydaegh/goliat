"""Embedding indexer for codebase indexing and retrieval."""

import hashlib
import json
import os
import time
from typing import Optional

from .config import AIConfig


class EmbeddingIndexer:
    """Handles codebase indexing, chunking, and embedding storage."""

    def __init__(self, config: AIConfig, base_dir: str, client):
        """Initialize the indexer.

        Args:
            config: AI configuration
            base_dir: Base directory of GOLIAT project
            client: OpenAI client instance
        """
        self.config = config
        self.base_dir = base_dir
        self.client = client
        self._embeddings_cache: dict = {}
        self._index_ready = False

    def ensure_index(self) -> None:
        """Ensure the embedding index is ready."""
        if self._index_ready:
            return

        cache_path = os.path.join(self.base_dir, self.config.indexing.cache_file)
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

    def _build_index(self) -> None:
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
                    rate_limit_code = str(self.config.processing.rate_limit_status_code)
                    if "rate_limit" in error_str.lower() or rate_limit_code in error_str:
                        wait_time = (attempt + 1) * self.config.processing.rate_limit_wait_multiplier
                        if attempt < self.config.processing.max_retries - 1:
                            time.sleep(wait_time)
                            continue
                    print(f"  Warning: Embedding batch failed: {e}")
                    break

            if (i + batch_size) % self.config.processing.progress_print_interval == 0:
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
        """Collect all files to index based on configuration."""
        files = []
        exclude_dirs_set = set(self.config.indexing.exclude_dirs)

        # Process configured directories
        for dir_name in self.config.indexing.index_directories:
            dir_path = os.path.join(self.base_dir, dir_name)
            if not os.path.exists(dir_path):
                continue

            for root, _, filenames in os.walk(dir_path):
                # Skip excluded directories
                if any(excluded in root for excluded in exclude_dirs_set):
                    continue

                for filename in filenames:
                    file_path = os.path.join(root, filename)

                    # Check Python patterns
                    if any(filename.endswith(pattern.replace("*", "")) for pattern in self.config.indexing.python_patterns):
                        files.append(file_path)
                    # Check Markdown patterns
                    elif any(filename.endswith(pattern.replace("*", "")) for pattern in self.config.indexing.markdown_patterns):
                        files.append(file_path)

        # Add specific config files
        configs_dir = os.path.join(self.base_dir, "configs")
        if os.path.exists(configs_dir):
            for filename in self.config.indexing.config_files:
                path = os.path.join(configs_dir, filename)
                if os.path.exists(path):
                    files.append(path)

        # Add README if it exists
        readme = os.path.join(self.base_dir, "README.md")
        if os.path.exists(readme):
            files.append(readme)

        return files

    def _chunk_file(self, content: str, path: str) -> list[dict]:
        """Split a file into chunks for embedding with overlap."""
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

    def search(self, query: str, top_k: Optional[int] = None, cost_tracker=None) -> list[dict]:
        """Search for relevant chunks using embedding similarity.

        Args:
            query: Search query
            top_k: Number of chunks to return (default: config.rag.top_k_chunks)
            cost_tracker: Optional cost tracker to record embedding costs

        Returns:
            List of relevant chunks sorted by similarity
        """
        if top_k is None:
            top_k = self.config.rag.top_k_chunks
        response = self.client.embeddings.create(model=self.config.models.embedding, input=[query])

        # Track embedding cost if tracker provided
        if cost_tracker and hasattr(response, "usage"):
            usage = {"prompt_tokens": response.usage.prompt_tokens, "total_tokens": response.usage.total_tokens}
            cost = cost_tracker.calculate_cost(self.config.models.embedding, usage)
            cost_tracker.track_call(
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

    def clear_cache(self) -> None:
        """Clear the index cache and force rebuild."""
        cache_path = os.path.join(self.base_dir, self.config.indexing.cache_file)

        if os.path.exists(cache_path):
            os.remove(cache_path)
            print("✓ Cleared existing cache.")

        self._embeddings_cache = {}
        self._index_ready = False

    @property
    def is_ready(self) -> bool:
        """Check if index is ready."""
        return self._index_ready
