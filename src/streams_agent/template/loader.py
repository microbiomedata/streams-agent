"""Template loading utilities for checklists and assessments."""

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from ..models.checklist import (
    Checklist,
    ChecklistItem,
    ChecklistAssessment,
    ItemAssessment,
    AssessmentRating,
)


class TemplateLoader:
    """Loads checklists and assessments from template CSV files.

    The extended template format includes:
    - Row 0: Human-friendly column headers
    - Row 1: Field mapping headers using model field names (e.g., ItemAssessment.rating)
    - Row 2+: Data rows

    Examples:
        >>> loader = TemplateLoader()
        >>> checklist = loader.load_checklist_from_template("streams.csv")
        >>> assessment = loader.load_assessment_from_template("filled_streams.csv", "paper123", "reviewer1")
    """

    def __init__(self):
        """Initialize the template loader."""
        pass

    def load_checklist_from_template(
        self,
        template_path: Path | str,
        checklist_name: Optional[str] = None,
        checklist_version: str = "1.0"
    ) -> Checklist:
        """Load a checklist from a template CSV file.

        Args:
            template_path: Path to the template CSV file
            checklist_name: Name for the checklist (defaults to filename)
            checklist_version: Version of the checklist

        Returns:
            Checklist object

        Examples:
            >>> loader = TemplateLoader()
            >>> checklist = loader.load_checklist_from_template("streams.csv")
            >>> len(checklist.items) > 0
            True
        """
        template_path = Path(template_path)
        if checklist_name is None:
            checklist_name = template_path.stem.upper()

        with open(template_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

        if len(rows) < 1:
            raise ValueError("Template must have at least 1 row (headers)")

        # Detect if this is old format (no field mappings) or new format
        is_old_format = self._is_old_format(rows)

        if is_old_format:
            # Old format: headers + data rows
            if len(rows) < 2:
                raise ValueError("Old format template must have at least 2 rows (headers + data)")

            # Use default field mappings for old format
            field_mappings = {
                'Number': 0, 'Item': 1, 'Recommendation': 2, 'Source': 3,
                'Additional Guidance': 4, 'Example(s)': 5,
                'Present in the manuscript? Yes/No/NA': 6,
                'Comments or location in manuscript': 7
            }
            data_start_row = 1
        else:
            # New format: headers + field mappings + data rows
            if len(rows) < 3:
                raise ValueError("New format template must have at least 3 rows (headers + field mappings + data)")

            # Parse field mappings from row 1
            field_mappings = self._parse_field_mappings(rows[1])
            data_start_row = 2

        # Extract checklist items starting from appropriate row
        items = []
        for i, row in enumerate(rows[data_start_row:], start=data_start_row):
            if not row or not any(cell.strip() for cell in row):
                continue  # Skip empty rows

            try:
                item = self._parse_checklist_item(row, field_mappings)
                if item:
                    items.append(item)
            except Exception as e:
                raise ValueError(f"Error parsing row {i + 1}: {e}") from e

        return Checklist(
            name=checklist_name,
            version=checklist_version,
            description=None,
            items=items
        )

    def load_assessment_from_template(
        self,
        filled_template_path: Path | str,
        paper_id: str,
        evaluator_id: str,
        checklist_name: Optional[str] = None,
        checklist_version: str = "1.0"
    ) -> ChecklistAssessment:
        """Load an assessment from a filled template CSV file.

        Args:
            filled_template_path: Path to the filled template CSV file
            paper_id: ID of the paper being assessed
            evaluator_id: ID of the evaluator
            checklist_name: Name of the checklist (defaults to filename)
            checklist_version: Version of the checklist

        Returns:
            ChecklistAssessment object

        Examples:
            >>> loader = TemplateLoader()
            >>> assessment = loader.load_assessment_from_template(
            ...     "filled_streams.csv", "paper123", "reviewer1"
            ... )
            >>> assessment.paper_id
            'paper123'
        """
        filled_template_path = Path(filled_template_path)
        if checklist_name is None:
            checklist_name = filled_template_path.stem.replace('_filled', '').upper()

        with open(filled_template_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

        if len(rows) < 1:
            raise ValueError("Template must have at least 1 row (headers)")

        # Detect if this is old format (no field mappings) or new format
        is_old_format = self._is_old_format(rows)

        if is_old_format:
            # Old format: headers + data rows
            if len(rows) < 2:
                raise ValueError("Old format template must have at least 2 rows (headers + data)")

            # Use default field mappings for old format
            field_mappings = {
                'Number': 0, 'Item': 1, 'Recommendation': 2, 'Source': 3,
                'Additional Guidance': 4, 'Example(s)': 5,
                'Present in the manuscript? Yes/No/NA': 6,
                'Comments or location in manuscript': 7
            }
            data_start_row = 1
        else:
            # New format: headers + field mappings + data rows
            if len(rows) < 3:
                raise ValueError("New format template must have at least 3 rows (headers + field mappings + data)")

            # Parse field mappings from row 1
            field_mappings = self._parse_field_mappings(rows[1])
            data_start_row = 2

        # Extract assessments starting from appropriate row
        assessments = []
        for i, row in enumerate(rows[data_start_row:], start=data_start_row):
            if not row or not any(cell.strip() for cell in row):
                continue  # Skip empty rows

            try:
                assessment = self._parse_item_assessment(row, field_mappings)
                if assessment:
                    assessments.append(assessment)
            except Exception as e:
                raise ValueError(f"Error parsing assessment row {i + 1}: {e}") from e

        return ChecklistAssessment(
            checklist_name=checklist_name,
            checklist_version=checklist_version,
            paper_id=paper_id,
            evaluator_id=evaluator_id,
            assessments=assessments,
            assessment_date=datetime.now()
        )

    def _is_old_format(self, rows: List[List[str]]) -> bool:
        """Detect if template is using old format (no field mappings).

        Old format: headers + data rows
        New format: headers + field mappings + data rows

        We detect new format by checking if row 1 contains field mappings
        (fields with dots like "ItemAssessment.rating").

        Args:
            rows: All rows from the CSV file

        Returns:
            True if old format, False if new format
        """
        if len(rows) < 2:
            return True  # Assume old format if insufficient rows

        # Check if row 1 contains field mappings (fields with dots)
        row1 = rows[1]
        for cell in row1:
            if isinstance(cell, str) and '.' in cell and any(
                cell.startswith(prefix) for prefix in ['ItemAssessment.', 'ChecklistItem.']
            ):
                return False  # Found field mapping, so it's new format

        return True  # No field mappings found, so it's old format

    def _parse_field_mappings(self, mapping_row: List[str]) -> Dict[str, int]:
        """Parse field mappings from the mapping row.

        Args:
            mapping_row: Row containing field mappings

        Returns:
            Dictionary mapping field names to column indices
        """
        mappings = {}
        for i, field in enumerate(mapping_row):
            field = field.strip()
            if field:
                mappings[field] = i
        return mappings

    def _parse_checklist_item(
        self,
        row: List[str],
        field_mappings: Dict[str, int]
    ) -> Optional[ChecklistItem]:
        """Parse a checklist item from a data row.

        Args:
            row: Data row from CSV
            field_mappings: Field name to column index mapping

        Returns:
            ChecklistItem if valid, None if this is a section header
        """
        # Get required fields with fallbacks for backwards compatibility
        item_id_col = field_mappings.get('ItemAssessment.item_id', field_mappings.get('Number', 0))
        title_col = field_mappings.get('ChecklistItem.title', field_mappings.get('Item', 1))
        description_col = field_mappings.get('ChecklistItem.description', field_mappings.get('Recommendation', 2))

        if len(row) <= max(item_id_col, title_col, description_col):
            return None

        item_id = row[item_id_col].strip()
        title = row[title_col].strip()
        description = row[description_col].strip()

        # Skip if no item ID (section headers)
        if not item_id or not title:
            return None

        # Get optional fields
        source = ""
        additional_guidance = ""
        examples = []

        source_col = field_mappings.get('ChecklistItem.source', field_mappings.get('Source'))
        if source_col is not None and len(row) > source_col:
            source = row[source_col].strip()

        guidance_col = field_mappings.get('ChecklistItem.additional_guidance', field_mappings.get('Additional Guidance'))
        if guidance_col is not None and len(row) > guidance_col:
            additional_guidance = row[guidance_col].strip()

        examples_col = field_mappings.get('ChecklistItem.examples', field_mappings.get('Example(s)'))
        if examples_col is not None and len(row) > examples_col:
            examples_text = row[examples_col].strip()
            if examples_text:
                examples = [examples_text]

        return ChecklistItem(
            id=item_id,
            title=title,
            description=description,
            source=source if source else None,
            additional_guidance=additional_guidance if additional_guidance else None,
            examples=examples,
            category=None
        )

    def _parse_item_assessment(
        self,
        row: List[str],
        field_mappings: Dict[str, int]
    ) -> Optional[ItemAssessment]:
        """Parse an item assessment from a data row.

        Args:
            row: Data row from CSV
            field_mappings: Field name to column index mapping

        Returns:
            ItemAssessment if valid, None if no rating provided
        """
        # Get required fields
        item_id_col = field_mappings.get('ItemAssessment.item_id', field_mappings.get('Number', 0))
        rating_col = field_mappings.get('ItemAssessment.rating', field_mappings.get('Present in the manuscript? Yes/No/NA', 6))

        if len(row) <= max(item_id_col, rating_col):
            return None

        item_id = row[item_id_col].strip()
        rating_text = row[rating_col].strip()

        # Skip if no item ID or rating
        if not item_id or not rating_text:
            return None

        # Parse rating
        rating = self._parse_rating(rating_text)

        # Get comments
        comments = ""
        comments_col = field_mappings.get('ItemAssessment.comments', field_mappings.get('Comments or location in manuscript'))
        if comments_col is not None and len(row) > comments_col:
            comments = row[comments_col].strip()

        return ItemAssessment(
            item_id=item_id,
            rating=rating,
            comments=comments if comments else None,
            confidence=None
        )

    def _parse_rating(self, rating_text: str) -> Optional[AssessmentRating]:
        """Parse rating text into AssessmentRating enum.

        Args:
            rating_text: Text representation of rating

        Returns:
            AssessmentRating enum value or None
        """
        rating_text = rating_text.lower().strip()

        if rating_text in ('yes', 'y', '1', 'true'):
            return AssessmentRating.YES
        elif rating_text in ('no', 'n', '0', 'false'):
            return AssessmentRating.NO
        elif rating_text in ('na', 'n/a', 'not applicable', 'not_applicable'):
            return AssessmentRating.NOT_APPLICABLE
        elif rating_text in ('partial', 'p', 'partly'):
            return AssessmentRating.PARTIAL
        else:
            return None