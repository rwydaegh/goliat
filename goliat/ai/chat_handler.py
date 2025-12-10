"""Interactive chat handler for GOLIAT AI Assistant."""

from .config import AIConfig
from .cost_tracker import CostTracker
from .embedding_indexer import EmbeddingIndexer
from .query_processor import QueryProcessor


class ChatHandler:
    """Handles interactive chat sessions."""

    def __init__(
        self,
        config: AIConfig,
        indexer: EmbeddingIndexer,
        query_processor: QueryProcessor,
        cost_tracker: CostTracker,
        client,
    ):
        """Initialize the chat handler.

        Args:
            config: AI configuration
            indexer: Embedding indexer instance
            query_processor: Query processor instance
            cost_tracker: Cost tracker instance
            client: OpenAI client instance
        """
        self.config = config
        self.indexer = indexer
        self.query_processor = query_processor
        self.cost_tracker = cost_tracker
        self.client = client

    def start_chat(self) -> None:
        """Start an interactive chat session."""
        print("\n" + "=" * 60)
        print("GOLIAT AI Assistant - Interactive Chat")
        print("=" * 60)
        print("Model selection: simple queries → gpt-5-mini, complex → gpt-5")
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
                self._show_cost_summary()
                continue

            # Select model and show which one is being used (single call to avoid duplicate classification)
            model, complexity = self.query_processor.select_model_with_complexity(user_input)
            print(f"\n[{complexity} query → {model}]")
            print("Assistant: ", end="", flush=True)

            # For chat, include conversation history
            self.indexer.ensure_index()
            relevant_chunks = self.indexer.search(user_input, cost_tracker=self.cost_tracker)
            retrieved_context = "\n\n---\n\n".join(chunk["content"] for chunk in relevant_chunks)

            messages = [
                {
                    "role": "system",
                    "content": self.config.system_prompt + f"\n\nRelevant code context:\n{retrieved_context}",
                }
            ]
            messages.extend(conversation_history[-self.config.processing.chat_history_messages :])
            messages.append({"role": "user", "content": user_input})

            # Build API call kwargs
            create_kwargs = self._build_chat_kwargs(model, complexity, messages)

            response = self.client.chat.completions.create(**create_kwargs)

            # Track cost
            cost = 0.0
            if hasattr(response, "usage") and response.usage:
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

            answer = response.choices[0].message.content
            print(answer)

            # Show cost
            if cost > 0:
                print(f"\n[Cost: ${cost:.6f} | Total: ${self.cost_tracker._total_cost:.6f}]")

            print()

            # Update history
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": answer})

    def _build_chat_kwargs(self, model: str, complexity: str, messages: list) -> dict:
        """Build kwargs for chat completion API call.

        Args:
            model: Model name
            complexity: Query complexity ("simple" or "complex")
            messages: List of message dicts

        Returns:
            Dictionary of kwargs for API call
        """
        create_kwargs = {
            "model": model,
            "messages": messages,
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

        return create_kwargs

    def _show_cost_summary(self) -> None:
        """Display cost summary to user."""
        summary = self.cost_tracker.get_summary()
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
