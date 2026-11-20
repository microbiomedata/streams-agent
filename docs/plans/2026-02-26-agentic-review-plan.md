# Agentic Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the STREAMS review agent using the Anthropic Claude Agent SDK, where Claude reads a PDF and iteratively edits a CSV checklist file.

**Architecture:** A thin wrapper around `claude-agent-sdk`'s `query()`. Python prepares a temp directory with a blank CSV, tells Claude to read the PDF and fill in the CSV using Edit, then parses the result back into the existing `ChecklistAssessment` model. Prompts are stored as markdown files.

**Tech Stack:** `claude-agent-sdk`, existing `streams_agent.models.checklist`, `streams_agent.template.loader`, `typer` for CLI.

---

### Task 1: Add claude-agent-sdk dependency

**Files:**
- Modify: `pyproject.toml:17-24`

**Step 1: Add the dependency**

In `pyproject.toml`, add `claude-agent-sdk` to the dependencies list:

```toml
dependencies = [
  "typer >= 0.9.0",
  "linkml-runtime >=1.9.4",
  "pydantic-ai>=1.1.0",
  "pymupdf>=1.26.5",
  "gradio>=5.49.1",
  "linkml-reference-validator>=0.1.7",
  "claude-agent-sdk>=0.1.0",
]
```

**Step 2: Install**

Run: `uv sync`
Expected: Successful install with claude-agent-sdk resolved.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add claude-agent-sdk dependency"
```

---

### Task 2: Create csv_utils module with tests

**Files:**
- Create: `src/streams_agent/agentic_review/__init__.py`
- Create: `src/streams_agent/agentic_review/csv_utils.py`
- Create: `tests/test_agentic_review_csv_utils.py`

**Step 1: Write the failing tests**

Create `tests/test_agentic_review_csv_utils.py`:

```python
"""Tests for agentic_review csv_utils."""

import csv
from pathlib import Path

import pytest

from streams_agent.agentic_review.csv_utils import prepare_workspace, parse_completed_csv
from streams_agent.models.checklist import AssessmentRating


TEMPLATE_PATH = Path("src/streams_agent/template/streams.csv")


def test_prepare_workspace_creates_csv(tmp_path):
    """prepare_workspace copies template and blanks rating/comments columns."""
    csv_path = prepare_workspace(TEMPLATE_PATH, tmp_path)
    assert csv_path.exists()
    assert csv_path.name == "checklist.csv"

    with open(csv_path) as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Row 0: human headers, Row 1: field mappings, Row 2+: data
    assert len(rows) > 2
    # Rating and comments columns (indices 6, 7) should be blank for data rows
    for row in rows[2:]:
        if len(row) > 6 and row[0].strip():  # skip empty/header rows
            assert row[6].strip() == "", f"Rating not blank for row {row[0]}"
            assert row[7].strip() == "", f"Comments not blank for row {row[0]}"


def test_prepare_workspace_preserves_checklist_content(tmp_path):
    """Checklist items (first 6 columns) are preserved from original template."""
    csv_path = prepare_workspace(TEMPLATE_PATH, tmp_path)

    with open(TEMPLATE_PATH) as f:
        original = list(csv.reader(f))
    with open(csv_path) as f:
        prepared = list(csv.reader(f))

    # First 6 columns should match for all rows
    for orig_row, prep_row in zip(original, prepared):
        assert orig_row[:6] == prep_row[:6]


def test_parse_completed_csv(tmp_path):
    """Parse a filled-in CSV back into ChecklistAssessment."""
    # Create a minimal filled CSV
    csv_path = tmp_path / "checklist.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Number", "Item", "Recommendation", "Source",
                         "Additional Guidance", "Example(s)",
                         "Present in the manuscript? Yes/No/NA",
                         "Comments or location in manuscript"])
        writer.writerow(["ItemAssessment.item_id", "ChecklistItem.title",
                         "ChecklistItem.description", "ChecklistItem.source",
                         "ChecklistItem.additional_guidance", "ChecklistItem.examples",
                         "ItemAssessment.rating", "ItemAssessment.comments"])
        writer.writerow(["1", "Structured abstract", "Include abstract", "",
                         "", "", "Yes", "Found in abstract section"])
        writer.writerow(["1.1", "Study design", "State study design", "",
                         "", "", "No", "Not mentioned"])
        writer.writerow(["1.2", "Environment info", "Describe environment", "",
                         "", "", "NA", "Not applicable"])
        writer.writerow(["1.3", "Host info", "Describe host", "",
                         "", "", "Partial", "Partially addressed on p.3"])

    assessment = parse_completed_csv(csv_path, paper_id="test_paper",
                                     evaluator_id="agentic_review")

    assert assessment.paper_id == "test_paper"
    assert assessment.evaluator_id == "agentic_review"
    assert assessment.checklist_name == "STREAMS"
    assert len(assessment.assessments) == 4

    a1 = assessment.get_assessment("1")
    assert a1.rating == AssessmentRating.YES
    assert a1.comments == "Found in abstract section"

    a2 = assessment.get_assessment("1.1")
    assert a2.rating == AssessmentRating.NO

    a3 = assessment.get_assessment("1.2")
    assert a3.rating == AssessmentRating.NOT_APPLICABLE

    a4 = assessment.get_assessment("1.3")
    assert a4.rating == AssessmentRating.PARTIAL
    assert "p.3" in a4.comments


def test_parse_completed_csv_empty_ratings(tmp_path):
    """Rows with empty ratings parse as None."""
    csv_path = tmp_path / "checklist.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Number", "Item", "Recommendation", "Source",
                         "Additional Guidance", "Example(s)",
                         "Present in the manuscript? Yes/No/NA",
                         "Comments or location in manuscript"])
        writer.writerow(["ItemAssessment.item_id", "ChecklistItem.title",
                         "ChecklistItem.description", "ChecklistItem.source",
                         "ChecklistItem.additional_guidance", "ChecklistItem.examples",
                         "ItemAssessment.rating", "ItemAssessment.comments"])
        writer.writerow(["1", "Abstract", "Include abstract", "", "", "", "", ""])

    assessment = parse_completed_csv(csv_path, paper_id="p1", evaluator_id="e1")
    assert assessment.assessments[0].rating is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agentic_review_csv_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'streams_agent.agentic_review'`

**Step 3: Create the package and implement csv_utils**

Create `src/streams_agent/agentic_review/__init__.py`:

```python
"""Agentic review engine using the Anthropic Claude Agent SDK."""
```

Create `src/streams_agent/agentic_review/csv_utils.py`:

```python
"""CSV utilities for agentic review workspace preparation and result parsing."""

import csv
import shutil
from pathlib import Path

from streams_agent.models.checklist import (
    AssessmentRating,
    ChecklistAssessment,
    ItemAssessment,
)

# Column indices in the STREAMS CSV template
RATING_COL = 6
COMMENTS_COL = 7


def prepare_workspace(template_path: Path, work_dir: Path) -> Path:
    """Copy the checklist template into a working directory with blank rating/comments columns.

    Args:
        template_path: Path to the STREAMS checklist CSV template.
        work_dir: Directory to place the working CSV copy.

    Returns:
        Path to the prepared CSV file ready for the agent to fill in.
    """
    csv_path = work_dir / "checklist.csv"

    with open(template_path) as f:
        rows = list(csv.reader(f))

    # Blank out rating and comments columns for data rows (skip header rows 0-1)
    for row in rows[2:]:
        if len(row) > COMMENTS_COL:
            row[RATING_COL] = ""
            row[COMMENTS_COL] = ""

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    return csv_path


_RATING_MAP = {
    "yes": AssessmentRating.YES,
    "y": AssessmentRating.YES,
    "no": AssessmentRating.NO,
    "n": AssessmentRating.NO,
    "na": AssessmentRating.NOT_APPLICABLE,
    "n/a": AssessmentRating.NOT_APPLICABLE,
    "not applicable": AssessmentRating.NOT_APPLICABLE,
    "partial": AssessmentRating.PARTIAL,
    "p": AssessmentRating.PARTIAL,
}


def _parse_rating(text: str) -> AssessmentRating | None:
    """Parse a rating string into an AssessmentRating enum value."""
    normalized = text.strip().lower()
    return _RATING_MAP.get(normalized)


def parse_completed_csv(
    csv_path: Path,
    paper_id: str,
    evaluator_id: str,
) -> ChecklistAssessment:
    """Parse a completed CSV checklist back into a ChecklistAssessment.

    Args:
        csv_path: Path to the filled-in CSV.
        paper_id: Identifier for the paper.
        evaluator_id: Identifier for the evaluator.

    Returns:
        ChecklistAssessment populated from the CSV contents.
    """
    with open(csv_path) as f:
        rows = list(csv.reader(f))

    assessments = []
    # Skip header row (0) and field mapping row (1)
    for row in rows[2:]:
        if len(row) <= COMMENTS_COL:
            continue
        item_id = row[0].strip()
        if not item_id:
            continue

        rating_text = row[RATING_COL].strip() if len(row) > RATING_COL else ""
        comments_text = row[COMMENTS_COL].strip() if len(row) > COMMENTS_COL else ""

        assessments.append(
            ItemAssessment(
                item_id=item_id,
                rating=_parse_rating(rating_text),
                comments=comments_text or None,
            )
        )

    return ChecklistAssessment(
        checklist_name="STREAMS",
        checklist_version="1.0",
        paper_id=paper_id,
        evaluator_id=evaluator_id,
        assessments=assessments,
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_agentic_review_csv_utils.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add src/streams_agent/agentic_review/ tests/test_agentic_review_csv_utils.py
git commit -m "feat: add csv_utils for agentic review workspace prep and parsing"
```

---

### Task 3: Create markdown prompt files

**Files:**
- Create: `src/streams_agent/agentic_review/system_prompt.md`
- Create: `src/streams_agent/agentic_review/user_prompt.md`

**Step 1: Write system prompt**

Create `src/streams_agent/agentic_review/system_prompt.md`:

```markdown
You are a STREAMS checklist reviewer for microbiome research papers.

STREAMS (Standards for Technical Reporting in Environmental and host-Associated Microbiome Studies) extends STORMS guidelines to environmental, non-human host, and synthetic microbiome studies.

## Your Task

You will be given:
1. A PDF research paper to review
2. A CSV checklist file to fill in

Read the paper carefully, then for each checklist item in the CSV, fill in:
- **Rating column** ("Present in the manuscript? Yes/No/NA"): one of `Yes`, `No`, `NA`, or `Partial`
- **Comments column** ("Comments or location in manuscript"): specific comments with page/section references and extracted values

## Rating Guidelines

- **Yes**: Item is clearly addressed and well-documented in the paper
- **No**: Item is missing or inadequately addressed
- **Partial**: Item is partially addressed but incomplete
- **NA**: Item is not applicable to this study type

## How to Work

1. First, read the PDF to understand the paper
2. Then read the CSV to see all checklist items
3. Work through the items systematically, editing the CSV to fill in ratings and comments
4. For group header rows (like "Abstract", "Introduction") that have no item number with a decimal, you may skip them or leave them blank
5. Be thorough but concise in comments. Focus on factual presence/absence of information.
6. Always include specific references (e.g., "Section 2.1", "Table 1", "p.5 paragraph 2") in your comments.
```

**Step 2: Write user prompt template**

Create `src/streams_agent/agentic_review/user_prompt.md`:

```markdown
Review the research paper at `{pdf_path}` against the STREAMS checklist.

The checklist CSV is at `{csv_path}`. Read both files, then edit the CSV to fill in the rating and comments columns for each checklist item.

The CSV has 8 columns. For each data row (starting at row 3), fill in:
- Column 7: Rating (Yes, No, NA, or Partial)
- Column 8: Comments with specific references to the paper

Work through all items systematically. When you are done, every item with a numeric ID should have a rating.
```

**Step 3: Commit**

```bash
git add src/streams_agent/agentic_review/system_prompt.md src/streams_agent/agentic_review/user_prompt.md
git commit -m "feat: add markdown prompt files for agentic review"
```

---

### Task 4: Implement engine.py with tests

**Files:**
- Create: `src/streams_agent/agentic_review/engine.py`
- Modify: `src/streams_agent/agentic_review/__init__.py`
- Create: `tests/test_agentic_review_engine.py`

**Step 1: Write the unit test for prompt loading**

Create `tests/test_agentic_review_engine.py`:

```python
"""Tests for agentic_review engine."""

import pytest
from pathlib import Path

from streams_agent.agentic_review.engine import _load_prompt


def test_load_system_prompt():
    """System prompt loads from markdown file."""
    prompt = _load_prompt("system_prompt.md")
    assert "STREAMS" in prompt
    assert "Rating Guidelines" in prompt


def test_load_user_prompt_with_substitution():
    """User prompt loads and substitutes variables."""
    prompt = _load_prompt("user_prompt.md", pdf_path="/tmp/paper.pdf", csv_path="/tmp/checklist.csv")
    assert "/tmp/paper.pdf" in prompt
    assert "/tmp/checklist.csv" in prompt


@pytest.mark.integration
def test_run_review(tmp_path):
    """Integration test: run a full agentic review against a real PDF."""
    from streams_agent.agentic_review import run_review

    # This test requires:
    # 1. ANTHROPIC_API_KEY set in environment
    # 2. A PDF file to review
    # Skip if no API key
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Use a test PDF if available
    test_pdfs = list(Path("evals/streams-gdrive").glob("*.pdf"))
    if not test_pdfs:
        pytest.skip("No test PDFs available")

    pdf_path = test_pdfs[0]
    template_path = Path("src/streams_agent/template/streams.csv")

    assessment = run_review(
        pdf_path=pdf_path,
        template_path=template_path,
        paper_id="integration_test",
        work_dir=tmp_path,
    )

    assert assessment.paper_id == "integration_test"
    assert len(assessment.assessments) > 0
    # At least some items should have ratings
    rated = [a for a in assessment.assessments if a.rating is not None]
    assert len(rated) > 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agentic_review_engine.py -v -k "not integration"`
Expected: FAIL with `ImportError: cannot import name '_load_prompt'`

**Step 3: Implement engine.py**

Create `src/streams_agent/agentic_review/engine.py`:

```python
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
```

Update `src/streams_agent/agentic_review/__init__.py`:

```python
"""Agentic review engine using the Anthropic Claude Agent SDK."""

from .engine import run_review

__all__ = ["run_review"]
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_agentic_review_engine.py -v -k "not integration"`
Expected: 2 tests PASS (prompt loading tests).

**Step 5: Commit**

```bash
git add src/streams_agent/agentic_review/ tests/test_agentic_review_engine.py
git commit -m "feat: implement agentic review engine with claude-agent-sdk"
```

---

### Task 5: Add CLI subcommand

**Files:**
- Modify: `src/streams_agent/cli.py`

**Step 1: Write a CLI test**

Append to `tests/test_agentic_review_engine.py`:

```python
from typer.testing import CliRunner
from streams_agent.cli import app

runner = CliRunner()


def test_agentic_review_cli_help():
    """The agentic-review command exists and shows help."""
    result = runner.invoke(app, ["agentic-review", "--help"])
    assert result.exit_code == 0
    assert "agentic" in result.output.lower()
```

**Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_agentic_review_engine.py::test_agentic_review_cli_help -v`
Expected: FAIL (no such command).

**Step 3: Add the CLI command**

Add to `src/streams_agent/cli.py` (after the existing `ui` command, before `def main()`):

```python
@app.command("agentic-review")
def agentic_review(
    pdf_path: Annotated[Path, typer.Argument(help="Path to the PDF file to review")],
    template_path: Annotated[Path, typer.Argument(help="Path to the STREAMS checklist template CSV")] = Path("src/streams_agent/template/streams.csv"),
    paper_id: Annotated[str, typer.Option(help="Identifier for the paper being reviewed")] = "paper",
    evaluator_id: Annotated[str, typer.Option(help="Identifier for the evaluator")] = "agentic_review",
    output: Annotated[Optional[Path], typer.Option(help="Output file path (JSON format)")] = None,
    work_dir: Annotated[Optional[Path], typer.Option(help="Working directory for intermediate CSV")] = None,
):
    """Review a PDF using the agentic review engine (Claude Agent SDK).

    The agent reads the PDF, works through the STREAMS checklist iteratively,
    and fills in ratings and comments by editing a CSV file.

    Requires ANTHROPIC_API_KEY environment variable to be set.
    """
    from .agentic_review import run_review

    typer.echo(f"Reviewing {pdf_path} using agentic review engine...")
    assessment = run_review(
        pdf_path=pdf_path,
        template_path=template_path,
        paper_id=paper_id,
        evaluator_id=evaluator_id,
        work_dir=work_dir,
    )

    if output:
        with open(output, "w") as f:
            json.dump(assessment.model_dump(mode="json"), f, indent=2, default=str)
        typer.echo(f"Review saved to {output}")
    else:
        total_items = len(assessment.assessments)
        rated = len([a for a in assessment.assessments if a.rating is not None])
        typer.echo(f"\nReview Complete!")
        typer.echo(f"Paper ID: {assessment.paper_id}")
        typer.echo(f"Items reviewed: {rated}/{total_items}")
        typer.echo(f"Completion rate: {assessment.get_completion_rate():.1%}")

        ratings_count: dict[str, int] = {}
        for a in assessment.assessments:
            if a.rating:
                ratings_count[a.rating.value] = ratings_count.get(a.rating.value, 0) + 1
        typer.echo("\nRatings Summary:")
        for rating, count in ratings_count.items():
            typer.echo(f"  {rating}: {count}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_agentic_review_engine.py::test_agentic_review_cli_help -v`
Expected: PASS.

**Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v -k "not integration"`
Expected: All tests pass, no regressions.

**Step 6: Commit**

```bash
git add src/streams_agent/cli.py tests/test_agentic_review_engine.py
git commit -m "feat: add agentic-review CLI subcommand"
```

---

### Task 6: Run linting and full checks

**Step 1: Run ruff**

Run: `uv run ruff check src/streams_agent/agentic_review/`
Fix any issues found.

**Step 2: Run all non-integration tests**

Run: `uv run pytest tests/ -v -k "not integration"`
Expected: All pass.

**Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: address linting issues in agentic_review"
```
