"""STREAMS review engine using pydantic-ai with native PDF support."""

import os
from pathlib import Path
from typing import Optional, Union
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic import BaseModel

from .models.checklist import Checklist, ChecklistAssessment, ItemAssessment, AssessmentRating
from .template.loader import TemplateLoader


class EvaluationContext(BaseModel):
    """Context passed to the evaluator agent."""
    checklist: Checklist
    paper_id: str
    evaluator_id: str


class StreamsReviewEngine:
    """STREAMS review engine using pydantic-ai with native PDF support.

    Uses Claude's native PDF processing capabilities for better performance
    and analysis quality compared to text extraction.

    Examples:
        >>> engine = StreamsReviewEngine()
        >>> assessment = engine.review_pdf("paper.pdf", "template.csv", "paper123", "ai_reviewer")
        >>> len(assessment.assessments) > 0
        True
    """

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", use_cborg: bool = False, provider: str = "anthropic"):
        """Initialize the review engine.

        Args:
            model: Model to use for review (use 'mock' for testing)
            use_cborg: Whether to use CBORG proxy for API access
            provider: Provider to use ('anthropic', 'openai', or 'mock')
        """
        self.is_mock = (model == "mock" or provider == "mock")
        self.provider = provider

        if self.is_mock:
            # Mock mode doesn't need real API setup
            self.model = "mock"
        elif use_cborg:
            # Validate CBORG configuration early
            cborg_api_key = os.environ.get("CBORG_API_KEY")
            if not cborg_api_key:
                raise ValueError(
                    "CBORG_API_KEY environment variable must be set when using CBORG proxy"
                )
            self.model = self._create_cborg_model(model, provider)
        elif provider == "openai":
            # Use OpenAI model directly
            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if not openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable must be set when using OpenAI models"
                )
            self.model = self._create_openai_model(model)
        else:
            # Default to Anthropic
            self.model = model
        self._agent = None
        self.loader = TemplateLoader()

    def _create_openai_model(self, model_name: str) -> OpenAIChatModel:
        """Create an OpenAI model.

        Args:
            model_name: OpenAI model name (e.g., "gpt-4o", "gpt-4o-mini")

        Returns:
            OpenAI model configured for direct OpenAI API access
        """
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        # API key validation is done in __init__, so we can assume it exists here

        return OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                api_key=openai_api_key
            ),
        )

    def _create_cborg_model(self, model_name: str, provider: str = "anthropic") -> OpenAIChatModel:
        """Create a model configured to use CBORG proxy.

        Args:
            model_name: Base model name
            provider: Underlying provider ('anthropic' or 'openai')

        Returns:
            Model configured for CBORG proxy
        """
        cborg_api_key = os.environ.get("CBORG_API_KEY")
        # API key validation is done in __init__, so we can assume it exists here

        return OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                base_url="https://api.cborg.lbl.gov",
                api_key=cborg_api_key
            ),
        )

    @property
    def agent(self) -> Agent:
        """Lazy-loaded agent property."""
        if self._agent is None:
            self._agent = Agent(
                model=self.model,
                output_type=list[ItemAssessment],
                deps_type=EvaluationContext,
                system_prompt="""You are a STREAMS checklist reviewer for microbiome research papers.

STREAMS (Standards for Technical Reporting in Environmental and host-Associated Microbiome Studies)
extends STORMS guidelines to environmental, non-human host, and synthetic microbiome studies.

Your task:
1. Read the provided research paper text carefully
2. Review each checklist item against the paper content
3. Rate each item as: Yes, No, NA (Not Applicable), or Partial
4. Provide specific comments with page/section references as well as extractd values

Rating Guidelines:
- Yes: Item is clearly addressed and well-documented
- No: Item is missing or inadequately addressed
- Partial: Item is partially addressed but incomplete
- NA: Item is not applicable to this study type

Be thorough but concise in your comments. Focus on factual presence/absence of information."""
            )
        return self._agent

    def load_pdf_content(self, pdf_path: Path | str) -> BinaryContent:
        """Load PDF file as binary content for native Claude processing.

        Args:
            pdf_path: Path to PDF file

        Returns:
            BinaryContent object for pydantic-ai
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        return BinaryContent(
            data=pdf_path.read_bytes(),
            media_type='application/pdf'
        )

    def _create_mock_assessment(
        self,
        checklist: Checklist,
        paper_id: str,
        reviewer_id: str
    ) -> ChecklistAssessment:
        """Create a mock assessment for testing purposes.

        Args:
            checklist: Checklist to assess against
            paper_id: Identifier for the paper
            reviewer_id: Identifier for the reviewer

        Returns:
            Mock checklist assessment with alternating ratings
        """
        mock_assessments = []
        ratings = [AssessmentRating.YES, AssessmentRating.NO, AssessmentRating.PARTIAL, AssessmentRating.NOT_APPLICABLE]

        for i, item in enumerate(checklist.items):
            # Alternate through ratings for variety
            rating = ratings[i % len(ratings)]

            # Generate mock comment based on rating
            comments_map = {
                AssessmentRating.YES: f"MOCK: Item {item.id} is present (see abstract/methods)",
                AssessmentRating.NO: f"MOCK: Item {item.id} is not found in the document",
                AssessmentRating.PARTIAL: f"MOCK: Item {item.id} is partially addressed but incomplete",
                AssessmentRating.NOT_APPLICABLE: f"MOCK: Item {item.id} is not applicable to this study"
            }

            mock_assessments.append(ItemAssessment(
                item_id=item.id,
                rating=rating,
                comments=comments_map[rating],
                confidence=0.95
            ))

        return ChecklistAssessment(
            checklist_name=checklist.name,
            checklist_version=checklist.version,
            paper_id=paper_id,
            evaluator_id=reviewer_id,
            assessments=mock_assessments,
            assessment_date=None
        )

    def review_pdf(
        self,
        pdf_path: Path | str,
        template_path: Path | str,
        paper_id: str,
        reviewer_id: str = "ai_reviewer"
    ) -> ChecklistAssessment:
        """Review a PDF against a STREAMS checklist template.

        Args:
            pdf_path: Path to the PDF file to review
            template_path: Path to the checklist template CSV
            paper_id: Identifier for the paper
            reviewer_id: Identifier for the reviewer

        Returns:
            Complete checklist assessment

        Examples:
            >>> engine = StreamsReviewEngine()
            >>> assessment = engine.review_pdf("paper.pdf", "streams.csv", "paper123")
            >>> assessment.paper_id
            'paper123'
        """
        # Load checklist from template
        checklist = self.loader.load_checklist_from_template(template_path)

        # If using mock mode, return mock assessment
        if self.is_mock:
            return self._create_mock_assessment(checklist, paper_id, reviewer_id)

        # Load PDF as binary content for native processing
        pdf_content = self.load_pdf_content(pdf_path)

        # Create review context
        context = EvaluationContext(
            checklist=checklist,
            paper_id=paper_id,
            evaluator_id=reviewer_id
        )

        # Format all checklist items for single-pass processing
        checklist_text = self._format_checklist_for_prompt(checklist)

        prompt_text = f"""Review this research paper against the complete STREAMS checklist ({len(checklist.items)} items).

CHECKLIST ITEMS TO REVIEW:
{checklist_text}

Please analyze the provided PDF document and provide a review assessment for each checklist item listed above."""

        # Run review in single pass with PDF content
        result = self.agent.run_sync([pdf_content, prompt_text], deps=context)

        # Create final assessment
        return ChecklistAssessment(
            checklist_name=checklist.name,
            checklist_version=checklist.version,
            paper_id=paper_id,
            evaluator_id=reviewer_id,
            assessments=result.output,
            assessment_date=None
        )

    def _format_checklist_for_prompt(self, checklist: Checklist) -> str:
        """Format checklist items for the prompt.

        Args:
            checklist: Checklist to format

        Returns:
            Formatted checklist text
        """
        lines = []
        for item in checklist.items:
            lines.append(f"ID: {item.id}")
            lines.append(f"Title: {item.title}")
            lines.append(f"Description: {item.description}")
            if item.examples:
                lines.append(f"Examples: {'; '.join(item.examples)}")
            lines.append("")
        return "\n".join(lines)