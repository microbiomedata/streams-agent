"""STREAMS-specific loaders for converting CSV/Excel to checklist models."""

import re
from pathlib import Path
from typing import Optional, Dict

import pandas as pd

from ..models import (
    ChecklistItem,
    Checklist,
    ItemAssessment,
    ChecklistAssessment,
    AssessmentRating,
)


def normalize_rating(rating: str) -> Optional[AssessmentRating]:
    """Normalize rating values to standard AssessmentRating enum.

    Args:
        rating: Raw rating value from Excel/CSV

    Returns:
        Normalized rating or None if invalid

    Examples:
        >>> normalize_rating("Yes")
        <AssessmentRating.YES: 'Yes'>
        >>> normalize_rating("n/a")
        <AssessmentRating.NOT_APPLICABLE: 'NA'>
        >>> normalize_rating("invalid")
    """
    if pd.isna(rating):
        return None

    rating_str = str(rating).strip().lower()

    if rating_str in ["yes", "y", "1", "true"]:
        return AssessmentRating.YES
    elif rating_str in ["no", "n", "0", "false"]:
        return AssessmentRating.NO
    elif rating_str in ["na", "n/a", "not applicable", "not_applicable"]:
        return AssessmentRating.NOT_APPLICABLE
    elif rating_str in ["partial", "partially", "p"]:
        return AssessmentRating.PARTIAL
    else:
        return None


def load_streams_checklist_from_csv(csv_path: Path) -> Checklist:
    """Load STREAMS checklist from CSV template.

    This function now uses the new TemplateLoader which supports both
    old format (for backwards compatibility) and new extended format
    with field mappings.

    Args:
        csv_path: Path to the STREAMS CSV template

    Returns:
        Checklist object with all STREAMS items

    Examples:
        >>> from pathlib import Path
        >>> checklist = load_streams_checklist_from_csv(
        ...     Path("src/streams_agent/template/streams.csv")
        ... )
        >>> checklist.name
        'STREAMS'
    """
    from ..template.loader import TemplateLoader

    loader = TemplateLoader()
    return loader.load_checklist_from_template(
        csv_path,
        checklist_name="STREAMS",
        checklist_version="1.0"
    )


def parse_assessment_filename(filename: str) -> Dict[str, str]:
    """Parse evaluation filename to extract paper ID and reviewer ID.

    Args:
        filename: The Excel filename to parse

    Returns:
        Dictionary with paper_id and reviewer_id

    Examples:
        >>> parse_assessment_filename("Paper39_Reviewer1_STREAMS_evaluation.xlsx")
        {'paper_id': 'Paper39', 'reviewer_id': 'Reviewer1'}
    """
    match = re.match(r"Paper(\d+)_Reviewer(\d+)_", filename)
    if match:
        return {
            "paper_id": f"Paper{match.group(1)}",
            "reviewer_id": f"Reviewer{match.group(2)}",
        }
    return {"paper_id": "", "reviewer_id": ""}


def load_streams_assessment_from_excel(
    excel_path: Path, checklist: Optional[Checklist] = None
) -> Optional[ChecklistAssessment]:
    """Load a STREAMS assessment from an Excel file.

    Args:
        excel_path: Path to the Excel assessment file
        checklist: Optional checklist to validate against

    Returns:
        ChecklistAssessment object or None if loading fails

    Examples:
        >>> from pathlib import Path
        >>> assessment = load_streams_assessment_from_excel(
        ...     Path("evals/streams-gdrive/Benchmarking STREAMS Exemplars/Paper37_Reviewer1_STREAMS_evaluation_10.1099_acmi.0.000902.v3.xlsx")
        ... )
        >>> assessment.paper_id if assessment else None
        'Paper37'
    """
    try:
        # Parse filename for paper and reviewer IDs
        filename_info = parse_assessment_filename(excel_path.name)
        if not filename_info["paper_id"] or not filename_info["reviewer_id"]:
            return None

        # Read Excel file with header at row 2 (0-indexed)
        df = pd.read_excel(excel_path, sheet_name=0, header=2)

        # Standardize column names
        columns_map = {}
        for col in df.columns:
            col_str = str(col).lower()
            if "number" in col_str:
                columns_map[col] = "item_number"
            elif "present" in col_str and ("yes" in col_str or "no" in col_str):
                columns_map[col] = "rating"
            elif "comment" in col_str:
                columns_map[col] = "comments"

        df = df.rename(columns=columns_map)

        # Extract assessments
        assessments = []
        for _, row in df.iterrows():
            if pd.isna(row.get("item_number")):
                continue

            item_id = str(row["item_number"]).strip()

            # Filter to valid item numbers (numeric or x.y format)
            if not re.match(r"^\d+(\.\d+)?$", item_id):
                continue

            # Clean up item ID
            if item_id.endswith(".0"):
                item_id = item_id[:-2]

            # Get rating and comments
            rating = normalize_rating(row.get("rating")) if "rating" in row else None
            comments = (
                str(row["comments"]).strip()
                if pd.notna(row.get("comments"))
                else None
            )

            assessment = ItemAssessment(
                item_id=item_id,
                rating=rating,
                comments=comments,
                confidence=None,
            )
            assessments.append(assessment)

        return ChecklistAssessment(
            checklist_name="STREAMS",
            checklist_version="1.0",
            paper_id=filename_info["paper_id"],
            evaluator_id=filename_info["reviewer_id"],
            assessments=assessments,
            assessment_date=None,
        )

    except Exception as e:
        print(f"Error loading assessment from {excel_path}: {e}")
        return None


def save_streams_checklist_to_csv(checklist: Checklist, csv_path: Path) -> None:
    """Save a STREAMS checklist to CSV format.

    Args:
        checklist: The checklist to save
        csv_path: Path where to save the CSV

    Examples:
        >>> from pathlib import Path
        >>> checklist = Checklist(name="Test", version="1.0", items=[
        ...     ChecklistItem(id="1", title="Test", description="Test item")
        ... ])
        >>> save_streams_checklist_to_csv(checklist, Path("test_output.csv"))
    """
    rows = []
    for item in checklist.items:
        row = {
            "Number": item.id,
            "Item": item.title,
            "Recommendation": item.description,
            "Source": item.source or "",
            "Additional Guidance": item.additional_guidance or "",
            "Example(s)": item.examples[0] if item.examples else "",
            "Present in the manuscript? Yes/No/NA": "",
            "Comments or location in manuscript": "",
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)


def save_streams_assessment_to_csv(
    assessment: ChecklistAssessment, csv_path: Path, checklist: Optional[Checklist] = None
) -> None:
    """Save a STREAMS assessment to CSV format.

    Args:
        assessment: The assessment to save
        csv_path: Path where to save the CSV
        checklist: Optional checklist for additional item information

    Examples:
        >>> from pathlib import Path
        >>> assessment = ChecklistAssessment(
        ...     checklist_name="STREAMS", checklist_version="1.0",
        ...     paper_id="Paper1", evaluator_id="Reviewer1",
        ...     assessments=[ItemAssessment(item_id="1", rating=AssessmentRating.YES)]
        ... )
        >>> save_streams_assessment_to_csv(assessment, Path("test_assessment.csv"))
    """
    # Create assessment lookup
    assessment_lookup = {a.item_id: a for a in assessment.assessments}

    rows = []
    if checklist:
        # Use checklist items as the base
        for item in checklist.items:
            item_assessment = assessment_lookup.get(item.id)
            row = {
                "Number": item.id,
                "Item": item.title,
                "Recommendation": item.description,
                "Source": item.source or "",
                "Additional Guidance": item.additional_guidance or "",
                "Example(s)": item.examples[0] if item.examples else "",
                "Present in the manuscript? Yes/No/NA": (
                    item_assessment.rating.value if item_assessment and item_assessment.rating else ""
                ),
                "Comments or location in manuscript": (
                    item_assessment.comments or "" if item_assessment else ""
                ),
            }
            rows.append(row)
    else:
        # Use only assessed items
        for item_assessment in assessment.assessments:
            row = {
                "Number": item_assessment.item_id,
                "Item": "",  # Not available without checklist
                "Recommendation": "",
                "Source": "",
                "Additional Guidance": "",
                "Example(s)": "",
                "Present in the manuscript? Yes/No/NA": (
                    item_assessment.rating.value if item_assessment.rating else ""
                ),
                "Comments or location in manuscript": item_assessment.comments or "",
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)