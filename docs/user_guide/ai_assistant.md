# AI assistant

GOLIAT has an integrated **AI assistant** for querying the codebase and documentation in natural language. It uses Retrieval-Augmented Generation (RAG), indexing all Python files, Markdown docs, and JSON configs.

## Usage

```bash
goliat ai "Your question here"
```

For multi-turn conversation:

```bash
goliat ai --interactive
```

### Model selection

By default, the assistant classifies query complexity and picks a model automatically. Override this with:

- `--simple`: Force the simpler (cheaper) model
- `--complex`: Force the more capable model

### Example queries

- *"How does phantom rotation work?"*
- *"Where is the heatmap generation logic?"*
- *"How do I configure subgridding?"*
- *"Why am I getting a CUDA error?"*

## Features

- **Context-aware**: Understands project structure and retrieves relevant code snippets.
- **Code citations**: Points to specific files and line numbers.
- **Cost tracking**: Shows token usage and estimated cost after each query.
- **Markdown output**: Responses are formatted with syntax highlighting.

## Setup

Copy the repository's example environment file and add your OpenAI API key:

```text
cp .env.example .env
# Edit .env and set OPENAI_API_KEY.
```

The `.env` file is local and ignored by Git. You can alternatively export
`OPENAI_API_KEY` in the process environment.

Optional: Install with `pip install goliat[ai]` for the `rich` library (better terminal formatting).
