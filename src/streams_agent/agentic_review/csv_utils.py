"""Workspace utilities for preparing and parsing STREAMS checklist files.

This module provides functions to:
- Prepare a blank checklist workspace (YAML or CSV) from the STREAMS template
- Parse a completed checklist back into a ChecklistAssessment

The YAML format is preferred for agent use — it produces short lines that are
easy for the Edit tool to match, and strips out bulky example/guidance columns
that the agent doesn't need in the working file.

The CSV functions are retained for backward compatibility and for producing
final output in the original template format.
"""

import csv
from pathlib import Path

import yaml

from streams_agent.models.checklist import (
    AssessmentRating,
    ChecklistAssessment,
    ItemAssessment,
)

RATING_COL = 6
COMMENTS_COL = 7

# Number of header rows before data rows begin
_HEADER_ROWS = 2


def _parse_rating(text: str) -> AssessmentRating | None:
    """Normalize a rating string to an AssessmentRating enum value.

    Handles common abbreviations and case-insensitive matching.

    Args:
        text: Raw rating text from the CSV.

    Returns:
        The corresponding AssessmentRating, or None if the text is empty
        or unrecognized.

    Examples:
        >>> _parse_rating("Yes")
        <AssessmentRating.YES: 'Yes'>
        >>> _parse_rating("y")
        <AssessmentRating.YES: 'Yes'>
        >>> _parse_rating("no")
        <AssessmentRating.NO: 'No'>
        >>> _parse_rating("N/A")
        <AssessmentRating.NOT_APPLICABLE: 'NA'>
        >>> _parse_rating("na")
        <AssessmentRating.NOT_APPLICABLE: 'NA'>
        >>> _parse_rating("partial")
        <AssessmentRating.PARTIAL: 'Partial'>
        >>> _parse_rating("p")
        <AssessmentRating.PARTIAL: 'Partial'>
        >>> _parse_rating("") is None
        True
        >>> _parse_rating("  ") is None
        True
    """
    normalized = text.strip().lower()
    if not normalized:
        return None

    if normalized in ("yes", "y"):
        return AssessmentRating.YES
    if normalized in ("no", "n"):
        return AssessmentRating.NO
    if normalized in ("na", "n/a", "not applicable"):
        return AssessmentRating.NOT_APPLICABLE
    if normalized in ("partial", "p"):
        return AssessmentRating.PARTIAL

    return None


def prepare_workspace(template_path: Path, work_dir: Path) -> Path:
    """Prepare a blank checklist CSV workspace from the STREAMS template.

    Reads the STREAMS CSV template, blanks out the rating (column 6) and
    comments (column 7) for all data rows (rows 2+), and writes the result
    to ``work_dir/checklist.csv``.

    Args:
        template_path: Path to the STREAMS CSV template file.
        work_dir: Directory where the prepared checklist CSV will be written.

    Returns:
        Path to the newly created ``checklist.csv``.

    Examples:
        >>> from pathlib import Path
        >>> import tempfile
        >>> template = Path("src/streams_agent/template/streams.csv")
        >>> with tempfile.TemporaryDirectory() as td:
        ...     out = prepare_workspace(template, Path(td))
        ...     out.name
        'checklist.csv'
    """
    with open(template_path, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Blank out rating and comments for data rows (row index >= 2)
    for i in range(_HEADER_ROWS, len(rows)):
        row = rows[i]
        # Ensure the row has enough columns
        while len(row) <= COMMENTS_COL:
            row.append("")
        row[RATING_COL] = ""
        row[COMMENTS_COL] = ""

    output_path = work_dir / "checklist.csv"
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    return output_path


def parse_completed_csv(
    csv_path: Path,
    paper_id: str,
    evaluator_id: str,
) -> ChecklistAssessment:
    """Parse a completed STREAMS checklist CSV into a ChecklistAssessment.

    Reads a filled-in checklist CSV and converts each data row (rows 2+) into
    an ItemAssessment. Rows with an empty item_id (column 0) are skipped, as
    these are section headers.

    Args:
        csv_path: Path to the completed CSV file.
        paper_id: Identifier for the paper being assessed.
        evaluator_id: Identifier for the evaluator (e.g. agent version).

    Returns:
        A ChecklistAssessment containing all parsed item assessments.

    Examples:
        >>> import csv, tempfile
        >>> from pathlib import Path
        >>> rows = [
        ...     ["Number", "Item", "Rec", "Src", "Guide", "Ex", "Rating", "Comments"],
        ...     ["item_id", "title", "desc", "src", "guide", "ex", "rating", "comments"],
        ...     ["1.1", "Design", "Desc", "S", "", "", "Yes", "Found it"],
        ... ]
        >>> with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        ...     writer = csv.writer(f)
        ...     _ = writer.writerows(rows)  # writerows returns None
        ...     p = Path(f.name)
        >>> result = parse_completed_csv(p, "paper1", "agent1")
        >>> result.assessments[0].rating.value
        'Yes'
    """
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    assessments: list[ItemAssessment] = []

    for row in rows[_HEADER_ROWS:]:
        item_id = row[0].strip() if row else ""
        if not item_id:
            continue

        # Skip non-numeric section headers (e.g. "Abstract", "Introduction")
        # Item IDs are numeric like "1", "1.1", "2.3" etc.
        if not item_id[0].isdigit():
            continue

        rating_text = row[RATING_COL] if len(row) > RATING_COL else ""
        comments_text = row[COMMENTS_COL] if len(row) > COMMENTS_COL else ""

        assessments.append(
            ItemAssessment(
                item_id=item_id,
                rating=_parse_rating(rating_text),
                comments=comments_text,
            )
        )

    return ChecklistAssessment(
        checklist_name="STREAMS",
        checklist_version="1.0",
        paper_id=paper_id,
        evaluator_id=evaluator_id,
        assessments=assessments,
    )


# ---------------------------------------------------------------------------
# YAML workspace (preferred for agent use)
# ---------------------------------------------------------------------------


def prepare_yaml_workspace(template_path: Path, work_dir: Path) -> Path:
    """Prepare a lean YAML checklist from the STREAMS CSV template.

    Extracts only the item id and title from the template — enough context
    for the agent to know what each item is, without the bulky examples and
    guidance columns that bloat the working file.

    Args:
        template_path: Path to the STREAMS CSV template file.
        work_dir: Directory where the prepared YAML will be written.

    Returns:
        Path to the newly created ``checklist.yaml``.

    Examples:
        >>> from pathlib import Path
        >>> import tempfile, yaml
        >>> template = Path("src/streams_agent/template/streams.csv")
        >>> td = tempfile.mkdtemp()
        >>> out = prepare_yaml_workspace(template, Path(td))
        >>> out.name
        'checklist.yaml'
        >>> with open(out) as f:
        ...     items = yaml.safe_load(f)
        >>> items[0]["id"]
        '1'
        >>> items[0]["rating"] is None
        True
    """
    with open(template_path, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    items: list[dict] = []
    for row in rows[_HEADER_ROWS:]:
        item_id = row[0].strip() if row else ""
        if not item_id or not item_id[0].isdigit():
            continue
        title = row[1].strip() if len(row) > 1 else ""
        items.append({
            "id": item_id,
            "title": title,
            "rating": None,
            "comments": None,
        })

    output_path = work_dir / "checklist.yaml"
    with open(output_path, "w") as f:
        yaml.dump(items, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return output_path


VALID_RATINGS = {"yes", "y", "no", "n", "na", "n/a", "not applicable", "partial", "p"}


def get_expected_ids(yaml_path: Path) -> list[str]:
    """Return the list of item IDs from a prepared YAML checklist.

    Args:
        yaml_path: Path to the YAML checklist file.

    Returns:
        List of item ID strings.

    Examples:
        >>> import tempfile, yaml
        >>> from pathlib import Path
        >>> items = [{"id": "1.1", "title": "X"}, {"id": "1.2", "title": "Y"}]
        >>> td = tempfile.mkdtemp()
        >>> p = Path(td) / "cl.yaml"
        >>> with open(p, "w") as f:
        ...     yaml.dump(items, f)
        >>> get_expected_ids(p)
        ['1.1', '1.2']
    """
    with open(yaml_path) as f:
        items = yaml.safe_load(f) or []
    return [str(item["id"]) for item in items if "id" in item]


def validate_checklist_yaml(
    yaml_path: Path,
    expected_ids: list[str] | None = None,
) -> list[str]:
    """Validate a completed YAML checklist and return a list of errors.

    Checks:
    - File is valid YAML containing a list of dicts
    - Each item has id, rating, comments keys
    - All non-null ratings are valid (Yes/No/NA/Partial etc.)
    - All expected item IDs are present (if provided)
    - Reports unrated items (rating is null)

    Returns empty list if valid.

    Args:
        yaml_path: Path to the YAML checklist file.
        expected_ids: If provided, check that all these IDs are present.

    Returns:
        List of error strings. Empty means valid.

    Examples:
        >>> import tempfile, yaml
        >>> from pathlib import Path
        >>> items = [{"id": "1.1", "title": "X", "rating": "Yes", "comments": "ok"}]
        >>> td = tempfile.mkdtemp()
        >>> p = Path(td) / "cl.yaml"
        >>> with open(p, "w") as f:
        ...     yaml.dump(items, f)
        >>> validate_checklist_yaml(p, expected_ids=["1.1"])
        []
    """
    with open(yaml_path) as f:
        raw = f.read()

    try:
        items = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        # Extract line info from the YAML error if available
        msg = f"YAML syntax error: {exc}"
        if hasattr(exc, "problem_mark") and exc.problem_mark is not None:
            mark = exc.problem_mark
            msg = (
                f"YAML syntax error at line {mark.line + 1}, column {mark.column + 1}: "
                f"{exc.problem}. "
                "Hint: quote string values that contain colons, e.g. "
                "comments: 'Found on p.2: some detail'"
            )
        return [msg]

    errors: list[str] = []

    if not isinstance(items, list):
        return ["YAML file must contain a list of items"]

    for item in items:
        if not isinstance(item, dict):
            errors.append(f"Expected dict, got {type(item).__name__}")
            continue

    # Check for invalid ratings
    for item in items:
        if not isinstance(item, dict):
            continue
        rating = item.get("rating")
        if rating is not None:
            normalized = str(rating).strip().lower()
            if normalized and normalized not in VALID_RATINGS:
                errors.append(
                    f"Item {item.get('id', '?')}: invalid rating '{rating}' "
                    f"(must be Yes/No/NA/Partial)"
                )

    # Check for unrated items
    unrated = [
        str(item.get("id", "?"))
        for item in items
        if isinstance(item, dict) and item.get("rating") is None
    ]
    if unrated:
        errors.append(
            f"{len(unrated)} items still unrated: {', '.join(unrated)}"
        )

    # Check for missing expected IDs
    if expected_ids is not None:
        present_ids = {
            str(item.get("id", ""))
            for item in items
            if isinstance(item, dict)
        }
        missing = [eid for eid in expected_ids if eid not in present_ids]
        if missing:
            errors.append(
                f"{len(missing)} expected items missing: {', '.join(missing)}"
            )

    return errors


def parse_completed_yaml(
    yaml_path: Path,
    paper_id: str,
    evaluator_id: str,
) -> ChecklistAssessment:
    """Parse a completed YAML checklist into a ChecklistAssessment.

    Args:
        yaml_path: Path to the filled-in YAML file.
        paper_id: Identifier for the paper being assessed.
        evaluator_id: Identifier for the evaluator.

    Returns:
        A ChecklistAssessment containing all parsed item assessments.

    Examples:
        >>> import tempfile, yaml
        >>> from pathlib import Path
        >>> items = [
        ...     {"id": "1.1", "title": "Design", "rating": "Yes", "comments": "Found it"},
        ...     {"id": "1.2", "title": "Env info", "rating": "No", "comments": "Missing"},
        ... ]
        >>> with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        ...     yaml.dump(items, f)
        ...     p = Path(f.name)
        >>> result = parse_completed_yaml(p, "paper1", "agent1")
        >>> result.assessments[0].rating.value
        'Yes'
    """
    with open(yaml_path) as f:
        items = yaml.safe_load(f) or []

    assessments: list[ItemAssessment] = []
    for item in items:
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            continue
        rating_text = str(item.get("rating") or "")
        comments_text = str(item.get("comments") or "")

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
