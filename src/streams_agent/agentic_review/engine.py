"""Agentic review engine using the Anthropic Claude Agent SDK."""

import asyncio
import tempfile
from importlib import resources
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions

from streams_agent.models.checklist import ChecklistAssessment

from .csv_utils import parse_completed_csv, prepare_workspace


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


async def _run_review_async(
    pdf_path: Path,
    template_path: Path,
    paper_id: str,
    evaluator_id: str = "agentic_review",
    work_dir: Path | None = None,
) -> ChecklistAssessment:
    """Run an agentic review (async implementation).

    Args:
        pdf_path: Path to the PDF file to review.
        template_path: Path to the STREAMS checklist CSV template.
        paper_id: Identifier for the paper.
        evaluator_id: Identifier for the evaluator.
        work_dir: Working directory for the CSV. If None, uses a temp directory.

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

    async for _message in query(prompt=user_prompt, options=options):
        pass  # Let the agent run to completion

    return parse_completed_csv(csv_path, paper_id=paper_id, evaluator_id=evaluator_id)


def run_review(
    pdf_path: Path,
    template_path: Path,
    paper_id: str,
    evaluator_id: str = "agentic_review",
    work_dir: Path | None = None,
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
        )
    )
