"""Tests for template loading functionality."""

import csv
import tempfile
from pathlib import Path

import pytest

from streams_agent.models.checklist import AssessmentRating
from streams_agent.template.loader import TemplateLoader


@pytest.fixture
def sample_template_csv():
    """Create a sample template CSV for testing."""
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
def sample_filled_template_csv():
    """Create a sample filled template CSV for testing."""
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


class TestTemplateLoader:
    """Test cases for TemplateLoader."""

    def test_load_checklist_from_template(self, sample_template_csv):
        """Test loading checklist from template CSV."""
        loader = TemplateLoader()
        checklist = loader.load_checklist_from_template(sample_template_csv)

        assert checklist.name == sample_template_csv.stem.upper()
        assert checklist.version == "1.0"
        assert len(checklist.items) == 3  # Items 1, 1.1, 2 (Abstract is skipped)

        # Check first item
        item1 = checklist.get_item("1")
        assert item1 is not None
        assert item1.title == "Structured abstract"
        assert item1.description == "Abstract should include structured information"
        assert item1.source == "STORMS"
        assert item1.additional_guidance == "Word limit considerations"
        assert item1.examples == ["Example abstract text"]

        # Check sub-item
        item11 = checklist.get_item("1.1")
        assert item11 is not None
        assert item11.title == "Study design"

    def test_load_checklist_custom_name_version(self, sample_template_csv):
        """Test loading checklist with custom name and version."""
        loader = TemplateLoader()
        checklist = loader.load_checklist_from_template(
            sample_template_csv,
            checklist_name="CUSTOM",
            checklist_version="2.0"
        )

        assert checklist.name == "CUSTOM"
        assert checklist.version == "2.0"

    def test_load_assessment_from_template(self, sample_filled_template_csv):
        """Test loading assessment from filled template CSV."""
        loader = TemplateLoader()
        assessment = loader.load_assessment_from_template(
            sample_filled_template_csv,
            paper_id="paper123",
            evaluator_id="reviewer1"
        )

        assert assessment.paper_id == "paper123"
        assert assessment.evaluator_id == "reviewer1"
        assert assessment.checklist_name == sample_filled_template_csv.stem.upper()
        assert len(assessment.assessments) == 3

        # Check ratings
        item1_assessment = assessment.get_assessment("1")
        assert item1_assessment is not None
        assert item1_assessment.rating == AssessmentRating.YES
        assert item1_assessment.comments == "Found in introduction"

        item11_assessment = assessment.get_assessment("1.1")
        assert item11_assessment is not None
        assert item11_assessment.rating == AssessmentRating.NO
        assert item11_assessment.comments == "Not clearly stated"

        item2_assessment = assessment.get_assessment("2")
        assert item2_assessment is not None
        assert item2_assessment.rating == AssessmentRating.PARTIAL
        assert item2_assessment.comments == "Some background provided"

    def test_load_assessment_custom_checklist_info(self, sample_filled_template_csv):
        """Test loading assessment with custom checklist information."""
        loader = TemplateLoader()
        assessment = loader.load_assessment_from_template(
            sample_filled_template_csv,
            paper_id="paper456",
            evaluator_id="reviewer2",
            checklist_name="CUSTOM_CHECKLIST",
            checklist_version="1.5"
        )

        assert assessment.checklist_name == "CUSTOM_CHECKLIST"
        assert assessment.checklist_version == "1.5"

    def test_parse_field_mappings(self):
        """Test parsing field mappings from mapping row."""
        loader = TemplateLoader()
        mapping_row = ["ItemAssessment.item_id", "ChecklistItem.title", "", "ChecklistItem.source"]

        mappings = loader._parse_field_mappings(mapping_row)

        assert mappings == {
            "ItemAssessment.item_id": 0,
            "ChecklistItem.title": 1,
            "ChecklistItem.source": 3
        }

    def test_parse_rating_variations(self):
        """Test parsing various rating formats."""
        loader = TemplateLoader()

        # Test Yes variations
        assert loader._parse_rating("Yes") == AssessmentRating.YES
        assert loader._parse_rating("y") == AssessmentRating.YES
        assert loader._parse_rating("1") == AssessmentRating.YES
        assert loader._parse_rating("true") == AssessmentRating.YES

        # Test No variations
        assert loader._parse_rating("No") == AssessmentRating.NO
        assert loader._parse_rating("n") == AssessmentRating.NO
        assert loader._parse_rating("0") == AssessmentRating.NO
        assert loader._parse_rating("false") == AssessmentRating.NO

        # Test NA variations
        assert loader._parse_rating("NA") == AssessmentRating.NOT_APPLICABLE
        assert loader._parse_rating("n/a") == AssessmentRating.NOT_APPLICABLE
        assert loader._parse_rating("not applicable") == AssessmentRating.NOT_APPLICABLE

        # Test Partial variations
        assert loader._parse_rating("Partial") == AssessmentRating.PARTIAL
        assert loader._parse_rating("p") == AssessmentRating.PARTIAL
        assert loader._parse_rating("partly") == AssessmentRating.PARTIAL

        # Test invalid
        assert loader._parse_rating("invalid") is None
        assert loader._parse_rating("") is None

    def test_backwards_compatibility_old_format(self):
        """Test that loader works with old format templates (no field mappings)."""
        # Create old format template
        content = [
            ["Number", "Item", "Recommendation", "Source", "Additional Guidance", "Example(s)", "Present in the manuscript? Yes/No/NA", "Comments or location in manuscript"],
            ["1", "Test item", "Test description", "TEST", "Test guidance", "Test example", "Yes", "Test comment"]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(content)
            template_path = Path(f.name)

        loader = TemplateLoader()

        # Should work as checklist
        checklist = loader.load_checklist_from_template(template_path)
        assert len(checklist.items) == 1
        assert checklist.items[0].title == "Test item"

        # Should work as assessment
        assessment = loader.load_assessment_from_template(
            template_path, "paper1", "reviewer1"
        )
        assert len(assessment.assessments) == 1
        assert assessment.assessments[0].rating == AssessmentRating.YES

    def test_error_handling_insufficient_rows(self):
        """Test error handling when template has insufficient rows."""
        # Create template with only 2 rows
        content = [
            ["Number", "Item"],
            ["ItemAssessment.item_id", "ChecklistItem.title"]
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(content)
            template_path = Path(f.name)

        loader = TemplateLoader()

        with pytest.raises(ValueError, match="at least 3 rows"):
            loader.load_checklist_from_template(template_path)

        with pytest.raises(ValueError, match="at least 3 rows"):
            loader.load_assessment_from_template(template_path, "paper1", "reviewer1")

    def test_skip_empty_rows(self, sample_template_csv):
        """Test that empty rows are properly skipped."""
        # Add empty rows to template
        with open(sample_template_csv, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([])  # Empty row
            writer.writerow(["", "", "", "", "", "", "", ""])  # Row with empty cells

        loader = TemplateLoader()
        checklist = loader.load_checklist_from_template(sample_template_csv)

        # Should still have same number of items (empty rows skipped)
        assert len(checklist.items) == 3

    def test_skip_section_headers(self, sample_template_csv):
        """Test that section headers (rows without item IDs) are skipped."""
        loader = TemplateLoader()
        checklist = loader.load_checklist_from_template(sample_template_csv)

        # "Abstract" row should be skipped (no numeric ID)
        abstract_item = checklist.get_item("Abstract")
        assert abstract_item is None

        # Only numeric IDs should be included
        assert checklist.get_item("1") is not None
        assert checklist.get_item("1.1") is not None
        assert checklist.get_item("2") is not None