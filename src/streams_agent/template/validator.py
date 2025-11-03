"""Template validation utilities."""

import csv
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass

from ..models.checklist import ChecklistAssessment, AssessmentRating


@dataclass
class ValidationError:
    """Represents a validation error found during template comparison."""

    row: int
    column: Optional[int]
    error_type: str
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None


@dataclass
class ValidationResult:
    """Results of template validation."""

    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    total_items: int
    items_with_ratings: int
    completion_rate: float


class TemplateValidator:
    """Validates filled templates against their base templates.

    This validator ensures that:
    1. The first 2 columns of filled templates precisely match the base template
    2. Every item has a rating in the assessment
    3. The structure and field mappings are consistent

    Examples:
        >>> validator = TemplateValidator()
        >>> result = validator.validate_filled_template(
        ...     "streams.csv", "filled_streams.csv"
        ... )
        >>> result.is_valid
        True
    """

    def __init__(self):
        """Initialize the template validator."""
        pass

    def validate_filled_template(
        self,
        base_template_path: Path | str,
        filled_template_path: Path | str
    ) -> ValidationResult:
        """Validate a filled template against its base template.

        Args:
            base_template_path: Path to the base template CSV
            filled_template_path: Path to the filled template CSV

        Returns:
            ValidationResult with validation status and any errors

        Examples:
            >>> validator = TemplateValidator()
            >>> result = validator.validate_filled_template(
            ...     "streams.csv", "filled_streams.csv"
            ... )
            >>> result.total_items > 0
            True
        """
        errors: List[ValidationError] = []
        warnings: List[ValidationError] = []

        # Load both templates
        try:
            base_rows = self._load_csv_rows(base_template_path)
            filled_rows = self._load_csv_rows(filled_template_path)
        except Exception as e:
            errors.append(ValidationError(
                row=0,
                column=None,
                error_type="file_error",
                message=f"Failed to load template files: {e}"
            ))
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                total_items=0,
                items_with_ratings=0,
                completion_rate=0.0
            )

        # Validate structure
        structure_errors = self._validate_structure(base_rows, filled_rows)
        errors.extend(structure_errors)

        if structure_errors:
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                total_items=0,
                items_with_ratings=0,
                completion_rate=0.0
            )

        # Validate first two columns match exactly
        column_errors = self._validate_first_two_columns(base_rows, filled_rows)
        errors.extend(column_errors)

        # Detect format and parse field mappings appropriately
        filled_is_old = self._is_old_format(filled_rows)

        if filled_is_old:
            # Old format: use default field mappings
            field_mappings = {
                'Number': 0, 'Item': 1, 'Recommendation': 2, 'Source': 3,
                'Additional Guidance': 4, 'Example(s)': 5,
                'Present in the manuscript? Yes/No/NA': 6,
                'Comments or location in manuscript': 7
            }
            data_start_row = 1
        else:
            # New format: parse field mappings from row 1
            field_mappings = self._parse_field_mappings(filled_rows[1])
            data_start_row = 2

        # Validate ratings and calculate completion
        rating_errors, rating_warnings, total_items, items_with_ratings = self._validate_ratings(
            filled_rows[data_start_row:], field_mappings
        )
        errors.extend(rating_errors)
        warnings.extend(rating_warnings)

        completion_rate = items_with_ratings / total_items if total_items > 0 else 0.0

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            total_items=total_items,
            items_with_ratings=items_with_ratings,
            completion_rate=completion_rate
        )

    def validate_assessment_completeness(
        self,
        assessment: ChecklistAssessment,
        required_completion_rate: float = 0.8
    ) -> ValidationResult:
        """Validate that an assessment is sufficiently complete.

        Args:
            assessment: The assessment to validate
            required_completion_rate: Minimum required completion rate (0.0-1.0)

        Returns:
            ValidationResult with completeness validation

        Examples:
            >>> from streams_agent.models.checklist import ChecklistAssessment, ItemAssessment, AssessmentRating
            >>> assessment = ChecklistAssessment(
            ...     checklist_name="test", checklist_version="1.0",
            ...     paper_id="p1", evaluator_id="e1",
            ...     assessments=[ItemAssessment(item_id="1", rating=AssessmentRating.YES)]
            ... )
            >>> validator = TemplateValidator()
            >>> result = validator.validate_assessment_completeness(assessment, 0.5)
            >>> result.is_valid
            True
        """
        errors = []
        warnings = []

        total_items = len(assessment.assessments)
        items_with_ratings = sum(1 for a in assessment.assessments if a.rating is not None)
        completion_rate = assessment.get_completion_rate()

        if completion_rate < required_completion_rate:
            errors.append(ValidationError(
                row=0,
                column=None,
                error_type="incomplete_assessment",
                message=f"Assessment completion rate {completion_rate:.1%} is below required {required_completion_rate:.1%}",
                expected=f"{required_completion_rate:.1%}",
                actual=f"{completion_rate:.1%}"
            ))

        # Check for missing ratings on specific items
        for i, item_assessment in enumerate(assessment.assessments):
            if item_assessment.rating is None:
                warnings.append(ValidationError(
                    row=i + 3,  # Account for headers
                    column=None,
                    error_type="missing_rating",
                    message=f"Item '{item_assessment.item_id}' has no rating"
                ))

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            total_items=total_items,
            items_with_ratings=items_with_ratings,
            completion_rate=completion_rate
        )

    def _load_csv_rows(self, file_path: Path | str) -> List[List[str]]:
        """Load CSV file and return all rows."""
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            return list(reader)

    def _validate_structure(
        self,
        base_rows: List[List[str]],
        filled_rows: List[List[str]]
    ) -> List[ValidationError]:
        """Validate that both templates have the required structure."""
        errors = []

        # Detect format for both templates
        base_is_old = self._is_old_format(base_rows)
        filled_is_old = self._is_old_format(filled_rows)

        # Both must use the same format
        if base_is_old != filled_is_old:
            errors.append(ValidationError(
                row=0,
                column=None,
                error_type="structure_error",
                message=f"Template format mismatch: base is {'old' if base_is_old else 'new'} format, filled is {'old' if filled_is_old else 'new'} format"
            ))

        # Check minimum rows based on format
        min_rows = 2 if base_is_old else 3

        if len(base_rows) < min_rows:
            errors.append(ValidationError(
                row=0,
                column=None,
                error_type="structure_error",
                message=f"Base template must have at least {min_rows} rows"
            ))

        if len(filled_rows) < min_rows:
            errors.append(ValidationError(
                row=0,
                column=None,
                error_type="structure_error",
                message=f"Filled template must have at least {min_rows} rows"
            ))

        # Check that both have same number of data rows
        if len(errors) == 0:
            data_start_row = 1 if base_is_old else 2
            base_data_rows = len([row for row in base_rows[data_start_row:] if any(cell.strip() for cell in row)])
            filled_data_rows = len([row for row in filled_rows[data_start_row:] if any(cell.strip() for cell in row)])

            if base_data_rows != filled_data_rows:
                errors.append(ValidationError(
                    row=0,
                    column=None,
                    error_type="structure_error",
                    message=f"Number of data rows differs: base has {base_data_rows}, filled has {filled_data_rows}",
                    expected=str(base_data_rows),
                    actual=str(filled_data_rows)
                ))

        return errors

    def _validate_first_two_columns(
        self,
        base_rows: List[List[str]],
        filled_rows: List[List[str]]
    ) -> List[ValidationError]:
        """Validate that the first two columns match exactly between templates."""
        errors: List[ValidationError] = []

        # Skip validation if format mismatch already detected
        base_is_old = self._is_old_format(base_rows)
        filled_is_old = self._is_old_format(filled_rows)

        if base_is_old != filled_is_old:
            return errors  # Structure validation will catch this

        max_rows = min(len(base_rows), len(filled_rows))
        data_start_row = 1 if base_is_old else 2

        # Only validate data rows (skip headers and field mappings if present)
        for i in range(data_start_row, max_rows):
            base_row = base_rows[i]
            filled_row = filled_rows[i]

            # Skip empty rows
            if not any(cell.strip() for cell in base_row) or not any(cell.strip() for cell in filled_row):
                continue

            # Check first two columns
            for col in range(min(2, len(base_row), len(filled_row))):
                base_value = base_row[col].strip()
                filled_value = filled_row[col].strip()

                if base_value != filled_value:
                    errors.append(ValidationError(
                        row=i + 1,
                        column=col + 1,
                        error_type="column_mismatch",
                        message=f"Column {col + 1} mismatch in row {i + 1}",
                        expected=base_value,
                        actual=filled_value
                    ))

        return errors

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
        """Parse field mappings from the mapping row."""
        mappings = {}
        for i, field in enumerate(mapping_row):
            field = field.strip()
            if field:
                mappings[field] = i
        return mappings

    def _validate_ratings(
        self,
        data_rows: List[List[str]],
        field_mappings: Dict[str, int]
    ) -> Tuple[List[ValidationError], List[ValidationError], int, int]:
        """Validate ratings in the filled template."""
        errors = []
        warnings = []
        total_items = 0
        items_with_ratings = 0

        # Get rating column
        rating_col = field_mappings.get('ItemAssessment.rating')
        if rating_col is None:
            # Fallback to old column name
            rating_col = field_mappings.get('Present in the manuscript? Yes/No/NA', 6)

        item_id_col = field_mappings.get('ItemAssessment.item_id')
        if item_id_col is None:
            # Fallback to old column name
            item_id_col = field_mappings.get('Number', 0)

        for i, row in enumerate(data_rows):
            if not row or not any(cell.strip() for cell in row):
                continue  # Skip empty rows

            row_num = i + 3  # Simplified row number calculation

            # Check if this is a data row (has item ID)
            if len(row) > item_id_col:
                item_id = row[item_id_col].strip()
                # Only process rows with numeric item IDs (skip section headers like "Abstract")
                if item_id and self._is_numeric_item_id(item_id):
                    total_items += 1

                    # Check rating
                    if len(row) > rating_col:
                        rating_text = row[rating_col].strip()
                        if rating_text:
                            # Validate rating value
                            if self._is_valid_rating(rating_text):
                                items_with_ratings += 1
                            else:
                                errors.append(ValidationError(
                                    row=row_num,
                                    column=rating_col + 1,
                                    error_type="invalid_rating",
                                    message=f"Invalid rating '{rating_text}' for item '{item_id}'. Must be Yes/No/NA/Partial",
                                    actual=rating_text
                                ))
                        else:
                            warnings.append(ValidationError(
                                row=row_num,
                                column=rating_col + 1,
                                error_type="missing_rating",
                                message=f"Missing rating for item '{item_id}'"
                            ))
                    else:
                        errors.append(ValidationError(
                            row=row_num,
                            column=rating_col + 1,
                            error_type="missing_column",
                            message=f"Rating column missing for item '{item_id}'"
                        ))

        return errors, warnings, total_items, items_with_ratings

    def _is_numeric_item_id(self, item_id: str) -> bool:
        """Check if item ID is numeric (e.g., '1', '1.1', '2.3.4').

        Args:
            item_id: The item ID to check

        Returns:
            True if the item ID matches numeric pattern
        """
        import re
        return bool(re.match(r'^\d+(\.\d+)*$', item_id.strip()))

    def _is_valid_rating(self, rating_text: str) -> bool:
        """Check if rating text is valid."""
        rating_text = rating_text.lower().strip()
        valid_ratings = {
            'yes', 'y', '1', 'true',
            'no', 'n', '0', 'false',
            'na', 'n/a', 'not applicable', 'not_applicable',
            'partial', 'p', 'partly'
        }
        return rating_text in valid_ratings

    def generate_validation_report(self, result: ValidationResult) -> str:
        """Generate a human-readable validation report.

        Args:
            result: ValidationResult to generate report for

        Returns:
            Formatted validation report as string

        Examples:
            >>> validator = TemplateValidator()
            >>> result = ValidationResult(
            ...     is_valid=True, errors=[], warnings=[],
            ...     total_items=10, items_with_ratings=8, completion_rate=0.8
            ... )
            >>> report = validator.generate_validation_report(result)
            >>> "80.0%" in report
            True
        """
        lines = []
        lines.append("=== Template Validation Report ===")
        lines.append("")

        # Overall status
        status = "✅ VALID" if result.is_valid else "❌ INVALID"
        lines.append(f"Status: {status}")
        lines.append("")

        # Completion statistics
        lines.append("Completion Statistics:")
        lines.append(f"  Total items: {result.total_items}")
        lines.append(f"  Items with ratings: {result.items_with_ratings}")
        lines.append(f"  Completion rate: {result.completion_rate:.1%}")
        lines.append("")

        # Errors
        if result.errors:
            lines.append(f"Errors ({len(result.errors)}):")
            for error in result.errors:
                location = f"Row {error.row}"
                if error.column:
                    location += f", Column {error.column}"
                lines.append(f"  {location}: {error.message}")
                if error.expected and error.actual:
                    lines.append(f"    Expected: '{error.expected}'")
                    lines.append(f"    Actual: '{error.actual}'")
            lines.append("")

        # Warnings
        if result.warnings:
            lines.append(f"Warnings ({len(result.warnings)}):")
            for warning in result.warnings:
                location = f"Row {warning.row}"
                if warning.column:
                    location += f", Column {warning.column}"
                lines.append(f"  {location}: {warning.message}")
            lines.append("")

        return "\n".join(lines)