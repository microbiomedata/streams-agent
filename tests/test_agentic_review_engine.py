"""Tests for agentic_review engine."""

import os
import pytest
from pathlib import Path

from streams_agent.agentic_review.engine import _load_prompt


def test_load_user_prompt_with_substitution():
    """User prompt loads and substitutes variables."""
    prompt = _load_prompt("user_prompt.md", pdf_path="/tmp/paper.pdf", checklist_path="/tmp/checklist.yaml")
    assert "/tmp/paper.pdf" in prompt
    assert "/tmp/checklist.yaml" in prompt
    assert "Rating Values" in prompt
    assert "checklist reviewer" in prompt


def test_agentic_review_cli_help():
    """The agentic-review command exists and shows help."""
    from typer.testing import CliRunner
    from streams_agent.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["agentic-review", "--help"])
    assert result.exit_code == 0
    assert "agentic" in result.output.lower()


@pytest.mark.integration
def test_run_review(tmp_path):
    """Integration test: run a full agentic review against a real PDF."""
    from streams_agent.agentic_review import run_review

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

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
    rated = [a for a in assessment.assessments if a.rating is not None]
    assert len(rated) > 0
