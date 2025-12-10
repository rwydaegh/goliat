"""Cost tracking and calculation for AI API usage."""

import json
import os

from .config import AIConfig


class CostTracker:
    """Tracks API costs and calculates pricing."""

    def __init__(self, config: AIConfig, base_dir: str):
        """Initialize the cost tracker.

        Args:
            config: AI configuration
            base_dir: Base directory of GOLIAT project
        """
        self.config = config
        self.base_dir = base_dir
        self._session_costs = []  # Track costs per call
        self._total_cost = 0.0
        self.pricing = self._load_pricing_config()

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
        config_path = os.path.join(self.base_dir, self.config.indexing.pricing_config_file)
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

    def calculate_cost(self, model: str, usage: dict) -> float:
        """Calculate cost from token usage using configured pricing.

        Args:
            model: Model name (e.g., "gpt-5-mini", "text-embedding-3-large")
            usage: Usage dict with prompt_tokens, completion_tokens, total_tokens

        Returns:
            Cost in USD
        """
        if model not in self.pricing:
            return 0.0

        cost = 0.0
        pricing = self.pricing[model]

        if "input" in pricing:
            input_tokens = usage.get("prompt_tokens", 0)
            cost += (input_tokens / 1_000_000) * pricing["input"]

        if "output" in pricing:
            output_tokens = usage.get("completion_tokens", 0)
            cost += (output_tokens / 1_000_000) * pricing["output"]

        return cost

    def track_call(self, call_info: dict) -> None:
        """Track an API call and its cost.

        Args:
            call_info: Dictionary with call details including 'cost'
        """
        cost = call_info.get("cost", 0.0)
        self._total_cost += cost
        self._session_costs.append(call_info)

    def get_summary(self) -> dict:
        """Get cost summary for current session.

        Returns:
            Dictionary with total_cost, call_count, breakdown, and pricing info.
        """
        return {
            "total_cost": self._total_cost,
            "call_count": len(self._session_costs),
            "breakdown": self._session_costs.copy(),
            "pricing_config": self.pricing.copy(),
        }

    def reset(self) -> None:
        """Reset cost tracking for a new session."""
        self._session_costs = []
        self._total_cost = 0.0
