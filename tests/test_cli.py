"""Tests for CLI commands."""

import pytest
from pathlib import Path
from typer.testing import CliRunner
import json
import csv
import tempfile

from streams_agent.cli import app

runner = CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_csv_input(temp_dir):
    """Create a sample CSV input file for multi-review."""
    csv_file = temp_dir / "papers.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['paper_id', 'pdf_path'])
        writer.writeheader()
        writer.writerow({'paper_id': 'test001', 'pdf_path': 'test_paper.pdf'})
    return csv_file


@pytest.fixture
def sample_tsv_input(temp_dir):
    """Create a sample TSV input file for multi-review."""
    tsv_file = temp_dir / "papers.tsv"
    with open(tsv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['paper_id', 'pdf_path'], delimiter='\t')
        writer.writeheader()
        writer.writerow({'paper_id': 'test001', 'pdf_path': 'test_paper.pdf'})
    return tsv_file


def test_multi_review_help():
    """Test that multi-review command shows help."""
    result = runner.invoke(app, ["multi-review", "--help"])
    assert result.exit_code == 0
    assert "Review multiple PDFs" in result.stdout
    assert "paper_id" in result.stdout
    assert "pdf_path" in result.stdout


def test_multi_review_missing_file():
    """Test multi-review with non-existent input file."""
    result = runner.invoke(app, [
        "multi-review",
        "nonexistent.csv",
        "src/streams_agent/template/streams.csv"
    ])
    assert result.exit_code == 1


def test_multi_review_empty_file(temp_dir):
    """Test multi-review with empty CSV file."""
    empty_csv = temp_dir / "empty.csv"
    empty_csv.write_text("")

    result = runner.invoke(app, [
        "multi-review",
        str(empty_csv),
        "src/streams_agent/template/streams.csv"
    ])
    assert result.exit_code == 1
    assert "empty" in result.stdout.lower()


def test_multi_review_missing_columns(temp_dir):
    """Test multi-review with CSV missing required columns."""
    bad_csv = temp_dir / "bad.csv"
    with open(bad_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'path'])
        writer.writeheader()
        writer.writerow({'id': 'test', 'path': 'test.pdf'})

    result = runner.invoke(app, [
        "multi-review",
        str(bad_csv),
        "src/streams_agent/template/streams.csv"
    ])
    assert result.exit_code == 1
    assert "Missing required columns" in result.stdout


def test_multi_review_csv_delimiter_detection(sample_csv_input):
    """Test that CSV delimiter is auto-detected."""
    result = runner.invoke(app, [
        "multi-review",
        str(sample_csv_input),
        "src/streams_agent/template/streams.csv",
        "--output-dir", str(sample_csv_input.parent / "output")
    ])
    # Should parse without error (even if PDFs don't exist)
    assert "Processing 1 papers" in result.stdout


def test_multi_review_tsv_delimiter_detection(sample_tsv_input):
    """Test that TSV delimiter is auto-detected."""
    result = runner.invoke(app, [
        "multi-review",
        str(sample_tsv_input),
        "src/streams_agent/template/streams.csv",
        "--output-dir", str(sample_tsv_input.parent / "output")
    ])
    # Should parse without error (even if PDFs don't exist)
    assert "Processing 1 papers" in result.stdout


def test_multi_review_custom_delimiter(temp_dir):
    """Test custom delimiter option."""
    pipe_csv = temp_dir / "papers.txt"
    with open(pipe_csv, 'w') as f:
        f.write("paper_id|pdf_path\n")
        f.write("test001|test_paper.pdf\n")

    result = runner.invoke(app, [
        "multi-review",
        str(pipe_csv),
        "src/streams_agent/template/streams.csv",
        "--delimiter", "|",
        "--output-dir", str(temp_dir / "output")
    ])
    assert "Processing 1 papers" in result.stdout


@pytest.mark.integration
def test_multi_review_integration(temp_dir):
    """Integration test for multi-review with actual PDF.

    This test requires ANTHROPIC_API_KEY or CBORG_API_KEY to be set.
    """
    import os

    # Skip if no API key (check for non-empty values)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    cborg_key = os.environ.get("CBORG_API_KEY", "")
    if not anthropic_key.strip() and not cborg_key.strip():
        pytest.skip("ANTHROPIC_API_KEY or CBORG_API_KEY not set")

    # Skip if test_paper.pdf doesn't exist
    test_pdf = Path("test_paper.pdf")
    if not test_pdf.exists():
        pytest.skip("test_paper.pdf not found")

    # Create input CSV
    csv_file = temp_dir / "papers.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['paper_id', 'pdf_path'])
        writer.writeheader()
        writer.writerow({'paper_id': 'integration_test', 'pdf_path': str(test_pdf)})

    # Run multi-review
    output_dir = temp_dir / "output"
    result = runner.invoke(app, [
        "multi-review",
        str(csv_file),
        "src/streams_agent/template/streams.csv",
        "--output-dir", str(output_dir)
    ])

    # Check output
    assert result.exit_code == 0
    assert "Successful: 1" in result.stdout

    # Verify output file was created
    output_file = output_dir / "integration_test.json"
    assert output_file.exists()

    # Verify JSON structure
    with open(output_file) as f:
        data = json.load(f)
        assert data['paper_id'] == 'integration_test'
        assert 'assessments' in data
        assert len(data['assessments']) > 0
