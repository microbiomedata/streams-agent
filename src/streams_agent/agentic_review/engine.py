"""Agentic review engine using the Anthropic Claude Agent SDK."""

import asyncio
import json
import logging
import sys
import tempfile
import time
from dataclasses import asdict
from importlib import resources
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

from streams_agent.models.checklist import ChecklistAssessment

from .csv_utils import (
    get_expected_ids,
    parse_completed_yaml,
    prepare_yaml_workspace,
    validate_checklist_yaml,
)

logger = logging.getLogger(__name__)

#: Short name → full model ID mapping for convenience.
MODEL_ALIASES: dict[str, str] = {
    "opus": "claude-opus-4-5-20250514",
    "sonnet": "claude-sonnet-4-5-20250514",
    "haiku": "claude-haiku-4-5-20251001",
}


def _resolve_model(model: str | None) -> str | None:
    """Resolve a model short name or full ID.

    Args:
        model: Short name (``"opus"``, ``"sonnet"``, ``"haiku"``),
               full model ID, or ``None`` for the SDK default.

    Returns:
        Full model ID string, or ``None``.

    Examples:
        >>> _resolve_model("sonnet")
        'claude-sonnet-4-5-20250514'
        >>> _resolve_model("claude-opus-4-5-20250514")
        'claude-opus-4-5-20250514'
        >>> _resolve_model(None) is None
        True
    """
    if model is None:
        return None
    return MODEL_ALIASES.get(model, model)


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


def _print_debug(message: object, verbosity: int = 1, t0: float = 0.0) -> None:
    """Print a debug trace line for a single SDK message to stderr.

    Verbosity levels:
        1 (-v):   tool calls + result summary
        2 (-vv):  + assistant text (truncated) + tool results (truncated)
        3 (-vvv): + full untruncated text, system messages, user messages

    Args:
        message: A message yielded by the SDK query() iterator.
        verbosity: How much detail to show (1-3).
        t0: Start time (from time.monotonic()) for elapsed timestamps.
    """
    elapsed = time.monotonic() - t0
    ts = f"{elapsed:7.1f}s"

    def _emit(tag: str, text: str) -> None:
        print(f"  {ts} [{tag}] {text}", file=sys.stderr)

    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                if verbosity >= 3:
                    _emit("assistant", block.text)
                elif verbosity >= 2:
                    text = block.text[:200] + "..." if len(block.text) > 200 else block.text
                    _emit("assistant", text)
            elif isinstance(block, ToolUseBlock):
                if verbosity >= 2:
                    _emit("tool_call", f"{block.name}({json.dumps(block.input, default=str)[:200]})")
                else:
                    _emit("tool_call", block.name)
            elif isinstance(block, ToolResultBlock):
                if verbosity >= 2:
                    content = str(block.content)[:200] if block.content else ""
                    error = " ERROR" if block.is_error else ""
                    _emit(f"tool_result{error}", content)
    elif isinstance(message, ResultMessage):
        _emit(
            "result",
            f"turns={message.num_turns} "
            f"cost=${message.total_cost_usd or 0:.4f} "
            f"duration={message.duration_ms}ms",
        )
    elif isinstance(message, SystemMessage) and verbosity >= 3:
        _emit("system", message.subtype)
    elif isinstance(message, UserMessage) and verbosity >= 3:
        content = str(message.content)[:200] if message.content else ""
        _emit("user", content)


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


def _make_validation_hook(
    checklist_path: Path,
    expected_ids: list[str],
):
    """Create a PostToolUse hook that validates the checklist YAML.

    The hook fires after every Write or Edit call. If the target file is the
    checklist, it runs ``validate_checklist_yaml`` and blocks with specific
    feedback when validation fails, giving the agent a chance to fix errors.

    Args:
        checklist_path: Resolved path to the checklist YAML file.
        expected_ids: List of item IDs that must be present.

    Returns:
        An async hook callback suitable for ``HookMatcher.hooks``.
    """

    async def _hook(hook_input, tool_use_id, context):
        tool_input = hook_input.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if not file_path.endswith(checklist_path.name):
            return {"continue_": True}

        errors = validate_checklist_yaml(checklist_path, expected_ids=expected_ids)
        if errors:
            return {
                "decision": "block",
                "reason": (
                    "Checklist validation failed:\n"
                    + "\n".join(f"- {e}" for e in errors)
                ),
            }
        return {"continue_": True}

    return _hook


async def _run_review_async(
    pdf_path: Path,
    template_path: Path,
    paper_id: str,
    evaluator_id: str = "agentic_review",
    work_dir: Path | None = None,
    model: str | None = None,
    verbosity: int = 0,
    trace_path: Path | None = None,
) -> ChecklistAssessment:
    """Run an agentic review (async implementation).

    Args:
        pdf_path: Path to the PDF file to review.
        template_path: Path to the STREAMS checklist CSV template.
        paper_id: Identifier for the paper.
        evaluator_id: Identifier for the evaluator.
        work_dir: Working directory for the CSV. If None, uses a temp directory.
        model: Model to use — short name (``"opus"``, ``"sonnet"``, ``"haiku"``),
               full model ID, or ``None`` for the SDK default.
        verbosity: Verbosity level (0=quiet, 1=tool calls, 2=+text, 3=+everything).
        trace_path: If set, save the full message trace as JSON to this path.

    Returns:
        ChecklistAssessment populated from the agent's YAML edits.
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

    checklist_path = prepare_yaml_workspace(template_path, work_dir)
    expected_ids = get_expected_ids(checklist_path)

    system_prompt = _load_prompt("system_prompt.md")
    user_prompt = _load_prompt(
        "user_prompt.md",
        pdf_path=str(pdf_path),
        checklist_path=str(checklist_path),
    )

    resolved_model = _resolve_model(model)

    validation_hook = _make_validation_hook(checklist_path, expected_ids)

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=resolved_model,
        allowed_tools=["Read", "Write", "Edit"],
        permission_mode="bypassPermissions",
        hooks={
            "PostToolUse": [
                HookMatcher(
                    matcher="Write|Edit",
                    hooks=[validation_hook],
                ),
            ],
        },
    )

    trace: list[dict] = []
    t0 = time.monotonic()

    async for message in query(prompt=user_prompt, options=options):
        if verbosity > 0:
            _print_debug(message, verbosity, t0)
        if trace_path is not None:
            trace.append(_serialize_message(message))

    if trace_path is not None:
        trace_path = Path(trace_path)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with open(trace_path, "w") as f:
            json.dump(trace, f, indent=2, default=str)
        if verbosity > 0:
            elapsed = time.monotonic() - t0
            print(f"  {elapsed:7.1f}s [trace] saved to {trace_path}", file=sys.stderr)

    return parse_completed_yaml(checklist_path, paper_id=paper_id, evaluator_id=evaluator_id)


def run_review(
    pdf_path: Path,
    template_path: Path,
    paper_id: str,
    evaluator_id: str = "agentic_review",
    work_dir: Path | None = None,
    model: str | None = None,
    verbosity: int = 0,
    trace_path: Path | None = None,
) -> ChecklistAssessment:
    """Run an agentic review of a PDF against a STREAMS checklist.

    This is the synchronous entry point. It spawns a Claude Code agent that
    reads the PDF and fills in a YAML checklist using the Edit tool.

    Args:
        pdf_path: Path to the PDF file to review.
        template_path: Path to the STREAMS checklist CSV template.
        paper_id: Identifier for the paper.
        evaluator_id: Identifier for the evaluator.
        work_dir: Working directory for the CSV. If None, uses a temp directory.
        model: Model to use — short name (``"opus"``, ``"sonnet"``, ``"haiku"``),
               full model ID, or ``None`` for the SDK default.
        verbosity: Verbosity level (0=quiet, 1=tool calls, 2=+text, 3=+everything).
        trace_path: If set, save the full message trace as JSON to this path.

    Returns:
        ChecklistAssessment populated from the agent's YAML edits.
    """
    return asyncio.run(
        _run_review_async(
            pdf_path=pdf_path,
            template_path=template_path,
            paper_id=paper_id,
            evaluator_id=evaluator_id,
            work_dir=work_dir,
            model=model,
            verbosity=verbosity,
            trace_path=trace_path,
        )
    )
