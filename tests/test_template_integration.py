"""Integration tests for the complete template system workflow."""

import csv
import tempfile
from pathlib import Path

import pytest

from streams_agent.template.loader import TemplateLoader
from streams_agent.template.validator import TemplateValidator
from streams_agent.models.checklist import AssessmentRating


class TestTemplateIntegration:
    """Integration tests for the complete template workflow."""

    def test_complete_workflow(self):
        """Test the complete workflow from template creation to validation."""

        # Step 1: Create a base template with field mappings
        base_content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
            ["Abstract", "", "", "", "", "", "", ""],
            ["1", "Study design", "State study design clearly", "STREAMS", "Be specific", "Cross-sectional study", "", ""],
            ["1.1", "Sample size", "Report sample size calculation", "STREAMS", "Include power analysis", "n=100", "", ""],
            ["2", "Ethics", "State ethics approval", "STREAMS", "Include IRB number", "IRB #12345", "", ""]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(base_content)
            base_template_path = Path(f.name)

        # Step 2: Load checklist from base template
        loader = TemplateLoader()
        checklist = loader.load_checklist_from_template(
            base_template_path,
            checklist_name="TEST_CHECKLIST",
            checklist_version="1.0"
        )

        assert checklist.name == "TEST_CHECKLIST"
        assert len(checklist.items) == 3  # Items 1, 1.1, 2

        # Verify checklist structure
        assert checklist.get_item("1").title == "Study design"
        assert checklist.get_item("1.1").title == "Sample size"
        assert checklist.get_item("2").title == "Ethics"

        # Step 3: Create a filled template
        filled_content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
            ["Abstract", "", "", "", "", "", "", ""],
            ["1", "Study design", "State study design clearly", "STREAMS", "Be specific", "Cross-sectional study", "Yes", "Found in methods section"],
            ["1.1", "Sample size", "Report sample size calculation", "STREAMS", "Include power analysis", "n=100", "No", "Not reported"],
            ["2", "Ethics", "State ethics approval", "STREAMS", "Include IRB number", "IRB #12345", "Yes", "IRB approval mentioned"]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(filled_content)
            filled_template_path = Path(f.name)

        # Step 4: Validate the filled template
        validator = TemplateValidator()
        validation_result = validator.validate_filled_template(
            base_template_path,
            filled_template_path
        )

        assert validation_result.is_valid is True
        assert validation_result.total_items == 3
        assert validation_result.items_with_ratings == 3
        assert validation_result.completion_rate == 1.0

        # Step 5: Load assessment from filled template
        assessment = loader.load_assessment_from_template(
            filled_template_path,
            paper_id="test_paper_123",
            evaluator_id="test_reviewer_1",
            checklist_name="TEST_CHECKLIST",
            checklist_version="1.0"
        )

        assert assessment.paper_id == "test_paper_123"
        assert assessment.evaluator_id == "test_reviewer_1"
        assert len(assessment.assessments) == 3

        # Verify assessment content
        item1_assessment = assessment.get_assessment("1")
        assert item1_assessment.rating == AssessmentRating.YES
        assert item1_assessment.comments == "Found in methods section"

        item11_assessment = assessment.get_assessment("1.1")
        assert item11_assessment.rating == AssessmentRating.NO
        assert item11_assessment.comments == "Not reported"

        item2_assessment = assessment.get_assessment("2")
        assert item2_assessment.rating == AssessmentRating.YES
        assert item2_assessment.comments == "IRB approval mentioned"

        # Step 6: Validate assessment completeness
        completeness_result = validator.validate_assessment_completeness(
            assessment,
            required_completion_rate=0.8
        )

        assert completeness_result.is_valid is True
        assert completeness_result.completion_rate == 1.0

    def test_workflow_with_validation_errors(self):
        """Test workflow when validation finds errors."""

        # Create base template
        base_content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
            ["1", "Study design", "State study design clearly", "STREAMS", "", "", "", ""],
            ["2", "Sample size", "Report sample size", "STREAMS", "", "", "", ""]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(base_content)
            base_template_path = Path(f.name)

        # Create filled template with errors
        filled_content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
            ["1", "WRONG TITLE", "State study design clearly", "STREAMS", "", "", "Invalid_Rating", "Comment 1"],  # Wrong title, invalid rating
            ["2", "Sample size", "Report sample size", "STREAMS", "", "", "", "Comment 2"]  # Missing rating
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(filled_content)
            filled_template_path = Path(f.name)

        # Validate and expect errors
        validator = TemplateValidator()
        validation_result = validator.validate_filled_template(
            base_template_path,
            filled_template_path
        )

        assert validation_result.is_valid is False
        assert len(validation_result.errors) > 0

        # Check for specific error types
        error_types = [error.error_type for error in validation_result.errors]
        assert "column_mismatch" in error_types  # Wrong title
        assert "invalid_rating" in error_types  # Invalid rating

        # Check for warnings
        warning_types = [warning.error_type for warning in validation_result.warnings]
        assert "missing_rating" in warning_types  # Missing rating for item 2

        # Generate validation report
        report = validator.generate_validation_report(validation_result)
        assert "❌ INVALID" in report
        assert "Errors" in report
        assert "Warnings" in report

    def test_workflow_backwards_compatibility(self):
        """Test that the workflow works with old format templates."""

        # Create old format template (no field mappings)
        old_content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["1", "Study design", "State study design clearly", "STREAMS", "", "", "Yes", "Found in methods"],
            ["2", "Sample size", "Report sample size", "STREAMS", "", "", "No", "Not reported"]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(old_content)
            old_template_path = Path(f.name)

        # Load checklist (should work with backwards compatibility)
        loader = TemplateLoader()
        checklist = loader.load_checklist_from_template(old_template_path)

        assert len(checklist.items) == 2
        assert checklist.get_item("1").title == "Study design"
        assert checklist.get_item("2").title == "Sample size"

        # Load assessment (should work with backwards compatibility)
        assessment = loader.load_assessment_from_template(
            old_template_path,
            paper_id="old_paper",
            evaluator_id="old_reviewer"
        )

        assert len(assessment.assessments) == 2
        assert assessment.get_assessment("1").rating == AssessmentRating.YES
        assert assessment.get_assessment("2").rating == AssessmentRating.NO

    def test_robot_template_inspiration(self):
        """Test that the field mapping approach works like OBO ROBOT templates."""

        # Create template inspired by ROBOT template format
        # First row: human-readable headers
        # Second row: field mappings using model attribute names
        robot_style_content = [
            # Human-readable headers
            ["ID", "Label", "Definition", "Source", "Guidance", "Examples", "Assessment", "Notes"],
            # Field mappings (ROBOT-style)
            ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
            # Data rows
            ["methodology.1", "Study methodology", "Describe the overall study methodology", "STREAMS", "Include experimental design", "Randomized controlled trial", "", ""],
            ["methodology.1.1", "Participant selection", "Describe how participants were selected", "STREAMS", "Include inclusion/exclusion criteria", "Adults aged 18-65", "", ""],
            ["results.1", "Primary outcomes", "Report primary outcome measures", "STREAMS", "Include statistical tests", "p < 0.05", "", ""]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(robot_style_content)
            robot_template_path = Path(f.name)

        # Load checklist using the ROBOT-style template
        loader = TemplateLoader()
        checklist = loader.load_checklist_from_template(
            robot_template_path,
            checklist_name="ROBOT_STYLE",
            checklist_version="1.0"
        )

        assert checklist.name == "ROBOT_STYLE"
        assert len(checklist.items) == 3

        # Verify the hierarchical structure is preserved
        methodology_item = checklist.get_item("methodology.1")
        assert methodology_item is not None
        assert methodology_item.title == "Study methodology"
        assert methodology_item.get_group_id() == "methodology"

        participant_item = checklist.get_item("methodology.1.1")
        assert participant_item is not None
        assert participant_item.title == "Participant selection"
        assert participant_item.get_group_id() == "methodology"

        results_item = checklist.get_item("results.1")
        assert results_item is not None
        assert results_item.title == "Primary outcomes"
        assert results_item.get_group_id() == "results"

        # Test grouping functionality
        groups = checklist.get_groups()
        assert "methodology" in groups
        assert "results" in groups
        assert len(groups["methodology"]) == 2  # methodology.1 and methodology.1.1
        assert len(groups["results"]) == 1     # results.1

    def test_error_propagation_and_reporting(self):
        """Test that errors are properly propagated and reported throughout the workflow."""

        # Test with malformed template
        malformed_content = [
            ["Incomplete row"],
            # Missing second row
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(malformed_content)
            malformed_template_path = Path(f.name)

        loader = TemplateLoader()
        validator = TemplateValidator()

        # Loading should fail with clear error
        with pytest.raises(ValueError, match="at least 2 rows"):
            loader.load_checklist_from_template(malformed_template_path)

        with pytest.raises(ValueError, match="at least 2 rows"):
            loader.load_assessment_from_template(
                malformed_template_path, "paper1", "reviewer1"
            )

        # Validation should fail gracefully
        valid_template_content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["ItemAssessment.item_id", "ChecklistItem.title", "ChecklistItem.description", "ChecklistItem.source", "ChecklistItem.additional_guidance", "ChecklistItem.examples", "ItemAssessment.rating", "ItemAssessment.comments"],
            ["1", "Test item", "Test description", "", "", "", "Yes", "Test comment"]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(valid_template_content)
            valid_template_path = Path(f.name)

        validation_result = validator.validate_filled_template(
            valid_template_path,
            malformed_template_path
        )

        assert validation_result.is_valid is False
        assert len(validation_result.errors) > 0
        # Should be a structure error since the file loads but has insufficient rows
        assert validation_result.errors[0].error_type == "structure_error"