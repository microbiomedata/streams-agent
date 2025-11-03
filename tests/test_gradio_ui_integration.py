"""Tests for Gradio UI integration with check_against_checklist.

These tests verify that the check_against_checklist functionality
integrates properly with the evaluation display logic.
"""

import pytest
from streams_agent.models.checklist import (
    Checklist,
    ChecklistItem,
    ChecklistAssessment,
    ItemAssessment,
    AssessmentRating,
)


@pytest.fixture
def sample_checklist():
    """Create a sample checklist."""
    return Checklist(
        name="STREAMS",
        version="1.0",
        items=[
            ChecklistItem(id="1", title="Abstract", description="Abstract section"),
            ChecklistItem(id="1.1", title="Study design", description="State study design"),
            ChecklistItem(id="1.2", title="Sample info", description="Describe samples"),
            ChecklistItem(id="2", title="Introduction", description="Introduction section"),
            ChecklistItem(id="2.1", title="Background", description="Provide background"),
        ],
    )


def test_assessment_with_missing_items_has_warning(sample_checklist):
    """Test that an assessment with missing items is properly detected."""
    assessment = ChecklistAssessment(
        checklist_name="STREAMS",
        checklist_version="1.0",
        paper_id="test_paper",
        evaluator_id="test_reviewer",
        assessments=[
            ItemAssessment(item_id="1", rating=AssessmentRating.YES, comments="Found"),
            ItemAssessment(item_id="1.1", rating=AssessmentRating.NO, comments="Missing"),
            # Missing items: 1.2, 2, 2.1
        ],
    )

    result = assessment.check_against_checklist(sample_checklist)

    # Should detect missing items
    assert result["proportion_completed"] == 0.4  # 2 of 5
    assert len(result["missing_items"]) == 3
    assert "1.2" in result["missing_items"]
    assert "2" in result["missing_items"]
    assert "2.1" in result["missing_items"]


def test_complete_assessment_has_no_warnings(sample_checklist):
    """Test that a complete assessment has no missing items."""
    assessment = ChecklistAssessment(
        checklist_name="STREAMS",
        checklist_version="1.0",
        paper_id="test_paper",
        evaluator_id="test_reviewer",
        assessments=[
            ItemAssessment(item_id="1", rating=AssessmentRating.YES),
            ItemAssessment(item_id="1.1", rating=AssessmentRating.YES),
            ItemAssessment(item_id="1.2", rating=AssessmentRating.PARTIAL),
            ItemAssessment(item_id="2", rating=AssessmentRating.YES),
            ItemAssessment(item_id="2.1", rating=AssessmentRating.NOT_APPLICABLE),
        ],
    )

    result = assessment.check_against_checklist(sample_checklist)

    # Should have complete coverage
    assert result["proportion_completed"] == 1.0
    assert len(result["missing_items"]) == 0
    assert len(result["extra_items"]) == 0


def test_assessment_with_extra_items_detected(sample_checklist):
    """Test that extra items not in the checklist are detected."""
    assessment = ChecklistAssessment(
        checklist_name="STREAMS",
        checklist_version="1.0",
        paper_id="test_paper",
        evaluator_id="test_reviewer",
        assessments=[
            ItemAssessment(item_id="1", rating=AssessmentRating.YES),
            ItemAssessment(item_id="3.1", rating=AssessmentRating.YES),  # Extra item
            ItemAssessment(item_id="99", rating=AssessmentRating.NO),  # Extra item
        ],
    )

    result = assessment.check_against_checklist(sample_checklist)

    # Should detect extra items
    assert len(result["extra_items"]) == 2
    assert "3.1" in result["extra_items"]
    assert "99" in result["extra_items"]


def test_ui_displays_correct_coverage_percentage(sample_checklist):
    """Test that coverage percentage calculation is correct for UI display."""
    # The checklist has items: 1, 1.1, 1.2, 2, 2.1
    all_item_ids = ["1", "1.1", "1.2", "2", "2.1"]

    test_cases = [
        ([], 0.0),  # No items assessed
        (["1"], 0.2),  # 1 of 5 items
        (["1", "1.1"], 0.4),  # 2 of 5 items
        (["1", "1.1", "1.2"], 0.6),  # 3 of 5 items
        (all_item_ids, 1.0),  # All items assessed
    ]

    for item_ids, expected_proportion in test_cases:
        assessments = [
            ItemAssessment(item_id=item_id, rating=AssessmentRating.YES)
            for item_id in item_ids
        ]

        assessment = ChecklistAssessment(
            checklist_name="STREAMS",
            checklist_version="1.0",
            paper_id="test_paper",
            evaluator_id="test_reviewer",
            assessments=assessments,
        )

        result = assessment.check_against_checklist(sample_checklist)
        assert result["proportion_completed"] == pytest.approx(expected_proportion)
        assert result["assessed_items"] == len(item_ids)
        assert result["total_items"] == 5


def test_unrated_items_are_tracked(sample_checklist):
    """Test that items with assessments but no ratings are properly tracked."""
    assessment = ChecklistAssessment(
        checklist_name="STREAMS",
        checklist_version="1.0",
        paper_id="test_paper",
        evaluator_id="test_reviewer",
        assessments=[
            ItemAssessment(item_id="1", rating=AssessmentRating.YES),
            ItemAssessment(item_id="1.1", rating=None, comments="Not yet reviewed"),
            ItemAssessment(item_id="1.2", rating=None, comments="Pending"),
        ],
    )

    result = assessment.check_against_checklist(sample_checklist)

    # Should track unrated items
    assert len(result["unrated_items"]) == 2
    assert "1.1" in result["unrated_items"]
    assert "1.2" in result["unrated_items"]

    # Unrated items should also be in missing_items
    assert "1.1" in result["missing_items"]
    assert "1.2" in result["missing_items"]
