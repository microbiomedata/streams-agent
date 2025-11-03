"""CLI interface for streams-agent."""

import typer
from pathlib import Path
from typing_extensions import Annotated
from typing import Optional, Tuple
import json
import csv

from .review_engine import StreamsReviewEngine

app = typer.Typer(help="streams-agent: AI agent for reviewing microbiome research against STREAMS checklist.")


def _parse_model_spec(model_spec: str) -> Tuple[str, str, bool]:
    """Parse model specification into provider, model name, and use_cborg flag.

    Args:
        model_spec: Model specification in format "provider:model" or just "model"
                   CBORG models can use format "cborg:provider/model" or "cborg:model"

    Returns:
        Tuple of (model_name, provider, use_cborg)
    """
    if ":" in model_spec:
        # Split only on first colon to handle models like "cborg:lbl/cborg-chat:latest"
        parts = model_spec.split(":", 1)
        provider = parts[0]
        model_name = parts[1] if len(parts) > 1 else ""

        if provider == "cborg":
            # CBORG is a proxy, determine underlying provider from model name
            if model_name.startswith("openai/") or model_name.startswith("gpt-") or model_name.startswith("o3"):
                return (model_name, "openai", True)
            elif model_name.startswith("lbl/") or model_name.startswith("google/") or model_name.startswith("xai/"):
                # LBL-hosted and other CBORG-specific models - treat as anthropic-compatible
                return (model_name, "anthropic", True)
            else:
                # anthropic/ prefix or claude models default to anthropic
                return (model_name, "anthropic", True)
        elif provider == "openai":
            return (model_name, "openai", False)
        else:
            # Unknown provider, treat as Anthropic
            return (model_name, "anthropic", False)
    else:
        # No provider specified
        if model_spec == "mock":
            return ("mock", "mock", False)
        else:
            # Default to Anthropic
            return (model_spec, "anthropic", False)


@app.command()
def run(
    name: Annotated[str, typer.Option(help="Name of the person to greet")],
):
    typer.echo(f"Hello, {name}!")


@app.command()
def review(
    pdf_path: Annotated[Path, typer.Argument(help="Path to the PDF file to review")],
    template_path: Annotated[Path, typer.Argument(help="Path to the STREAMS checklist template CSV")],
    paper_id: Annotated[str, typer.Option(help="Identifier for the paper being reviewed")],
    reviewer_id: Annotated[str, typer.Option(help="Identifier for the reviewer")] = "ai_reviewer",
    output: Annotated[Optional[Path], typer.Option(help="Output file path (JSON format)")] = None,
    model: Annotated[str, typer.Option(help="Model to use (format: 'provider:model' or just 'model' for Anthropic)")] = "claude-sonnet-4-5-20250929",
    use_cborg: Annotated[bool, typer.Option("--use-cborg/--no-use-cborg", help="Use CBORG as a model proxy (LBNL account required)")] = False,
):
    """Review a PDF against a STREAMS checklist template using AI.

    Model specification format:
    - 'model_name' - Use Anthropic model (default)
    - 'openai:model_name' - Use OpenAI model directly
    - 'cborg:model_name' - Use CBORG proxy for the specified model
    - 'mock' - Use mock mode for testing (no API calls)

    Examples:
    - claude-sonnet-4-5-20250929 (Anthropic Claude Sonnet 4.5, default)
    - claude-haiku-4-5-20251015 (Anthropic Claude Haiku 4.5)
    - openai:gpt-5 (OpenAI GPT-5 direct)
    - openai:gpt-5-mini (OpenAI GPT-5 Mini)
    - cborg:anthropic/claude-sonnet (Claude via CBORG proxy)
    - cborg:gpt-5 (GPT-5 via CBORG proxy)
    - cborg:lbl/cborg-chat:latest (LBL-hosted free model via CBORG)
    """
    try:
        # Parse model specification
        model_name, provider, use_cborg_parsed = _parse_model_spec(model)

        # CLI --use-cborg flag overrides model spec
        if use_cborg:
            use_cborg_parsed = True

        engine = StreamsReviewEngine(model=model_name, use_cborg=use_cborg_parsed, provider=provider)

        if use_cborg_parsed:
            typer.echo(f"Using CBORG proxy at https://api.cborg.lbl.gov")
        elif provider == "openai":
            typer.echo(f"Using OpenAI model: {model_name}")
        else:
            typer.echo(f"Using Anthropic model: {model_name}")

        typer.echo(f"Reviewing {pdf_path} against {template_path}...")
        assessment = engine.review_pdf(pdf_path, template_path, paper_id, reviewer_id)

        # Output results
        if output:
            with open(output, 'w') as f:
                json.dump(assessment.model_dump(mode='json'), f, indent=2, default=str)
            typer.echo(f"Review saved to {output}")
        else:
            # Print summary to console
            total_items = len(assessment.assessments)
            completed_items = len([a for a in assessment.assessments if a.rating is not None])

            typer.echo(f"\nReview Complete!")
            typer.echo(f"Paper ID: {assessment.paper_id}")
            typer.echo(f"Checklist: {assessment.checklist_name} v{assessment.checklist_version}")
            typer.echo(f"Items reviewed: {completed_items}/{total_items}")
            typer.echo(f"Completion rate: {assessment.get_completion_rate():.1%}")

            # Show ratings summary
            ratings_count: dict[str, int] = {}
            for a in assessment.assessments:
                if a.rating:
                    ratings_count[a.rating.value] = ratings_count.get(a.rating.value, 0) + 1

            typer.echo("\nRatings Summary:")
            for rating, count in ratings_count.items():
                typer.echo(f"  {rating}: {count}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def multi_review(
    input_file: Annotated[Path, typer.Argument(help="CSV/TSV file with columns: paper_id, pdf_path")],
    template_path: Annotated[Path, typer.Argument(help="Path to the STREAMS checklist template CSV")],
    output_dir: Annotated[Path, typer.Option(help="Directory to save individual review JSON files")] = Path("output"),
    reviewer_id: Annotated[str, typer.Option(help="Identifier for the reviewer")] = "ai_reviewer",
    model: Annotated[str, typer.Option(help="Model to use (format: 'provider:model' or just 'model' for Anthropic)")] = "claude-sonnet-4-5-20250929",
    use_cborg: Annotated[bool, typer.Option("--use-cborg/--no-use-cborg", help="Use CBORG as a model proxy (LBNL account required)")] = False,
    delimiter: Annotated[str, typer.Option(help="Delimiter for input file (auto-detected from extension if not specified)")] = None,
):
    """Review multiple PDFs against a STREAMS checklist template using AI.

    The input file should be a CSV or TSV with at least two columns:
    - paper_id: Unique identifier for the paper
    - pdf_path: Path to the PDF file (can be relative or absolute)

    Additional columns are ignored.

    Example CSV:
        paper_id,pdf_path
        study001,papers/study001.pdf
        study002,papers/study002.pdf

    Example TSV:
        paper_id\tpdf_path
        study001\tpapers/study001.pdf
        study002\tpapers/study002.pdf
    """
    # Auto-detect delimiter if not specified
    if delimiter is None:
        if input_file.suffix.lower() == '.tsv':
            delimiter = '\t'
        else:
            delimiter = ','

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read input file
    try:
        with open(input_file, 'r') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            rows = list(reader)
    except Exception as e:
        typer.echo(f"Error reading input file: {e}", err=True)
        raise typer.Exit(1)

    # Validate required columns
    if not rows:
        typer.echo("Error: Input file is empty", err=True)
        raise typer.Exit(1)

    required_cols = {'paper_id', 'pdf_path'}
    available_cols = set(rows[0].keys())
    missing_cols = required_cols - available_cols

    if missing_cols:
        typer.echo(f"Error: Missing required columns: {missing_cols}", err=True)
        typer.echo(f"Available columns: {available_cols}", err=True)
        raise typer.Exit(1)

    # Initialize engine once for all reviews
    try:
        # Parse model specification
        model_name, provider, use_cborg_parsed = _parse_model_spec(model)

        # CLI --use-cborg flag overrides model spec
        if use_cborg:
            use_cborg_parsed = True

        engine = StreamsReviewEngine(model=model_name, use_cborg=use_cborg_parsed, provider=provider)

        if use_cborg_parsed:
            typer.echo(f"Using CBORG proxy at https://api.cborg.lbl.gov")
        elif provider == "openai":
            typer.echo(f"Using OpenAI model: {model_name}")
        else:
            typer.echo(f"Using Anthropic model: {model_name}")
    except Exception as e:
        typer.echo(f"Error initializing review engine: {e}", err=True)
        raise typer.Exit(1)

    # Process each paper
    total = len(rows)
    successful = 0
    failed = 0

    typer.echo(f"Processing {total} papers...")
    typer.echo(f"Template: {template_path}")
    typer.echo(f"Output directory: {output_dir}")
    typer.echo("")

    for i, row in enumerate(rows, 1):
        paper_id = row['paper_id']
        pdf_path = Path(row['pdf_path'])

        typer.echo(f"[{i}/{total}] Reviewing {paper_id} ({pdf_path.name})...")

        # Check if PDF exists
        if not pdf_path.exists():
            typer.echo(f"  ⚠ Warning: PDF not found: {pdf_path}", err=True)
            failed += 1
            continue

        try:
            # Review the paper
            assessment = engine.review_pdf(pdf_path, template_path, paper_id, reviewer_id)

            # Save to output directory
            output_file = output_dir / f"{paper_id}.json"
            with open(output_file, 'w') as f:
                json.dump(assessment.model_dump(mode='json'), f, indent=2, default=str)

            # Show quick summary
            completed = len([a for a in assessment.assessments if a.rating is not None])
            total_items = len(assessment.assessments)
            typer.echo(f"  ✓ Complete: {completed}/{total_items} items ({assessment.get_completion_rate():.1%})")
            typer.echo(f"  → Saved to: {output_file}")

            successful += 1

        except Exception as e:
            typer.echo(f"  ✗ Error: {e}", err=True)
            failed += 1

    # Final summary
    typer.echo("")
    typer.echo("=" * 50)
    typer.echo(f"Multi-review complete!")
    typer.echo(f"Total papers: {total}")
    typer.echo(f"Successful: {successful}")
    typer.echo(f"Failed: {failed}")
    typer.echo(f"Results saved to: {output_dir}")


@app.command()
def ui(
    share: Annotated[bool, typer.Option("--share/--no-share", help="Create a public share link")] = False,
    port: Annotated[int, typer.Option(help="Port to run the server on")] = 7860,
):
    """Launch the Gradio web interface for STREAMS Agent.

    This starts a web server with an interactive UI for:
    - Uploading and evaluating PDF papers against STREAMS checklist
    - Chatting about STREAMS guidelines and evaluation results

    The interface will be available at http://localhost:7860 (or the specified port).
    Use --share to create a public URL that can be accessed from anywhere.
    """
    try:
        from .gradio_app import launch

        typer.echo("🚀 Launching STREAMS Agent Web Interface...")
        typer.echo(f"📍 Server will run on port {port}")
        if share:
            typer.echo("🌐 Creating public share link...")
        typer.echo("")

        launch(share=share, server_port=port)

    except ImportError as e:
        typer.echo(f"Error: Could not import gradio_app. Make sure gradio is installed.", err=True)
        typer.echo(f"Run: uv add gradio", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error launching UI: {e}", err=True)
        raise typer.Exit(1)


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
