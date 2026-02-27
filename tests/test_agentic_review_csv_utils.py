"""Tests for agentic_review.csv_utils module."""

import csv
from pathlib import Path

import pytest
import yaml

from streams_agent.agentic_review.csv_utils import (
    COMMENTS_COL,
    RATING_COL,
    parse_completed_csv,
    parse_completed_yaml,
    prepare_workspace,
    prepare_yaml_workspace,
)
from streams_agent.models.checklist import AssessmentRating

TEMPLATE_PATH = Path(__file__).parent.parent / "src" / "streams_agent" / "template" / "streams.csv"


def test_prepare_workspace_creates_csv(tmp_path: Path) -> None:
    """prepare_workspace writes checklist.csv with blank rating/comments for data rows."""
    out = prepare_workspace(TEMPLATE_PATH, tmp_path)
    assert out.exists()
    assert out.name == "checklist.csv"

    with open(out, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Must have at least the 2 header rows plus data rows
    assert len(rows) > 2

    # Data rows (index 2+) should have blank rating and comments columns
    for i, row in enumerate(rows):
        if i < 2:
            continue
        assert row[RATING_COL] == "", f"Row {i} rating column should be blank, got {row[RATING_COL]!r}"
        assert row[COMMENTS_COL] == "", f"Row {i} comments column should be blank, got {row[COMMENTS_COL]!r}"


def test_prepare_workspace_preserves_checklist_content(tmp_path: Path) -> None:
    """First 6 columns of data rows match the original template."""
    out = prepare_workspace(TEMPLATE_PATH, tmp_path)

    with open(TEMPLATE_PATH, newline="") as f:
        original_rows = list(csv.reader(f))

    with open(out, newline="") as f:
        prepared_rows = list(csv.reader(f))

    assert len(prepared_rows) == len(original_rows)

    for i, (orig, prep) in enumerate(zip(original_rows, prepared_rows)):
        # First 6 columns (indices 0-5) must match exactly
        assert orig[:6] == prep[:6], f"Row {i}: first 6 columns differ"


def test_parse_completed_csv(tmp_path: Path) -> None:
    """parse_completed_csv correctly reads ratings and comments from a filled CSV."""
    csv_path = tmp_path / "checklist.csv"
    rows = [
        ["Number", "Item", "Recommendation", "Source", "Guidance", "Examples", "Rating", "Comments"],
        ["item_id", "title", "description", "source", "guidance", "examples", "rating", "comments"],
        ["1.1", "Study design", "Describe design", "STORMS", "", "", "Yes", "Found in abstract"],
        ["1.2", "Sample info", "Describe samples", "STREAMS", "", "", "No", "Missing from paper"],
        ["1.3", "Host info", "Describe host", "STREAMS", "", "", "NA", "Not applicable"],
        ["1.4", "Methods", "Describe methods", "STORMS", "", "", "Partial", "Only partially reported"],
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    result = parse_completed_csv(csv_path, paper_id="paper_001", evaluator_id="agent_v1")
    assert result.paper_id == "paper_001"
    assert result.evaluator_id == "agent_v1"
    assert len(result.assessments) == 4

    a1 = result.get_assessment("1.1")
    assert a1 is not None
    assert a1.rating == AssessmentRating.YES
    assert a1.comments == "Found in abstract"

    a2 = result.get_assessment("1.2")
    assert a2 is not None
    assert a2.rating == AssessmentRating.NO
    assert a2.comments == "Missing from paper"

    a3 = result.get_assessment("1.3")
    assert a3 is not None
    assert a3.rating == AssessmentRating.NOT_APPLICABLE
    assert a3.comments == "Not applicable"

    a4 = result.get_assessment("1.4")
    assert a4 is not None
    assert a4.rating == AssessmentRating.PARTIAL
    assert a4.comments == "Only partially reported"


def test_parse_completed_csv_empty_ratings(tmp_path: Path) -> None:
    """Rows with empty rating parse as None."""
    csv_path = tmp_path / "checklist.csv"
    rows = [
        ["Number", "Item", "Recommendation", "Source", "Guidance", "Examples", "Rating", "Comments"],
        ["item_id", "title", "description", "source", "guidance", "examples", "rating", "comments"],
        ["2.1", "Some item", "Description", "SRC", "", "", "", ""],
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    result = parse_completed_csv(csv_path, paper_id="paper_002", evaluator_id="agent_v1")
    assert len(result.assessments) == 1

    a = result.get_assessment("2.1")
    assert a is not None
    assert a.rating is None
    assert a.comments == ""


# ---------------------------------------------------------------------------
# YAML workspace tests
# ---------------------------------------------------------------------------


def test_prepare_yaml_workspace_creates_file(tmp_path: Path) -> None:
    """prepare_yaml_workspace writes a YAML file with items from the template."""
    out = prepare_yaml_workspace(TEMPLATE_PATH, tmp_path)
    assert out.exists()
    assert out.name == "checklist.yaml"

    with open(out) as f:
        items = yaml.safe_load(f)

    assert isinstance(items, list)
    assert len(items) > 0
    # Each item should have id, title, rating=None, comments=None
    for item in items:
        assert "id" in item
        assert "title" in item
        assert item["rating"] is None
        assert item["comments"] is None
        # IDs should be numeric (not section headers)
        assert item["id"][0].isdigit()


def test_prepare_yaml_workspace_is_compact(tmp_path: Path) -> None:
    """YAML workspace should be much smaller than the CSV template."""
    yaml_path = prepare_yaml_workspace(TEMPLATE_PATH, tmp_path)
    yaml_size = yaml_path.stat().st_size
    csv_size = TEMPLATE_PATH.stat().st_size
    # YAML should be less than half the CSV size (no examples/guidance columns)
    assert yaml_size < csv_size / 2, f"YAML ({yaml_size}B) should be much smaller than CSV ({csv_size}B)"


def test_parse_completed_yaml(tmp_path: Path) -> None:
    """parse_completed_yaml correctly reads ratings and comments."""
    yaml_path = tmp_path / "checklist.yaml"
    items = [
        {"id": "1.1", "title": "Study design", "rating": "Yes", "comments": "Found in abstract"},
        {"id": "1.2", "title": "Sample info", "rating": "No", "comments": "Missing"},
        {"id": "1.3", "title": "Host info", "rating": "NA", "comments": None},
        {"id": "1.4", "title": "Methods", "rating": "Partial", "comments": "p.3 partial"},
    ]
    with open(yaml_path, "w") as f:
        yaml.dump(items, f, sort_keys=False)

    result = parse_completed_yaml(yaml_path, paper_id="paper_001", evaluator_id="agent_v1")
    assert result.paper_id == "paper_001"
    assert len(result.assessments) == 4

    assert result.get_assessment("1.1").rating == AssessmentRating.YES
    assert result.get_assessment("1.1").comments == "Found in abstract"
    assert result.get_assessment("1.2").rating == AssessmentRating.NO
    assert result.get_assessment("1.3").rating == AssessmentRating.NOT_APPLICABLE
    assert result.get_assessment("1.4").rating == AssessmentRating.PARTIAL


def test_parse_completed_yaml_null_ratings(tmp_path: Path) -> None:
    """Items with null rating parse as None."""
    yaml_path = tmp_path / "checklist.yaml"
    items = [{"id": "2.1", "title": "Some item", "rating": None, "comments": None}]
    with open(yaml_path, "w") as f:
        yaml.dump(items, f, sort_keys=False)

    result = parse_completed_yaml(yaml_path, paper_id="p1", evaluator_id="e1")
    assert result.assessments[0].rating is None
    assert result.assessments[0].comments is None


def test_yaml_roundtrip(tmp_path: Path) -> None:
    """Prepare workspace then parse it back — all items present with null ratings."""
    yaml_path = prepare_yaml_workspace(TEMPLATE_PATH, tmp_path)
    result = parse_completed_yaml(yaml_path, paper_id="p1", evaluator_id="e1")
    assert len(result.assessments) > 0
    for a in result.assessments:
        assert a.rating is None
