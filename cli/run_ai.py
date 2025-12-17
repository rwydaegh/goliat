"""CLI entry point for GOLIAT AI Assistant.

Provides 'goliat ask', 'goliat chat', and 'goliat debug' commands.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# ============================================================================
# CLI Configuration - All tunable parameters in one place
# ============================================================================
SHELL_HISTORY_LINES = 20  # Recent shell commands to capture
SHELL_HISTORY_FALLBACK = 10  # Fallback if main history fails
LOG_RECENCY_SECONDS = 3600  # Logs modified within this time (1 hour)
MAX_LOG_FILES = 3  # Most recent log sessions to include (each session = 2 files: .log + .progress.log)
SPINNER_FRAMES = ["   ", ".  ", ".. ", "..."]  # Simple dot animation (fixed width)
SPINNER_INTERVAL = 0.3  # Seconds between frames


@contextmanager
def thinking_spinner(message: str = "Thinking"):
    """Display a minimal thinking animation while processing.

    Usage:
        with thinking_spinner("Analyzing"):
            result = slow_operation()
    """
    # Check if we're in an interactive terminal
    is_tty = sys.stdout.isatty()

    if not is_tty:
        # Non-interactive: just print static message
        print(f"{message}...")
        yield
        return

    stop_event = threading.Event()
    current_frame = [0]
    line_length = len(message) + 4  # message + dots + buffer

    def spin():
        while not stop_event.is_set():
            frame = SPINNER_FRAMES[current_frame[0] % len(SPINNER_FRAMES)]
            # Build fixed-width output, return to start of line
            sys.stdout.write(f"\r{message}{frame}")
            sys.stdout.flush()
            current_frame[0] += 1
            stop_event.wait(SPINNER_INTERVAL)

    spinner_thread = threading.Thread(target=spin, daemon=True)
    spinner_thread.start()

    try:
        yield
    finally:
        stop_event.set()
        spinner_thread.join(timeout=1)
        # Clear the spinner line completely
        sys.stdout.write(f"\r{' ' * line_length}\r")
        sys.stdout.flush()


def print_markdown(text: str) -> None:
    """Print markdown text with nice formatting.

    Uses `rich` library if available for beautiful rendering,
    otherwise falls back to basic ANSI formatting.

    Install rich for best results: pip install goliat[ai]
    """
    try:
        from rich.console import Console
        from rich.markdown import Markdown

        console = Console()
        console.print(Markdown(text))
    except ImportError:
        # Fallback: basic ANSI formatting
        _print_markdown_simple(text)


def _print_markdown_simple(text: str) -> None:
    """Simple markdown formatter using ANSI codes (fallback when rich not installed)."""
    # ANSI codes
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    RESET = "\033[0m"

    lines = text.split("\n")
    in_code_block = False
    code_lang = ""

    for line in lines:
        # Code blocks
        if line.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lang = line[3:].strip()
                if code_lang:
                    print(f"{DIM}[{code_lang}]{RESET}")
                print(f"{DIM}{'-' * 40}{RESET}")
            else:
                in_code_block = False
                print(f"{DIM}{'-' * 40}{RESET}")
            continue

        if in_code_block:
            print(f"{CYAN}  {line}{RESET}")
            continue

        # Headers
        if line.startswith("### "):
            print(f"\n{BOLD}{line[4:]}{RESET}")
        elif line.startswith("## "):
            print(f"\n{BOLD}{UNDERLINE}{line[3:]}{RESET}")
        elif line.startswith("# "):
            print(f"\n{BOLD}{UNDERLINE}{line[2:]}{RESET}\n")
        # Bullet points (check before bold to handle bullets with bold)
        elif line.strip().startswith("- "):
            indent = len(line) - len(line.lstrip())
            content = line.strip()[2:]
            # Handle bold in bullet points
            content = re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", content)
            # Handle inline code in bullet points
            content = re.sub(r"`([^`]+)`", f"{CYAN}\\1{RESET}", content)
            print(f"{' ' * indent}{GREEN}*{RESET} {content}")
        # Bold
        elif "**" in line:
            # Replace **text** with bold
            formatted = re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", line)
            # Also handle inline code
            formatted = re.sub(r"`([^`]+)`", f"{CYAN}\\1{RESET}", formatted)
            print(formatted)
        # Inline code
        elif "`" in line and not line.startswith("```"):
            formatted = re.sub(r"`([^`]+)`", f"{CYAN}\\1{RESET}", line)
            print(formatted)
        else:
            print(line)


def _init_assistant():
    """Initialize and return the GOLIAT assistant."""
    try:
        from goliat.ai.assistant import GOLIATAssistant

        return GOLIATAssistant()
    except ImportError as e:
        print(f"Error initializing AI assistant: {e}")
        print("\nMake sure you have set OPENAI_API_KEY in your environment or .env file.")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing AI assistant: {e}")
        print("\nMake sure you have set OPENAI_API_KEY in your environment or .env file.")
        sys.exit(1)


def main_ask():
    """Entry point for 'goliat ask' command."""
    parser = argparse.ArgumentParser(description="Ask the GOLIAT AI Assistant a question.")
    parser.add_argument("question", nargs="?", default=None, help="The question to ask.")
    parser.add_argument("--debug", type=str, default=None, help="Provide an error message to debug.")
    parser.add_argument("--logs", type=str, default=None, help="Path to a log file for context.")
    parser.add_argument("--config", type=str, default=None, help="Path to a config file for context.")
    parser.add_argument("--backend", type=str, default="openai", help="AI backend to use (openai).")
    parser.add_argument("--reindex", action="store_true", help="Force rebuild of the codebase index.")

    # Model selection group (mutually exclusive)
    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument("--simple", action="store_true", help="Force simple model (gpt-5-mini).")
    model_group.add_argument("--complex", action="store_true", help="Force complex model (gpt-5).")

    args = parser.parse_args()

    assistant = _init_assistant()

    # Handle reindex
    if args.reindex:
        assistant.reindex()
        print("Index will be rebuilt on next query.")
        return

    # Handle debug mode
    if args.debug:
        log_context = ""
        if args.logs:
            try:
                with open(args.logs, encoding="utf-8", errors="ignore") as f:
                    log_context = f.read()  # Full content - we have 400K context
            except Exception as e:
                print(f"Warning: Could not read logs from {args.logs}: {e}")

        config_context = ""
        if args.config:
            try:
                with open(args.config) as f:
                    config_context = f.read()  # Full content
            except Exception as e:
                print(f"Warning: Could not read config from {args.config}: {e}")

        print()
        with thinking_spinner("Analyzing"):
            response = assistant.debug(args.debug, log_context, config_context)
        print_markdown(response)
        return

    # Handle question
    if args.question:
        print()

        # Determine model selection mode and classify if auto
        if args.simple:
            force_complex = False
            mode_str = "forced"
            model_name = assistant.config.models.simple
            complexity = "simple"
            classify_time = 0.0
        elif args.complex:
            force_complex = True
            mode_str = "forced"
            model_name = assistant.config.models.complex
            complexity = "complex"
            classify_time = 0.0
        else:
            mode_str = "auto"
            # Classify with timing
            start_time = time.time()
            model_name, complexity = assistant.query_processor.select_model_with_complexity(args.question)
            classify_time = time.time() - start_time
            # Pass result to avoid re-classification in ask()
            force_complex = complexity == "complex"

        # Show process info
        print(f"Mode: {mode_str} | Complexity: {complexity} | Model: {model_name}", end="")
        if classify_time > 0:
            print(f" | Classified in {classify_time:.2f}s")
        else:
            print()

        # Run the query with spinner
        start_time = time.time()
        with thinking_spinner("Thinking"):
            response = assistant.ask(args.question, force_complex=force_complex)
        query_time = time.time() - start_time

        print_markdown(response)

        # Show cost and timing
        summary = assistant.get_cost_summary()
        if summary["call_count"] > 0:
            last_call = summary["breakdown"][-1]
            last_cost = last_call["cost"]
            tokens_in = last_call.get("input_tokens", 0)
            tokens_out = last_call.get("output_tokens", 0)
            print(
                f"\n[Cost: ${last_cost:.6f} | Tokens: {tokens_in} in / {tokens_out} out | Time: {query_time:.1f}s | Session: ${summary['total_cost']:.6f}]"
            )
        return

    # No arguments
    parser.print_help()


def main_chat():
    """Entry point for 'goliat chat' command."""
    parser = argparse.ArgumentParser(description="Start an interactive chat with GOLIAT AI Assistant.")
    parser.add_argument("--backend", type=str, default="openai", help="AI backend to use (openai).")

    parser.parse_args()

    assistant = _init_assistant()

    print("\n[Tip] Type 'cost' to see cost summary, 'exit' to quit\n")

    assistant.chat()

    # Show final cost summary
    summary = assistant.get_cost_summary()
    if summary["total_cost"] > 0:
        print(f"\n{'=' * 60}")
        print("Session Cost Summary:")
        print(f"  Total calls: {summary['call_count']}")
        print(f"  Total cost: ${summary['total_cost']:.6f}")
        print(f"{'=' * 60}")


def _gather_shell_context(log_count: int = MAX_LOG_FILES) -> dict:
    """Gather context from the current shell session.

    Args:
        log_count: Number of recent log files to include (default: MAX_LOG_FILES)

    Returns:
        Dictionary with shell history, environment, working directory, etc.
    """
    context = {"history": [], "cwd": os.getcwd(), "env": {}, "recent_logs": []}

    # Try to get current shell session history (not global history file)
    try:
        # First, try using the 'history' command which shows current session
        # This works in bash/zsh and shows only commands from current shell
        result = subprocess.run(["history"], shell=True, capture_output=True, text=True, timeout=2, env=os.environ.copy())
        if result.returncode == 0 and result.stdout:
            # Parse history output (format: " 1234  command")
            lines = result.stdout.strip().split("\n")
            # Get last N commands, remove line numbers
            history_lines = []
            for line in lines[-SHELL_HISTORY_LINES:]:
                # Remove leading whitespace and line number
                parts = line.strip().split(None, 1)
                if len(parts) > 1:
                    history_lines.append(parts[1])  # Just the command
            context["history"] = history_lines
        else:
            # Fallback: try HISTFILE might point to current session
            histfile = os.environ.get("HISTFILE")
            if histfile and os.path.exists(histfile):
                # This is the current session's history file
                with open(histfile, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    context["history"] = [line.strip() for line in lines[-SHELL_HISTORY_LINES:] if line.strip()]
    except Exception:
        # Fallback: try reading global bash_history
        try:
            hist_file = os.path.expanduser("~/.bash_history")
            if os.path.exists(hist_file):
                with open(hist_file, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    context["history"] = [line.strip() for line in lines[-SHELL_HISTORY_FALLBACK:] if line.strip()]
        except Exception:
            pass

    # Get relevant environment variables
    relevant_env = [
        "PATH",
        "PYTHONPATH",
        "SIM4LIFE_PATH",
        "GOLIAT_BASE_DIR",
        "OPENAI_API_KEY",  # Don't include value, just presence
    ]
    for key in relevant_env:
        if key in os.environ:
            if key == "OPENAI_API_KEY":
                context["env"][key] = "***set***"  # Don't expose API key
            else:
                context["env"][key] = os.environ[key]

    # Find recent GOLIAT log files
    try:
        cwd = Path(context["cwd"])
        # Look for logs in current directory and common locations
        log_dirs = [
            cwd / "logs",
            cwd / "data" / "logs",
            cwd.parent / "logs",
        ]

        for log_dir in log_dirs:
            if log_dir.exists():
                # GOLIAT log files come in pairs: TIMESTAMP.log (verbose) and TIMESTAMP.progress.log (less verbose)
                # Group by timestamp prefix to get pairs
                all_log_files = list(log_dir.glob("*.log"))

                # Group by timestamp prefix (everything before .log or .progress.log)
                log_pairs = {}
                for log_file in all_log_files:
                    name = log_file.name
                    # Extract timestamp prefix (remove .log or .progress.log)
                    if name.endswith(".progress.log"):
                        prefix = name[: -len(".progress.log")]
                    else:
                        prefix = name[: -len(".log")]

                    if prefix not in log_pairs:
                        log_pairs[prefix] = {}

                    if name.endswith(".progress.log"):
                        log_pairs[prefix]["progress"] = log_file
                    else:
                        log_pairs[prefix]["verbose"] = log_file

                # Sort pairs by most recent modification time (use verbose log's mtime)
                def get_pair_mtime(prefix):
                    pair = log_pairs[prefix]
                    # Use verbose log's mtime, or progress if verbose doesn't exist
                    if "verbose" in pair:
                        return pair["verbose"].stat().st_mtime
                    elif "progress" in pair:
                        return pair["progress"].stat().st_mtime
                    return 0

                sorted_pairs = sorted(log_pairs.keys(), key=get_pair_mtime, reverse=True)[:log_count]

                # Collect files from pairs (include both verbose and progress if available)
                for prefix in sorted_pairs:
                    pair = log_pairs[prefix]
                    # Include verbose log first (more detailed)
                    if "verbose" in pair:
                        log_file = pair["verbose"]
                        try:
                            with open(log_file, encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if log_file.stat().st_mtime > time.time() - LOG_RECENCY_SECONDS:
                                    context["recent_logs"].append({"file": str(log_file), "content": content})
                        except Exception:
                            pass
                    # Then include progress log (summary)
                    if "progress" in pair:
                        log_file = pair["progress"]
                        try:
                            with open(log_file, encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if log_file.stat().st_mtime > time.time() - LOG_RECENCY_SECONDS:
                                    context["recent_logs"].append({"file": str(log_file), "content": content})
                        except Exception:
                            pass
                break
    except Exception:
        pass

    return context


def create_debug_html(error_message: str, context: dict, response: str) -> str:
    """Create an HTML file with the debug conversation and return its path."""

    # Escape HTML entities
    def escape_html(text):
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

    # Enhanced markdown to HTML converter
    def markdown_to_html(md_text):
        if not md_text:
            return ""

        # Store code blocks temporarily to avoid processing markdown inside them
        code_blocks = []

        def store_code_block(match):
            idx = len(code_blocks)
            code_blocks.append(match.group(0))
            return f"__CODE_BLOCK_{idx}__"

        html = md_text

        # Step 1: Extract code blocks first (to avoid processing markdown inside them)
        html = re.sub(r"```(\w+)?\n(.*?)```", store_code_block, html, flags=re.DOTALL)

        # Step 2: Extract inline code (to avoid processing markdown inside them)
        inline_codes = []

        def store_inline_code(match):
            idx = len(inline_codes)
            inline_codes.append(match.group(0))
            return f"__INLINE_CODE_{idx}__"

        html = re.sub(r"`([^`]+)`", store_inline_code, html)

        # Step 3: Process block-level elements (headers, blockquotes, horizontal rules)
        # Headers (process from most specific to least)
        html = re.sub(r"^###### (.*)$", r"<h6>\1</h6>", html, flags=re.MULTILINE)
        html = re.sub(r"^##### (.*)$", r"<h5>\1</h5>", html, flags=re.MULTILINE)
        html = re.sub(r"^#### (.*)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
        html = re.sub(r"^### (.*)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.*)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.*)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

        # Horizontal rules
        html = re.sub(r"^---+\s*$", r"<hr>", html, flags=re.MULTILINE)
        html = re.sub(r"^\*\*\*\s*$", r"<hr>", html, flags=re.MULTILINE)

        # Blockquotes (process before other formatting to avoid recursion issues)
        def process_blockquotes(text):
            lines = text.split("\n")
            result = []
            in_quote = False
            quote_lines = []

            for line in lines:
                if line.strip().startswith(">"):
                    if not in_quote:
                        in_quote = True
                    # Remove > and any following space
                    quote_content = line.strip()[1:].strip()
                    quote_lines.append(quote_content)
                else:
                    if in_quote:
                        # Join quote lines and wrap in blockquote
                        # We'll process inline formatting later, so just store as-is for now
                        quote_content = "\n".join(quote_lines)
                        result.append(f"__BLOCKQUOTE_START__{quote_content}__BLOCKQUOTE_END__")
                        quote_lines = []
                        in_quote = False
                    result.append(line)

            if in_quote:
                quote_content = "\n".join(quote_lines)
                result.append(f"__BLOCKQUOTE_START__{quote_content}__BLOCKQUOTE_END__")

            return "\n".join(result)

        html = process_blockquotes(html)

        # Step 4: Process tables
        def process_tables(text):
            lines = text.split("\n")
            result = []
            i = 0

            while i < len(lines):
                line = lines[i]
                # Check if this line looks like a table (contains | and has multiple columns)
                if "|" in line:
                    # Try to find table
                    table_lines = []
                    j = i
                    while j < len(lines) and ("|" in lines[j] or lines[j].strip() == ""):
                        if lines[j].strip():
                            table_lines.append(lines[j])
                        j += 1

                    if len(table_lines) >= 2:  # At least header and separator
                        # Parse table
                        header = table_lines[0]
                        separator = table_lines[1] if len(table_lines) > 1 else ""
                        rows = table_lines[2:] if len(table_lines) > 2 else []

                        # Check if separator is valid (contains --- or ===)
                        # Also check that header has multiple cells (at least 2 pipes)
                        if re.match(r"^[\|\s\-:|]+$", separator) and header.count("|") >= 2:
                            # Build table HTML
                            table_html = "<table>\n<thead>\n<tr>"
                            # Split by | and filter empty strings at start/end
                            header_cells = [cell.strip() for cell in header.split("|")]
                            # Remove empty cells at start/end (from leading/trailing |)
                            if header_cells and not header_cells[0]:
                                header_cells = header_cells[1:]
                            if header_cells and not header_cells[-1]:
                                header_cells = header_cells[:-1]

                            for cell in header_cells:
                                table_html += f"<th>{cell}</th>"
                            table_html += "</tr>\n</thead>\n<tbody>"

                            for row in rows:
                                row_cells = [cell.strip() for cell in row.split("|")]
                                # Remove empty cells at start/end
                                if row_cells and not row_cells[0]:
                                    row_cells = row_cells[1:]
                                if row_cells and not row_cells[-1]:
                                    row_cells = row_cells[:-1]

                                if row_cells:
                                    table_html += "<tr>"
                                    for cell in row_cells:
                                        table_html += f"<td>{cell}</td>"
                                    table_html += "</tr>"

                            table_html += "</tbody>\n</table>"
                            result.append(table_html)
                            i = j
                            continue

                result.append(line)
                i += 1

            return "\n".join(result)

        html = process_tables(html)

        # Step 5: Process lists (ordered and unordered)
        def process_lists(text):
            lines = text.split("\n")
            result = []
            i = 0

            while i < len(lines):
                line = lines[i]

                # Check for unordered list
                if re.match(r"^[\*\-\+]\s+", line):
                    list_items = []
                    while i < len(lines) and re.match(r"^[\*\-\+]\s+", lines[i]):
                        item_text = re.sub(r"^[\*\-\+]\s+", "", lines[i])
                        # Handle nested lists (2+ spaces)
                        if item_text.startswith("  "):
                            item_text = item_text[2:]
                        list_items.append(item_text)
                        i += 1

                    list_html = "<ul>\n"
                    for item in list_items:
                        list_html += f"<li>{item}</li>\n"
                    list_html += "</ul>"
                    result.append(list_html)
                    continue

                # Check for ordered list
                elif re.match(r"^\d+\.\s+", line):
                    list_items = []
                    while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                        item_text = re.sub(r"^\d+\.\s+", "", lines[i])
                        # Handle nested lists (2+ spaces)
                        if item_text.startswith("  "):
                            item_text = item_text[2:]
                        list_items.append(item_text)
                        i += 1

                    list_html = "<ol>\n"
                    for item in list_items:
                        list_html += f"<li>{item}</li>\n"
                    list_html += "</ol>"
                    result.append(list_html)
                    continue

                result.append(line)
                i += 1

            return "\n".join(result)

        html = process_lists(html)

        # Step 6: Process inline formatting (bold, italic, strikethrough, links)
        # Bold (**text** or __text__)
        html = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"__(.*?)__", r"<strong>\1</strong>", html)

        # Italic (*text* or _text_) - but not if it's part of bold
        html = re.sub(r"(?<!\*)\*(?!\*)([^\*]+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", html)
        html = re.sub(r"(?<!_)_(?!_)([^_]+?)(?<!_)_(?!_)", r"<em>\1</em>", html)

        # Strikethrough
        html = re.sub(r"~~(.*?)~~", r"<del>\1</del>", html)

        # Links
        html = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r'<a href="\2">\1</a>', html)

        # Step 7: Convert blockquote markers to HTML
        # Process __BLOCKQUOTE_START__...__BLOCKQUOTE_END__ markers
        def convert_blockquotes(text):
            result = []
            i = 0
            while i < len(text):
                start_marker = "__BLOCKQUOTE_START__"
                end_marker = "__BLOCKQUOTE_END__"
                start_idx = text.find(start_marker, i)
                if start_idx == -1:
                    result.append(text[i:])
                    break
                result.append(text[i:start_idx])
                end_idx = text.find(end_marker, start_idx)
                if end_idx == -1:
                    result.append(text[start_idx:])
                    break
                quote_content = text[start_idx + len(start_marker) : end_idx]
                result.append(f"<blockquote>{quote_content}</blockquote>")
                i = end_idx + len(end_marker)
            return "".join(result)

        html = convert_blockquotes(html)

        # Step 8: Restore inline code
        for idx, code in enumerate(inline_codes):
            code_content = code[1:-1]  # Remove backticks
            html = html.replace(f"__INLINE_CODE_{idx}__", f"<code>{escape_html(code_content)}</code>")

        # Step 9: Process paragraphs (split by double newlines, but preserve lists, headers, etc.)
        def process_paragraphs(text):
            # Split by double newlines, but don't split inside block elements
            parts = re.split(r"\n\n+", text)
            result = []

            for part in parts:
                part = part.strip()
                if not part:
                    continue

                # Don't wrap block elements in <p>
                if (
                    part.startswith("<h")
                    or part.startswith("<ul")
                    or part.startswith("<ol")
                    or part.startswith("<table")
                    or part.startswith("<blockquote")
                    or part.startswith("<hr")
                    or part.startswith('<div class="code-wrapper"')
                ):
                    result.append(part)
                else:
                    # Convert single newlines to <br> within paragraphs
                    part = part.replace("\n", "<br>")
                    result.append(f"<p>{part}</p>")

            return "\n".join(result)

        html = process_paragraphs(html)

        # Step 10: Restore code blocks (with proper formatting)
        for idx, code_block in enumerate(code_blocks):
            match = re.match(r"```(\w+)?\n(.*?)```", code_block, flags=re.DOTALL)
            if match:
                lang = match.group(1) or "text"
                code_content = match.group(2)
                code_html = f'<div class="code-wrapper"><div class="code-header"><span class="lang">{lang}</span><button class="copy-btn" onclick="copyCode(this)">Copy</button></div><pre><code class="language-{lang}">{escape_html(code_content)}</code></pre></div>'
                html = html.replace(f"__CODE_BLOCK_{idx}__", code_html)

        return html

    # Format context sections
    context_html = ""
    if context.get("history"):
        history_text = "\n".join(context["history"][-SHELL_HISTORY_FALLBACK:])
        context_html += f"""
        <div class="section">
            <h3>Recent Shell Commands</h3>
            <div class="code-wrapper">
                <div class="code-header"><span class="lang">bash</span><button class="copy-btn" onclick="copyCode(this)">Copy</button></div>
                <pre><code>{escape_html(history_text)}</code></pre>
            </div>
        </div>
        """

    if context.get("cwd"):
        context_html += f"""
        <div class="section">
            <h3>Working Directory</h3>
            <div class="code-wrapper">
                <pre><code>{escape_html(context["cwd"])}</code></pre>
            </div>
        </div>
        """

    if context.get("env"):
        env_lines = [f"{escape_html(k)}={escape_html(v)}" for k, v in context["env"].items()]
        env_html = "\n".join(env_lines)
        context_html += f"""
        <div class="section">
            <h3>Environment Variables</h3>
            <div class="code-wrapper">
                 <div class="code-header"><span class="lang">env</span><button class="copy-btn" onclick="copyCode(this)">Copy</button></div>
                 <pre><code>{env_html}</code></pre>
            </div>
        </div>
        """

    if context.get("recent_logs"):
        for log_info in context["recent_logs"]:
            context_html += f"""
            <div class="section">
                <h3>Log File: {escape_html(log_info["file"])}</h3>
                <div class="code-wrapper">
                    <div class="code-header"><span class="lang">log</span><button class="copy-btn" onclick="copyCode(this)">Copy</button></div>
                    <pre><code>{escape_html(log_info["content"])}</code></pre>
                </div>
            </div>
            """

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GOLIAT Debug Session</title>
    <style>
        :root {{
            --primary: #4F46E5;
            --bg: #F3F4F6;
            --surface: #FFFFFF;
            --text: #1F2937;
            --code-bg: #1E293B;
            --code-text: #E2E8F0;
            --border: #E5E7EB;
            --header-grad-start: #4F46E5;
            --header-grad-end: #7C3AED;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: var(--text);
            background: var(--bg);
            padding: 20px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: var(--surface);
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, var(--header-grad-start), var(--header-grad-end));
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
            letter-spacing: -0.025em;
        }}
        .header .timestamp {{
            opacity: 0.9;
            font-size: 0.95em;
            font-weight: 500;
        }}
        .content {{
            padding: 40px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            color: var(--text);
            margin-bottom: 20px;
            font-size: 1.5em;
            font-weight: 600;
            border-bottom: 2px solid var(--border);
            padding-bottom: 10px;
        }}
        .section h3 {{
            color: #4B5563;
            margin-bottom: 12px;
            font-size: 1.1em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        /* Enhanced Code Blocks */
        .code-wrapper {{
            background: var(--code-bg);
            border-radius: 8px;
            overflow: hidden;
            margin: 15px 0;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .code-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 16px;
            background: rgba(0, 0, 0, 0.2);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .code-header .lang {{
            color: #94A3B8;
            font-size: 0.8em;
            text-transform: uppercase;
            font-weight: 600;
        }}
        .copy-btn {{
            background: transparent;
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: #E2E8F0;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .copy-btn:hover {{
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.4);
        }}
        pre {{
            margin: 0;
            padding: 20px;
            overflow-x: auto;
            color: var(--code-text);
            font-size: 0.9em;
            line-height: 1.5;
        }}
        code {{
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        }}
        /* Inline Code */
        p code, li code {{
            background: #EFF6FF;
            color: #1D4ED8;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
            border: 1px solid #DBEAFE;
        }}

        /* Response Areas */
        .error-box {{
            background: #FEF2F2;
            border: 1px solid #FECACA;
            border-radius: 8px;
            padding: 20px;
        }}
        .error-box pre {{
            background: transparent;
            color: #991B1B;
            padding: 0;
            white-space: pre-wrap;
        }}
        .response-box {{
            background: #F0F9FF;
            border: 1px solid #BAE6FD;
            border-radius: 8px;
            padding: 30px;
        }}

        p {{ margin-bottom: 1em; }}
        a {{ color: var(--primary); text-decoration: none; font-weight: 500; }}
        a:hover {{ text-decoration: underline; }}

        /* Lists */
        ul, ol {{
            margin-left: 20px;
            margin-bottom: 1em;
            padding-left: 20px;
        }}
        li {{
            margin-bottom: 0.5em;
            line-height: 1.6;
        }}
        ul ul, ol ol, ul ol, ol ul {{
            margin-top: 0.5em;
            margin-bottom: 0.5em;
        }}

        /* Headers */
        h1 {{
            font-size: 2em;
            margin-top: 1.5em;
            margin-bottom: 0.75em;
            font-weight: 700;
            color: var(--text);
            border-bottom: 2px solid var(--border);
            padding-bottom: 0.5em;
        }}
        h2 {{
            font-size: 1.5em;
            margin-top: 1.25em;
            margin-bottom: 0.625em;
            font-weight: 600;
            color: var(--text);
        }}
        h3 {{
            font-size: 1.25em;
            margin-top: 1em;
            margin-bottom: 0.5em;
            font-weight: 600;
            color: #4B5563;
        }}
        h4, h5, h6 {{
            margin-top: 0.875em;
            margin-bottom: 0.5em;
            font-weight: 600;
            color: #6B7280;
        }}
        h4 {{ font-size: 1.1em; }}
        h5 {{ font-size: 1em; }}
        h6 {{ font-size: 0.9em; }}

        /* Blockquotes */
        blockquote {{
            border-left: 4px solid var(--primary);
            margin: 1em 0;
            padding: 0.5em 1em;
            background: #F9FAFB;
            color: #4B5563;
            font-style: italic;
            border-radius: 4px;
        }}
        blockquote p {{
            margin-bottom: 0.5em;
        }}
        blockquote p:last-child {{
            margin-bottom: 0;
        }}

        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}
        thead {{
            background: #F3F4F6;
        }}
        th {{
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: var(--text);
            border-bottom: 2px solid var(--border);
        }}
        td {{
            padding: 10px 16px;
            border-bottom: 1px solid #E5E7EB;
        }}
        tbody tr:hover {{
            background: #F9FAFB;
        }}
        tbody tr:last-child td {{
            border-bottom: none;
        }}

        /* Horizontal Rules */
        hr {{
            border: none;
            border-top: 2px solid var(--border);
            margin: 2em 0;
        }}

        /* Text Formatting */
        em {{ font-style: italic; }}
        strong {{ font-weight: 600; }}
        del {{
            text-decoration: line-through;
            opacity: 0.7;
        }}
    </style>
    <script>
        function copyCode(btn) {{
            const wrapper = btn.closest('.code-wrapper');
            const code = wrapper.querySelector('pre code').innerText;
            navigator.clipboard.writeText(code).then(() => {{
                const originalText = btn.innerText;
                btn.innerText = 'Copied!';
                setTimeout(() => {{
                    btn.innerText = originalText;
                }}, 2000);
            }});
        }}
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 GOLIAT Debug Session</h1>
            <div class="timestamp">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
        </div>
        <div class="content">
            <div class="section">
                <h2>Error Message</h2>
                <div class="error-box">
                    <pre><code>{escape_html(error_message)}</code></pre>
                </div>
            </div>

            {context_html}

            <div class="section">
                <h2>AI Diagnosis & Recommendations</h2>
                <div class="response-box">
                    {markdown_to_html(response)}
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""

    # Create temporary HTML file
    fd, html_path = tempfile.mkstemp(suffix=".html", prefix="goliat_debug_", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html_content)
        return html_path
    except Exception:
        os.close(fd)
        raise


def main_debug():
    """Entry point for 'goliat debug' command - AI-powered error diagnosis.

    Automatically gathers context from logs, shell history, and environment,
    then uses GPT-5 to diagnose issues and suggest fixes.

    Examples:
        # Auto-detect error from recent logs
        goliat debug

        # Debug specific error message
        goliat debug "iSolve.exe failed with return code 1"

        # Ask a question about logs
        goliat debug --question "Why did the simulation fail?"

        # Use specific log file and ask question
        goliat debug --logs logs/session.log --question "What caused the power balance error?"

        # Look back more log files
        goliat debug --log-count 10 --question "Analyze all recent simulation failures"

        # Force simple model (faster, cheaper)
        goliat debug --simple "quick check"

        # Force complex model (thorough analysis)
        goliat debug --complex "deep dive into error"

        # Auto-select model (default)
        goliat debug --auto "let AI decide"
    """
    parser = argparse.ArgumentParser(
        description="Debug errors and analyze GOLIAT logs with AI assistance.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Auto-detect from recent logs (auto model selection)
  %(prog)s "simulation failed"                 # Debug specific error
  %(prog)s --question "Why did SAR extraction fail?"
  %(prog)s --simple "quick check"             # Use fast/cheap model
  %(prog)s --complex "deep analysis"           # Use thorough model
  %(prog)s --logs logs/session.log --log-count 5
  %(prog)s --no-shell-context                 # Skip shell history gathering
        """,
    )
    parser.add_argument(
        "error",
        nargs="?",
        default=None,
        metavar="ERROR_MESSAGE",
        help="The error message to debug. If not provided, will try to infer from context.",
    )
    parser.add_argument(
        "--question",
        "--query",
        "-q",
        type=str,
        default=None,
        dest="question",
        help="Natural language question about the error or logs. "
        "Example: 'Why did the simulation fail?' or 'What caused the power balance issue?'",
    )
    parser.add_argument(
        "--logs",
        type=str,
        default=None,
        metavar="LOG_FILE",
        help="Path to a specific log file to analyze. If not provided, will auto-detect recent log files from logs/ directory.",
    )
    parser.add_argument(
        "--log-count",
        type=int,
        default=None,
        metavar="N",
        help=f"Number of recent log sessions to analyze (default: {MAX_LOG_FILES}). "
        f"Each session includes both .log (verbose) and .progress.log (summary) files. "
        f"Only applies when --logs is not specified.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        metavar="CONFIG_FILE",
        help="Path to a GOLIAT config file to include for context. Useful when debugging config-related issues.",
    )
    parser.add_argument(
        "--no-shell-context",
        action="store_true",
        help="Don't gather shell history and environment variables. Useful if you want to focus only on log files.",
    )
    parser.add_argument("--no-browser", action="store_true", help="Don't open the HTML debug report in browser. Just print to console.")

    # Model selection group (mutually exclusive)
    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument("--simple", action="store_true", help="Force use of simple model (gpt-5-mini) - faster and cheaper.")
    model_group.add_argument("--complex", action="store_true", help="Force use of complex model (gpt-5) - more thorough analysis.")
    model_group.add_argument("--auto", action="store_true", help="Auto-select model based on query complexity (default if not specified).")

    args = parser.parse_args()

    assistant = _init_assistant()

    # Determine how many log files to read
    log_count = args.log_count if args.log_count is not None else MAX_LOG_FILES

    # Gather shell context unless disabled
    shell_context = {}
    if not args.no_shell_context:
        print("🔍 Gathering shell context...")
        shell_context = _gather_shell_context(log_count=log_count)
        print(f"  Found {len(shell_context['history'])} recent commands")
        if shell_context.get("recent_logs"):
            print(f"  Found {len(shell_context['recent_logs'])} recent log files:")
            for log_info in shell_context["recent_logs"]:
                log_path = log_info["file"]
                size_kb = Path(log_path).stat().st_size / 1024 if Path(log_path).exists() else 0
                print(f"     - {log_path} ({size_kb:.1f} KB)")
        else:
            print(f"  No recent log files found (checked last {LOG_RECENCY_SECONDS // 60} minutes)")

    # Get log context
    log_context_parts = []
    log_files_read = []

    # Add shell context logs (if auto-detected)
    if shell_context.get("recent_logs") and not args.logs:
        for log_info in shell_context["recent_logs"]:
            log_path = log_info["file"]
            log_files_read.append(log_path)
            log_context_parts.append(f"Log file: {log_path}\n{log_info['content']}")

    # Add explicit log file if provided
    if args.logs:
        try:
            log_path = Path(args.logs)
            if not log_path.exists():
                print(f"Warning: Log file not found: {args.logs}")
            else:
                with open(args.logs, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    log_files_read.append(str(log_path))
                    log_context_parts.append(f"Log file: {args.logs}\n{content}")
                    size_kb = log_path.stat().st_size / 1024
                    print(f"📄 Reading log file: {args.logs} ({size_kb:.1f} KB)")
        except Exception as e:
            print(f"❌ Error reading log file {args.logs}: {e}")

    log_context = "\n\n---\n\n".join(log_context_parts)

    # Get config context
    config_context = ""
    if args.config:
        try:
            config_path = Path(args.config)
            if not config_path.exists():
                print(f"Warning: Config file not found: {args.config}")
            else:
                with open(args.config) as f:
                    config_context = f.read()
                    print(f"⚙️  Reading config: {args.config}")
        except Exception as e:
            print(f"❌ Error reading config file {args.config}: {e}")

    # Build error/question message
    if args.question:
        # User provided a natural language question
        if args.error:
            error_message = f"""Error message: {args.error}

Question: {args.question}

Please analyze the error and answer the question based on the provided context."""
        else:
            error_message = args.question
    elif args.error:
        # User provided error message
        error_message = args.error
    else:
        # Try to infer from context
        if shell_context.get("history"):
            recent_cmds = "\n".join(shell_context["history"][-5:])
            error_message = f"""Recent commands:
{recent_cmds}

Please help diagnose what went wrong based on the provided context."""
        elif log_files_read:
            error_message = "Please analyze the log files and diagnose any issues."
        else:
            error_message = "Please help diagnose the issue based on the provided context."

    # Build full context string
    full_context = []

    if shell_context.get("history"):
        full_context.append("Recent shell commands:\n```\n" + "\n".join(shell_context["history"][-SHELL_HISTORY_FALLBACK:]) + "\n```")

    if shell_context.get("cwd"):
        full_context.append(f"Current working directory: {shell_context['cwd']}")

    if shell_context.get("env"):
        env_str = "\n".join(f"{k}={v}" for k, v in shell_context["env"].items())
        full_context.append(f"Relevant environment variables:\n```\n{env_str}\n```")

    if log_context:
        full_context.append(log_context)

    if config_context:
        full_context.append(f"Config file:\n```json\n{config_context}\n```")

    context_str = "\n\n".join(full_context)

    # Show what we're analyzing
    print("\n" + "=" * 70)
    print("🤖 AI Debug Analysis")
    print("=" * 70)
    if log_files_read:
        print(f"📋 Analyzing {len(log_files_read)} log file(s):")
        for log_file in log_files_read:
            print(f"   • {log_file}")
    if args.question:
        print(f"❓ Question: {args.question}")
    elif args.error:
        print(f"🔴 Error: {args.error[:100]}{'...' if len(args.error) > 100 else ''}")
    # Determine model selection
    if args.simple:
        model_selection = "simple"
        model_name = "gpt-5-mini"
    elif args.complex:
        model_selection = "complex"
        model_name = "gpt-5"
    else:  # --auto or default
        model_selection = "auto"
        # Determine model based on query complexity for display
        complexity = assistant.query_processor.classify_complexity(error_message)
        if complexity == "simple":
            model_name = "gpt-5-mini (auto)"
        else:
            model_name = "gpt-5 (auto)"

    print("=" * 70 + "\n")

    # Show which model will be used
    print(f"Model: {model_name}\n")

    # Call AI assistant with spinner
    try:
        with thinking_spinner("Analyzing"):
            response = assistant.debug(
                error_message, context_str, config_context if config_context else "", model_selection=model_selection
            )

        # Check for empty response
        if not response or not response.strip():
            print("Warning: AI returned an empty response. This may indicate an API issue.")
            response = (
                "The AI assistant did not provide a response. This could be due to:\n"
                "- API rate limiting\n"
                "- Model timeout\n"
                "- Invalid request format\n\n"
                "Please try again or check your API key."
            )
    except Exception as e:
        print(f"Error calling AI assistant: {e}")
        print("\nTroubleshooting:")
        print("  - Check your OPENAI_API_KEY is set correctly")
        print("  - Verify you have access to gpt-5 models")
        print("  - Check your API quota/rate limits")
        response = f"Error occurred: {str(e)}"

    # Show cost and model info
    summary = assistant.get_cost_summary()
    if summary["call_count"] > 0:
        last_call = summary["breakdown"][-1]
        model_used = last_call.get("model", "unknown")
        last_cost = last_call["cost"]
        print(f"\n💰 Cost: ${last_cost:.6f} | Total session: ${summary['total_cost']:.6f}")
        print(f"   Model used: {model_used}")

    # Validate response before creating HTML
    if not response or not response.strip():
        print("\nWarning: Received empty response from AI.")
        print("   The HTML report will still be created, but may be incomplete.")

    # Create HTML and open in browser
    try:
        html_path = create_debug_html(error_message, shell_context, response or "No response received from AI.")
        if not args.no_browser:
            print("\n✅ Opening debug report in browser...")
            print(f"   File: {html_path}")
            webbrowser.open(f"file://{html_path}")
            print("   (HTML file will remain available after browser closes)")
        else:
            print(f"\nDebug report saved to: {html_path}")
            print("\n" + "=" * 70)
            print("AI Response:")
            print("=" * 70)
            if response:
                print_markdown(response)
            else:
                print("(Empty response)")
    except Exception as e:
        print(f"\nWarning: Could not create HTML report: {e}")
        print("\n" + "=" * 70)
        print("AI Response:")
        print("=" * 70)
        if response:
            print_markdown(response)
        else:
            print("(Empty response)")


def main():
    """Generic entry point."""
    if "--chat" in sys.argv:
        sys.argv.remove("--chat")
        main_chat()
    else:
        main_ask()


if __name__ == "__main__":
    main()
