"""Agentic review engine using the Anthropic Claude Agent SDK."""

import asyncio
import json
import logging
import sys
import tempfile
from dataclasses import asdict
from importlib import resources
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

from streams_agent.models.checklist import ChecklistAssessment

from .csv_utils import parse_completed_csv, prepare_workspace

logger = logging.getLogger(__name__)


def _load_prompt(filename: str, **kwargs: str) -> str:
    """Load a markdown prompt file from the package directory.

    Args:
        filename: Name of the markdown file (e.g., "system_prompt.md").
        **kwargs: Variables to substitute into the prompt via str.format().

    Returns:
        The prompt text with variables substituted.
    """
    prompt_file = resources.files("streams_agent.agentic_review").joinpath(filename)
    text = prompt_file.read_text(encoding="utf-8")
    if kwargs:
        text = text.format(**kwargs)
    return text


def _print_debug(message: object) -> None:
    """Print a debug trace line for a single SDK message to stderr.

    Args:
        message: A message yielded by the SDK query() iterator.
    """
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                # Truncate long text for readability
                text = block.text[:200] + "..." if len(block.text) > 200 else block.text
                print(f"  [assistant] {text}", file=sys.stderr)
            elif isinstance(block, ToolUseBlock):
                print(f"  [tool_call] {block.name}({json.dumps(block.input, default=str)[:120]})", file=sys.stderr)
            elif isinstance(block, ToolResultBlock):
                content = str(block.content)[:120] if block.content else ""
                error = " ERROR" if block.is_error else ""
                print(f"  [tool_result{error}] {content}", file=sys.stderr)
    elif isinstance(message, ResultMessage):
        print(
            f"  [result] turns={message.num_turns} "
            f"cost=${message.total_cost_usd or 0:.4f} "
            f"duration={message.duration_ms}ms",
            file=sys.stderr,
        )
    elif isinstance(message, SystemMessage):
        print(f"  [system] {message.subtype}", file=sys.stderr)
    elif isinstance(message, UserMessage):
        content = str(message.content)[:120] if message.content else ""
        print(f"  [user] {content}", file=sys.stderr)


def _serialize_message(message: object) -> dict:
    """Serialize an SDK message to a JSON-compatible dict for trace saving.

    Args:
        message: A message yielded by the SDK query() iterator.

    Returns:
        A dictionary representation of the message.
    """
    result = {"type": type(message).__name__}
    if hasattr(message, "__dataclass_fields__"):
        result.update(asdict(message))
    return result


async def _run_review_async(
    pdf_path: Path,
    template_path: Path,
    paper_id: str,
    evaluator_id: str = "agentic_review",
    work_dir: Path | None = None,
    verbose: bool = False,
    trace_path: Path | None = None,
) -> ChecklistAssessment:
    """Run an agentic review (async implementation).

    Args:
        pdf_path: Path to the PDF file to review.
        template_path: Path to the STREAMS checklist CSV template.
        paper_id: Identifier for the paper.
        evaluator_id: Identifier for the evaluator.
        work_dir: Working directory for the CSV. If None, uses a temp directory.
        verbose: If True, print agent trace to stderr as it runs.
        trace_path: If set, save the full message trace as JSON to this path.

    Returns:
        ChecklistAssessment populated from the agent's CSV edits.
    """
    pdf_path = Path(pdf_path).resolve()
    template_path = Path(template_path).resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="agentic_review_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    csv_path = prepare_workspace(template_path, work_dir)

    system_prompt = _load_prompt("system_prompt.md")
    user_prompt = _load_prompt(
        "user_prompt.md",
        pdf_path=str(pdf_path),
        csv_path=str(csv_path),
    )

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=["Read", "Edit"],
        permission_mode="bypassPermissions",
    )

    trace: list[dict] = []

    async for message in query(prompt=user_prompt, options=options):
        if verbose:
            _print_debug(message)
        if trace_path is not None:
            trace.append(_serialize_message(message))

    if trace_path is not None:
        trace_path = Path(trace_path)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with open(trace_path, "w") as f:
            json.dump(trace, f, indent=2, default=str)
        if verbose:
            print(f"  [trace] saved to {trace_path}", file=sys.stderr)

    return parse_completed_csv(csv_path, paper_id=paper_id, evaluator_id=evaluator_id)


def run_review(
    pdf_path: Path,
    template_path: Path,
    paper_id: str,
    evaluator_id: str = "agentic_review",
    work_dir: Path | None = None,
    verbose: bool = False,
    trace_path: Path | None = None,
) -> ChecklistAssessment:
    """Run an agentic review of a PDF against a STREAMS checklist.

    This is the synchronous entry point. It spawns a Claude Code agent that
    reads the PDF and fills in a CSV checklist using the Edit tool.

    Args:
        pdf_path: Path to the PDF file to review.
        template_path: Path to the STREAMS checklist CSV template.
        paper_id: Identifier for the paper.
        evaluator_id: Identifier for the evaluator.
        work_dir: Working directory for the CSV. If None, uses a temp directory.
        verbose: If True, print agent trace to stderr as it runs.
        trace_path: If set, save the full message trace as JSON to this path.

    Returns:
        ChecklistAssessment populated from the agent's CSV edits.
    """
    return asyncio.run(
        _run_review_async(
            pdf_path=pdf_path,
            template_path=template_path,
            paper_id=paper_id,
            evaluator_id=evaluator_id,
            work_dir=work_dir,
            verbose=verbose,
            trace_path=trace_path,
        )
    )
