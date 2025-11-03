"""Tests for checklist data models."""

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
    """Create a sample checklist for testing."""
    return Checklist(
        name="test_checklist",
        version="1.0",
        items=[
            ChecklistItem(id="1", title="Item 1", description="First item"),
            ChecklistItem(id="2", title="Item 2", description="Second item"),
            ChecklistItem(id="3", title="Item 3", description="Third item"),
            ChecklistItem(id="4", title="Item 4", description="Fourth item"),
        ],
    )


@pytest.fixture
def sample_assessment():
    """Create a sample assessment for testing."""
    return ChecklistAssessment(
        checklist_name="test_checklist",
        checklist_version="1.0",
        paper_id="paper123",
        evaluator_id="evaluator1",
        assessments=[
            ItemAssessment(item_id="1", rating=AssessmentRating.YES, comments="Found"),
            ItemAssessment(item_id="2", rating=AssessmentRating.NO, comments="Missing"),
            ItemAssessment(item_id="3", rating=None, comments="Not yet reviewed"),
        ],
    )


def test_check_against_checklist_full_coverage(sample_checklist):
    """Test check_against_checklist with complete coverage."""
    assessment = ChecklistAssessment(
        checklist_name="test_checklist",
        checklist_version="1.0",
        paper_id="paper123",
        evaluator_id="evaluator1",
        assessments=[
            ItemAssessment(item_id="1", rating=AssessmentRating.YES),
            ItemAssessment(item_id="2", rating=AssessmentRating.NO),
            ItemAssessment(item_id="3", rating=AssessmentRating.PARTIAL),
            ItemAssessment(item_id="4", rating=AssessmentRating.NOT_APPLICABLE),
        ],
    )

    result = assessment.check_against_checklist(sample_checklist)

    assert result["proportion_completed"] == 1.0
    assert result["total_items"] == 4
    assert result["assessed_items"] == 4
    assert result["missing_items"] == []
    assert result["extra_items"] == []
    assert result["unrated_items"] == []


def test_check_against_checklist_partial_coverage(sample_checklist, sample_assessment):
    """Test check_against_checklist with partial coverage."""
    result = sample_assessment.check_against_checklist(sample_checklist)

    assert result["proportion_completed"] == 0.5  # 2 out of 4 items rated
    assert result["total_items"] == 4
    assert result["assessed_items"] == 2
    assert "3" in result["missing_items"]  # Has assessment but no rating
    assert "4" in result["missing_items"]  # No assessment at all
    assert result["extra_items"] == []
    assert result["unrated_items"] == ["3"]


def test_check_against_checklist_with_extra_items(sample_checklist):
    """Test check_against_checklist when assessment has extra items."""
    assessment = ChecklistAssessment(
        checklist_name="test_checklist",
        checklist_version="1.0",
        paper_id="paper123",
        evaluator_id="evaluator1",
        assessments=[
            ItemAssessment(item_id="1", rating=AssessmentRating.YES),
            ItemAssessment(item_id="2", rating=AssessmentRating.NO),
            ItemAssessment(item_id="5", rating=AssessmentRating.YES),  # Extra item
            ItemAssessment(item_id="6", rating=AssessmentRating.NO),  # Extra item
        ],
    )

    result = assessment.check_against_checklist(sample_checklist)

    assert result["proportion_completed"] == 0.5  # 2 out of 4 checklist items
    assert result["total_items"] == 4
    assert result["assessed_items"] == 2
    assert set(result["missing_items"]) == {"3", "4"}
    assert set(result["extra_items"]) == {"5", "6"}


def test_check_against_checklist_empty_assessment(sample_checklist):
    """Test check_against_checklist with no assessments."""
    assessment = ChecklistAssessment(
        checklist_name="test_checklist",
        checklist_version="1.0",
        paper_id="paper123",
        evaluator_id="evaluator1",
        assessments=[],
    )

    result = assessment.check_against_checklist(sample_checklist)

    assert result["proportion_completed"] == 0.0
    assert result["total_items"] == 4
    assert result["assessed_items"] == 0
    assert set(result["missing_items"]) == {"1", "2", "3", "4"}
    assert result["extra_items"] == []


def test_check_against_checklist_empty_checklist():
    """Test check_against_checklist with an empty checklist."""
    empty_checklist = Checklist(
        name="empty",
        version="1.0",
        items=[],
    )

    assessment = ChecklistAssessment(
        checklist_name="empty",
        checklist_version="1.0",
        paper_id="paper123",
        evaluator_id="evaluator1",
        assessments=[
            ItemAssessment(item_id="1", rating=AssessmentRating.YES),
        ],
    )

    result = assessment.check_against_checklist(empty_checklist)

    assert result["proportion_completed"] == 0.0
    assert result["total_items"] == 0
    assert result["assessed_items"] == 0
    assert result["missing_items"] == []
    assert result["extra_items"] == ["1"]


@pytest.mark.parametrize(
    "ratings,expected_proportion",
    [
        ([AssessmentRating.YES, AssessmentRating.NO, AssessmentRating.PARTIAL], 0.75),
        ([AssessmentRating.YES, AssessmentRating.NO], 0.5),
        ([AssessmentRating.YES], 0.25),
        ([], 0.0),
    ],
)
def test_check_against_checklist_various_proportions(
    sample_checklist, ratings, expected_proportion
):
    """Test various completion proportions using parametrize."""
    assessments = [
        ItemAssessment(item_id=str(i + 1), rating=rating)
        for i, rating in enumerate(ratings)
    ]

    assessment = ChecklistAssessment(
        checklist_name="test_checklist",
        checklist_version="1.0",
        paper_id="paper123",
        evaluator_id="evaluator1",
        assessments=assessments,
    )

    result = assessment.check_against_checklist(sample_checklist)
    assert result["proportion_completed"] == expected_proportion


def test_check_against_checklist_all_unrated(sample_checklist):
    """Test when all assessments exist but none have ratings."""
    assessment = ChecklistAssessment(
        checklist_name="test_checklist",
        checklist_version="1.0",
        paper_id="paper123",
        evaluator_id="evaluator1",
        assessments=[
            ItemAssessment(item_id="1", rating=None),
            ItemAssessment(item_id="2", rating=None),
            ItemAssessment(item_id="3", rating=None),
            ItemAssessment(item_id="4", rating=None),
        ],
    )

    result = assessment.check_against_checklist(sample_checklist)

    assert result["proportion_completed"] == 0.0
    assert result["assessed_items"] == 0
    assert set(result["unrated_items"]) == {"1", "2", "3", "4"}
    assert set(result["missing_items"]) == {"1", "2", "3", "4"}