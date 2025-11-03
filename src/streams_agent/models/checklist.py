"""Generic data models for checklists and assessments.

This module provides Pydantic models for representing checklists and their assessments
in a generic way that can be used for STREAMS or other evaluation frameworks.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field


class AssessmentRating(str, Enum):
    """Standard rating values for checklist assessments."""
    YES = "Yes"
    NO = "No"
    NOT_APPLICABLE = "NA"
    PARTIAL = "Partial"


class ChecklistItem(BaseModel):
    """A single item in a checklist.

    Examples:
        >>> item = ChecklistItem(
        ...     id="1.1",
        ...     title="Study design",
        ...     description="State study design in abstract.",
        ...     examples=["High-throughput sequencing was performed..."]
        ... )
        >>> item.id
        '1.1'
    """
    id: str = Field(..., description="Unique identifier for this checklist item")
    title: str = Field(..., description="Short descriptive title")
    description: str = Field(..., description="Detailed description of what should be evaluated")
    examples: List[str] = Field(default_factory=list, description="Example implementations")
    source: Optional[str] = Field(None, description="Source standard or guideline")
    additional_guidance: Optional[str] = Field(None, description="Additional implementation guidance")
    category: Optional[str] = Field(None, description="Category or section this item belongs to")

    def get_group_id(self, separator: str = ".") -> str:
        """Extract group ID from item ID using a separator.

        For STREAMS-style IDs like "1.1", "1.2", etc., the group would be "1".
        For flat IDs, returns the ID itself.

        Args:
            separator: Character used to separate group from sub-item

        Returns:
            Group identifier

        Examples:
            >>> item = ChecklistItem(id="1.1", title="Test", description="Test")
            >>> item.get_group_id()
            '1'
            >>> item2 = ChecklistItem(id="5", title="Test", description="Test")
            >>> item2.get_group_id()
            '5'
        """
        if separator in self.id:
            return self.id.split(separator)[0]
        return self.id

    def is_group_header(self, separator: str = ".") -> bool:
        """Check if this item is a group header (no sub-items).

        Args:
            separator: Character used to separate group from sub-item

        Returns:
            True if this is a group header item

        Examples:
            >>> item1 = ChecklistItem(id="1", title="Abstract", description="Test")
            >>> item1.is_group_header()
            True
            >>> item2 = ChecklistItem(id="1.1", title="Study design", description="Test")
            >>> item2.is_group_header()
            False
        """
        return separator not in self.id


class Checklist(BaseModel):
    """A complete checklist containing multiple items.

    Examples:
        >>> checklist = Checklist(
        ...     name="STREAMS",
        ...     version="1.0",
        ...     items=[
        ...         ChecklistItem(id="1", title="Abstract", description="Include abstract"),
        ...         ChecklistItem(id="1.1", title="Study design", description="State study design")
        ...     ]
        ... )
        >>> len(checklist.items)
        2
    """
    name: str = Field(..., description="Name of the checklist (e.g., 'STREAMS', 'CONSORT')")
    version: str = Field(..., description="Version of the checklist")
    description: Optional[str] = Field(None, description="Description of the checklist purpose")
    items: List[ChecklistItem] = Field(..., description="List of checklist items")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def get_item(self, item_id: str) -> Optional[ChecklistItem]:
        """Get a checklist item by its ID.

        Args:
            item_id: The ID of the item to retrieve

        Returns:
            The checklist item if found, None otherwise

        Examples:
            >>> checklist = Checklist(name="test", version="1.0", items=[
            ...     ChecklistItem(id="1", title="Test", description="Test item")
            ... ])
            >>> item = checklist.get_item("1")
            >>> item.title if item else None
            'Test'
        """
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_groups(self, separator: str = ".") -> Dict[str, List[ChecklistItem]]:
        """Group checklist items by their group ID.

        Args:
            separator: Character used to separate group from sub-item

        Returns:
            Dictionary mapping group IDs to lists of items

        Examples:
            >>> checklist = Checklist(name="test", version="1.0", items=[
            ...     ChecklistItem(id="1", title="Group 1", description="Header"),
            ...     ChecklistItem(id="1.1", title="Item 1.1", description="Sub-item"),
            ...     ChecklistItem(id="1.2", title="Item 1.2", description="Sub-item"),
            ...     ChecklistItem(id="2", title="Group 2", description="Header")
            ... ])
            >>> groups = checklist.get_groups()
            >>> len(groups["1"])
            3
        """
        groups: Dict[str, List[ChecklistItem]] = {}
        for item in self.items:
            group_id = item.get_group_id(separator)
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(item)
        return groups

    def get_group_items(self, group_id: str, separator: str = ".", include_header: bool = False) -> List[ChecklistItem]:
        """Get all items in a specific group.

        Args:
            group_id: The group ID to retrieve items for
            separator: Character used to separate group from sub-item
            include_header: Whether to include the group header item

        Returns:
            List of items in the specified group

        Examples:
            >>> checklist = Checklist(name="test", version="1.0", items=[
            ...     ChecklistItem(id="1", title="Abstract", description="Header"),
            ...     ChecklistItem(id="1.1", title="Study design", description="Sub-item"),
            ...     ChecklistItem(id="1.2", title="Sample info", description="Sub-item")
            ... ])
            >>> items = checklist.get_group_items("1", include_header=False)
            >>> len(items)
            2
        """
        group_items = []
        for item in self.items:
            if item.get_group_id(separator) == group_id:
                if include_header or not item.is_group_header(separator):
                    group_items.append(item)
        return group_items


class ItemAssessment(BaseModel):
    """Assessment of a single checklist item.

    Examples:
        >>> assessment = ItemAssessment(
        ...     item_id="1.1",
        ...     rating=AssessmentRating.YES,
        ...     comments="Found in abstract section; the value is 'foo'"
        ... )
        >>> assessment.rating
        <AssessmentRating.YES: 'Yes'>
    """
    item_id: str = Field(..., description="ID of the checklist item being assessed")
    rating: Optional[AssessmentRating] = Field(None, description="Rating for this item")
    comments: Optional[str] = Field(None, description="Comments or location information, plus information about the value if applicable")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence in rating (0-1)")


class ChecklistAssessment(BaseModel):
    """Complete assessment of a checklist by an evaluator.

    Examples:
        >>> assessment = ChecklistAssessment(
        ...     checklist_name="STREAMS",
        ...     checklist_version="1.0",
        ...     paper_id="paper123",
        ...     evaluator_id="reviewer1",
        ...     assessments=[
        ...         ItemAssessment(item_id="1", rating=AssessmentRating.YES)
        ...     ]
        ... )
        >>> assessment.paper_id
        'paper123'
    """
    checklist_name: str = Field(..., description="Name of the checklist used")
    checklist_version: str = Field(..., description="Version of the checklist used")
    paper_id: str = Field(..., description="Identifier for the paper being assessed")
    evaluator_id: str = Field(..., description="Identifier for the evaluator")
    assessments: List[ItemAssessment] = Field(..., description="Individual item assessments")
    assessment_date: Optional[datetime] = Field(None, description="When the assessment was completed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def get_assessment(self, item_id: str) -> Optional[ItemAssessment]:
        """Get the assessment for a specific item.

        Args:
            item_id: The ID of the item to get assessment for

        Returns:
            The item assessment if found, None otherwise

        Examples:
            >>> assessment = ChecklistAssessment(
            ...     checklist_name="test", checklist_version="1.0",
            ...     paper_id="p1", evaluator_id="e1",
            ...     assessments=[ItemAssessment(item_id="1", rating=AssessmentRating.YES)]
            ... )
            >>> item_assessment = assessment.get_assessment("1")
            >>> item_assessment.rating if item_assessment else None
            <AssessmentRating.YES: 'Yes'>
        """
        for assessment in self.assessments:
            if assessment.item_id == item_id:
                return assessment
        return None

    def get_completion_rate(self) -> float:
        """Calculate the completion rate of the assessment.

        Returns:
            Fraction of items that have been rated (0.0 to 1.0)

        Examples:
            >>> assessment = ChecklistAssessment(
            ...     checklist_name="test", checklist_version="1.0",
            ...     paper_id="p1", evaluator_id="e1",
            ...     assessments=[
            ...         ItemAssessment(item_id="1", rating=AssessmentRating.YES),
            ...         ItemAssessment(item_id="2", rating=None)
            ...     ]
            ... )
            >>> assessment.get_completion_rate()
            0.5
        """
        if not self.assessments:
            return 0.0

        rated_count = sum(1 for a in self.assessments if a.rating is not None)
        return rated_count / len(self.assessments)

    def check_against_checklist(self, checklist: "Checklist") -> Dict[str, Any]:
        """Check this assessment against the source checklist to determine coverage and completion.

        This method compares the assessment against the source checklist to provide detailed
        information about what has been assessed and what may be missing.

        Args:
            checklist: The source checklist to check against

        Returns:
            Dictionary containing:
                - proportion_completed: Fraction of checklist items that have been assessed (0.0-1.0)
                - total_items: Total number of items in the source checklist
                - assessed_items: Number of items that have been assessed with a rating
                - missing_items: List of item IDs from the checklist that lack assessments
                - extra_items: List of item IDs in the assessment not found in the checklist
                - unrated_items: List of item IDs that have assessments but no rating

        Examples:
            >>> checklist = Checklist(name="test", version="1.0", items=[
            ...     ChecklistItem(id="1", title="Item 1", description="First item"),
            ...     ChecklistItem(id="2", title="Item 2", description="Second item"),
            ...     ChecklistItem(id="3", title="Item 3", description="Third item")
            ... ])
            >>> assessment = ChecklistAssessment(
            ...     checklist_name="test", checklist_version="1.0",
            ...     paper_id="p1", evaluator_id="e1",
            ...     assessments=[
            ...         ItemAssessment(item_id="1", rating=AssessmentRating.YES),
            ...         ItemAssessment(item_id="2", rating=AssessmentRating.NO),
            ...         ItemAssessment(item_id="4", rating=AssessmentRating.YES)
            ...     ]
            ... )
            >>> result = assessment.check_against_checklist(checklist)
            >>> result["proportion_completed"]
            0.6666666666666666
            >>> result["total_items"]
            3
            >>> result["assessed_items"]
            2
            >>> result["missing_items"]
            ['3']
            >>> result["extra_items"]
            ['4']
        """
        checklist_item_ids = {item.id for item in checklist.items}
        assessment_map = {a.item_id: a for a in self.assessments}

        # Find items with ratings
        assessed_items = [
            item_id for item_id, assessment in assessment_map.items()
            if item_id in checklist_item_ids and assessment.rating is not None
        ]

        # Find missing items (in checklist but not assessed or not rated)
        missing_items = [
            item_id for item_id in checklist_item_ids
            if item_id not in assessment_map or assessment_map[item_id].rating is None
        ]

        # Find extra items (in assessment but not in checklist)
        extra_items = [
            item_id for item_id in assessment_map.keys()
            if item_id not in checklist_item_ids
        ]

        # Find items that have assessments but no rating
        unrated_items = [
            item_id for item_id in checklist_item_ids
            if item_id in assessment_map and assessment_map[item_id].rating is None
        ]

        total_items = len(checklist.items)
        proportion_completed = len(assessed_items) / total_items if total_items > 0 else 0.0

        return {
            "proportion_completed": proportion_completed,
            "total_items": total_items,
            "assessed_items": len(assessed_items),
            "missing_items": missing_items,
            "extra_items": extra_items,
            "unrated_items": unrated_items,
        }