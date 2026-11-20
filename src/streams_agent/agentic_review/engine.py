"""Agentic review engine using the Anthropic Claude Agent SDK."""

import asyncio
import json
import logging
import sys
import tempfile
import time
from datetime import datetime, timezone
from dataclasses import asdict
from importlib import resources
from pathlib import Path

import anyio

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

# ---------------------------------------------------------------------------
# Monkey-patch for claude-agent-sdk #554/#595: stdin closes too early,
# breaking hook callbacks.  For string prompts the SDK calls
# transport.end_input() immediately after writing the user message,
# closing the bidirectional channel that hooks need.
# Remove once the SDK ships a fix (watch PRs #580, #595).
# https://github.com/anthropics/claude-agent-sdk-python/issues/554
# ---------------------------------------------------------------------------
from claude_agent_sdk._internal.client import InternalClient as _IC  # noqa: E402

_original_process_query = _IC.process_query


async def _patched_process_query(self, prompt, options, transport=None):  # type: ignore[no-untyped-def]
    """Wrap process_query to keep stdin open for hooks on string prompts.

    Converts the string prompt into an async iterable so it routes through
    ``stream_input()`` (which keeps stdin open) instead of the direct
    ``write + end_input()`` path.  The generator blocks on an event after
    yielding the user message.  When ResultMessage arrives the event is
    set, the generator finishes, ``stream_input`` calls ``end_input()``,
    and the CLI exits — all in the correct task context.
    """
    has_hooks = bool(options.hooks)

    if isinstance(prompt, str) and has_hooks:
        user_message = {
            "type": "user",
            "session_id": "",
            "message": {"role": "user", "content": prompt},
            "parent_tool_use_id": None,
        }
        done = anyio.Event()

        async def _single_message_stream():  # type: ignore[no-untyped-def]
            yield user_message
            # Block until the result arrives so stdin stays open for hooks.
            # stream_input will call end_input() once we return.
            await done.wait()

        async for msg in _original_process_query(
            self, _single_message_stream(), options, transport
        ):
            yield msg
            if isinstance(msg, ResultMessage):
                done.set()
    else:
        async for msg in _original_process_query(self, prompt, options, transport):
            yield msg


_IC.process_query = _patched_process_query  # type: ignore[assignment]

from streams_agent.models.checklist import ChecklistAssessment  # noqa: E402

from .csv_utils import (  # noqa: E402
    get_expected_ids,
    parse_completed_yaml,
    prepare_yaml_workspace,
    validate_checklist_yaml,
)

logger = logging.getLogger(__name__)

#: Short name → full model ID mapping for convenience.
MODEL_ALIASES: dict[str, str] = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
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
        'claude-sonnet-4-6'
        >>> _resolve_model("claude-opus-4-6")
        'claude-opus-4-6'
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
    item_ids: list[str] | None = None,
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
        item_ids: If set, only evaluate these checklist item IDs (e.g.
            ``["1.1", "1.2"]``).  Useful for quick testing.

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

    checklist_path = prepare_yaml_workspace(template_path, work_dir, item_ids=item_ids)
    input_yaml = checklist_path.read_text()  # Capture blank template before agent fills it
    expected_ids = get_expected_ids(checklist_path)

    user_prompt = _load_prompt(
        "user_prompt.md",
        pdf_path=str(pdf_path),
        checklist_path=str(checklist_path),
    )

    resolved_model = _resolve_model(model)

    validation_hook = _make_validation_hook(checklist_path, expected_ids)

    options = ClaudeAgentOptions(
        model=resolved_model,
        max_buffer_size=50 * 1024 * 1024,  # 50 MB — PDFs exceed the 1 MB default
        extra_args={"strict-mcp-config": None},  # Ignore user's MCP servers
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
    result_metadata: dict = {}
    t0 = time.monotonic()
    timestamp = datetime.now(timezone.utc).isoformat()

    async for message in query(prompt=user_prompt, options=options):
        if verbosity > 0:
            _print_debug(message, verbosity, t0)
        if trace_path is not None:
            trace.append(_serialize_message(message))
        if isinstance(message, ResultMessage):
            result_metadata = {
                "total_cost_usd": message.total_cost_usd,
                "duration_ms": message.duration_ms,
                "num_turns": message.num_turns,
                "session_id": message.session_id,
            }

    # Read the completed YAML for inclusion in trace and return value
    completed_yaml = checklist_path.read_text()

    if trace_path is not None:
        trace_path = Path(trace_path)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_data = {
            "metadata": {
                "model": resolved_model,
                "paper_id": paper_id,
                "pdf_path": str(pdf_path),
                "timestamp": timestamp,
                "item_ids": item_ids,
                **result_metadata,
            },
            "input_yaml": input_yaml,
            "checklist_yaml": completed_yaml,
            "messages": trace,
        }
        with open(trace_path, "w") as f:
            json.dump(trace_data, f, indent=2, default=str)
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
    item_ids: list[str] | None = None,
) -> ChecklistAssessment:
    """Run an agentic review of a PDF against a STREAMS checklist.

    This is the synchronous entry point. It spawns a Claude Code agent that
    reads the PDF and writes a completed YAML checklist in one shot, with a
    PostToolUse validation hook to catch errors.

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
        item_ids: If set, only evaluate these checklist item IDs (e.g.
            ``["1.1", "1.2"]``).  Useful for quick testing.

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
            item_ids=item_ids,
        )
    )
