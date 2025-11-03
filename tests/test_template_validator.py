"""Tests for template validation functionality."""

import csv
import tempfile
from pathlib import Path

import pytest

from streams_agent.models.checklist import (
    ChecklistAssessment,
    ItemAssessment,
    AssessmentRating,
)
from streams_agent.template.validator import TemplateValidator, ValidationError, ValidationResult


@pytest.fixture
def base_template_csv():
    """Create a base template CSV for testing."""
    content = [
        ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
        ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
        ["Abstract", "", "", "", "", "", "", ""],
        ["1", "Structured abstract", "Abstract should include structured information", "STORMS", "Word limit considerations", "Example abstract text", "", ""],
        ["1.1", "Study design", "State study design in abstract", "STORMS", "See 3.0 for details", "16S rRNA sequencing", "", ""],
        ["2", "Background", "Summarize motivation and background", "STREAMS", "", "Knowledge gaps", "", ""]
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerows(content)
        return Path(f.name)


@pytest.fixture
def valid_filled_template_csv():
    """Create a valid filled template CSV for testing."""
    content = [
        ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
        ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
        ["Abstract", "", "", "", "", "", "", ""],
        ["1", "Structured abstract", "Abstract should include structured information", "STORMS", "Word limit considerations", "Example abstract text", "Yes", "Found in introduction"],
        ["1.1", "Study design", "State study design in abstract", "STORMS", "See 3.0 for details", "16S rRNA sequencing", "No", "Not clearly stated"],
        ["2", "Background", "Summarize motivation and background", "STREAMS", "", "Knowledge gaps", "Partial", "Some background provided"]
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerows(content)
        return Path(f.name)


@pytest.fixture
def invalid_filled_template_csv():
    """Create an invalid filled template CSV for testing."""
    content = [
        ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
        ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
        ["Abstract", "", "", "", "", "", "", ""],
        ["1", "DIFFERENT TITLE", "Abstract should include structured information", "STORMS", "Word limit considerations", "Example abstract text", "Yes", "Found in introduction"],  # Different title
        ["1.1", "Study design", "State study design in abstract", "STORMS", "See 3.0 for details", "16S rRNA sequencing", "Invalid", "Not clearly stated"],  # Invalid rating
        ["2", "Background", "Summarize motivation and background", "STREAMS", "", "Knowledge gaps", "", "Some background provided"]  # Missing rating
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerows(content)
        return Path(f.name)


class TestTemplateValidator:
    """Test cases for TemplateValidator."""

    def test_validate_valid_filled_template(self, base_template_csv, valid_filled_template_csv):
        """Test validation of a valid filled template."""
        validator = TemplateValidator()
        result = validator.validate_filled_template(base_template_csv, valid_filled_template_csv)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.total_items == 3
        assert result.items_with_ratings == 3
        assert result.completion_rate == 1.0

    def test_validate_invalid_filled_template(self, base_template_csv, invalid_filled_template_csv):
        """Test validation of an invalid filled template."""
        validator = TemplateValidator()
        result = validator.validate_filled_template(base_template_csv, invalid_filled_template_csv)

        assert result.is_valid is False
        assert len(result.errors) > 0

        # Check for specific errors
        error_types = [error.error_type for error in result.errors]
        assert "column_mismatch" in error_types  # Different title
        assert "invalid_rating" in error_types  # Invalid rating value

        # Check warnings for missing rating
        warning_types = [warning.error_type for warning in result.warnings]
        assert "missing_rating" in warning_types

    def test_validate_column_mismatch(self, base_template_csv):
        """Test detection of column mismatches."""
        # Create template with mismatched columns but same structure
        content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
            ["Abstract", "", "", "", "", "", "", ""],
            ["WRONG", "Structured abstract", "Abstract should include structured information", "STORMS", "Word limit considerations", "Example abstract text", "Yes", "Found in introduction"],  # Wrong item ID
            ["1.1", "Study design", "State study design in abstract", "STORMS", "See 3.0 for details", "16S rRNA sequencing", "No", "Not clearly stated"],  # Keep other rows
            ["2", "Background", "Summarize motivation and background", "STREAMS", "", "Knowledge gaps", "Partial", "Some background provided"]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(content)
            mismatched_template = Path(f.name)

        validator = TemplateValidator()
        result = validator.validate_filled_template(base_template_csv, mismatched_template)

        assert result.is_valid is False
        column_mismatch_errors = [e for e in result.errors if e.error_type == "column_mismatch"]
        assert len(column_mismatch_errors) > 0

        # Check specific mismatch details
        first_mismatch = column_mismatch_errors[0]
        assert first_mismatch.expected == "1"
        assert first_mismatch.actual == "WRONG"

    def test_validate_structure_errors(self, base_template_csv):
        """Test validation of structural issues."""
        # Create template with insufficient rows
        content = [
            ["Number", "Item"]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(content)
            bad_template = Path(f.name)

        validator = TemplateValidator()
        result = validator.validate_filled_template(base_template_csv, bad_template)

        assert result.is_valid is False
        structure_errors = [e for e in result.errors if e.error_type == "structure_error"]
        assert len(structure_errors) > 0

    def test_validate_rating_values(self, base_template_csv):
        """Test validation of rating values."""
        # Create template with various rating values
        content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
            ["1", "Test 1", "Description 1", "", "", "", "Yes", "Comment 1"],  # Valid
            ["2", "Test 2", "Description 2", "", "", "", "Invalid", "Comment 2"],  # Invalid
            ["3", "Test 3", "Description 3", "", "", "", "Maybe", "Comment 3"],  # Invalid
            ["4", "Test 4", "Description 4", "", "", "", "", "Comment 4"],  # Missing
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(content)
            rating_template = Path(f.name)

        validator = TemplateValidator()
        result = validator.validate_filled_template(base_template_csv, rating_template)

        # Should have structure error first (different number of data rows)
        assert result.is_valid is False

    def test_validate_assessment_completeness(self):
        """Test assessment completeness validation."""
        # Create assessment with partial completion
        assessments = [
            ItemAssessment(item_id="1", rating=AssessmentRating.YES, comments="Comment 1"),
            ItemAssessment(item_id="2", rating=None, comments="Comment 2"),  # Missing rating
            ItemAssessment(item_id="3", rating=AssessmentRating.NO, comments="Comment 3"),
            ItemAssessment(item_id="4", rating=None, comments="Comment 4"),  # Missing rating
        ]

        assessment = ChecklistAssessment(
            checklist_name="Test",
            checklist_version="1.0",
            paper_id="paper1",
            evaluator_id="reviewer1",
            assessments=assessments
        )

        validator = TemplateValidator()

        # Test with 80% requirement (should fail - only 50% complete)
        result = validator.validate_assessment_completeness(assessment, 0.8)
        assert result.is_valid is False
        assert result.completion_rate == 0.5
        assert result.total_items == 4
        assert result.items_with_ratings == 2

        # Test with 40% requirement (should pass)
        result = validator.validate_assessment_completeness(assessment, 0.4)
        assert result.is_valid is True

        # Check warnings for missing ratings
        assert len(result.warnings) == 2
        missing_warnings = [w for w in result.warnings if w.error_type == "missing_rating"]
        assert len(missing_warnings) == 2

    def test_is_valid_rating(self):
        """Test rating validation function."""
        validator = TemplateValidator()

        # Valid ratings
        assert validator._is_valid_rating("Yes") is True
        assert validator._is_valid_rating("y") is True
        assert validator._is_valid_rating("No") is True
        assert validator._is_valid_rating("n") is True
        assert validator._is_valid_rating("NA") is True
        assert validator._is_valid_rating("n/a") is True
        assert validator._is_valid_rating("Partial") is True
        assert validator._is_valid_rating("p") is True

        # Invalid ratings
        assert validator._is_valid_rating("Maybe") is False
        assert validator._is_valid_rating("Sometimes") is False
        assert validator._is_valid_rating("Invalid") is False
        assert validator._is_valid_rating("") is False

    def test_generate_validation_report(self):
        """Test validation report generation."""
        # Create a validation result with errors and warnings
        errors = [
            ValidationError(
                row=4,
                column=2,
                error_type="column_mismatch",
                message="Column mismatch",
                expected="Expected",
                actual="Actual"
            ),
            ValidationError(
                row=5,
                column=7,
                error_type="invalid_rating",
                message="Invalid rating"
            )
        ]

        warnings = [
            ValidationError(
                row=6,
                column=7,
                error_type="missing_rating",
                message="Missing rating"
            )
        ]

        result = ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            total_items=10,
            items_with_ratings=7,
            completion_rate=0.7
        )

        validator = TemplateValidator()
        report = validator.generate_validation_report(result)

        # Check report content
        assert "❌ INVALID" in report
        assert "Total items: 10" in report
        assert "Items with ratings: 7" in report
        assert "70.0%" in report
        assert "Errors (2)" in report
        assert "Warnings (1)" in report
        assert "Row 4, Column 2" in report
        assert "Expected: 'Expected'" in report
        assert "Actual: 'Actual'" in report

    def test_generate_validation_report_valid(self):
        """Test validation report generation for valid result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            total_items=5,
            items_with_ratings=5,
            completion_rate=1.0
        )

        validator = TemplateValidator()
        report = validator.generate_validation_report(result)

        assert "✅ VALID" in report
        assert "100.0%" in report
        assert "Errors" not in report
        assert "Warnings" not in report

    def test_file_loading_error(self):
        """Test handling of file loading errors."""
        validator = TemplateValidator()

        # Test with non-existent files
        result = validator.validate_filled_template(
            Path("nonexistent1.csv"),
            Path("nonexistent2.csv")
        )

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert result.errors[0].error_type == "file_error"
        assert "Failed to load template files" in result.errors[0].message

    def test_backwards_compatibility_old_format(self, base_template_csv):
        """Test validation works with old format templates."""
        # Create old format template (no field mappings row)
        content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["1", "Test item", "Test description", "TEST", "Test guidance", "Test example", "Yes", "Test comment"]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(content)
            old_template = Path(f.name)

        validator = TemplateValidator()
        result = validator.validate_filled_template(base_template_csv, old_template)

        # Should detect structure error (different number of rows)
        assert result.is_valid is False
        structure_errors = [e for e in result.errors if e.error_type == "structure_error"]
        assert len(structure_errors) > 0