# AI Assistant

GOLIAT features an integrated **AI Assistant** that allows you to query the codebase and documentation using natural language. It's designed to help you understand how GOLIAT works, find specific functionality, or troubleshoot issues without digging through source code or static docs.

## Overview

The assistant uses Retrieval-Augmented Generation (RAG) to provide context-aware answers. It indexes:
- The entire GOLIAT codebase (Python files)
- All Markdown documentation
- JSON configuration schemas

## Usage

To use the assistant, run the following command:

```bash
goliat ai "Your question here"
```

Or for an interactive session:

```bash
goliat ai --interactive
```

### Example Queries

Here are some things you can ask:

- **Concepts**: *"How does the phantom rotation work?"* or *"What is the difference between local and cloud execution?"*
- **Codebase**: *"Where is the heat map generation logic?"* or *"Show me the `SimulationManager` class."*
- **Configuration**: *"block for near-field simulation?"* or *"How do I add a new material?"*
- **Troubleshooting**: *"Why am I getting a CUDA error?"*

## Features

- **Context-Aware**: Understands the structure of the GOLIAT project.
- **Code Citations**: Points you to specific files and lines of code.
- **Markdown Output**: Responses are formatted with syntax highlighting and links.
- **Interactive Mode**: Have a multi-turn conversation to refine your query.
