# STREAMS AI Reviewer - Example Usage

This document shows how to use the STREAMS AI reviewer that was implemented using pydantic-ai.

## Setup

The reviewer requires an Anthropic API key to run:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Basic Usage

### Single Paper Review

Review a research paper PDF against the STREAMS checklist:

```bash
# Basic review
uv run streams-agent review test_paper.pdf src/streams_agent/template/streams.csv --paper-id "microbiome_2024_study"

# Save results to JSON file
uv run streams-agent review test_paper.pdf src/streams_agent/template/streams.csv \
  --paper-id "microbiome_2024_study" \
  --output review_results.json

# Use different model
uv run streams-agent review test_paper.pdf src/streams_agent/template/streams.csv \
  --paper-id "microbiome_2024_study" \
  --model "claude-3-5-haiku" \
  --reviewer-id "haiku_reviewer"
```

### Batch Review (Multiple Papers)

Review multiple papers at once using the `multi-review` command:

```bash
# Create a CSV file with paper information
cat > papers.csv << EOF
paper_id,pdf_path
study001,papers/study001.pdf
study002,papers/study002.pdf
study003,papers/study003.pdf
EOF

# Run batch review
uv run streams-agent multi-review papers.csv src/streams_agent/template/streams.csv

# Customize output directory and model
uv run streams-agent multi-review papers.csv src/streams_agent/template/streams.csv \
  --output-dir batch_results \
  --model "claude-3-5-sonnet-20241022" \
  --reviewer-id "batch_reviewer"

# Use TSV format with custom delimiter
uv run streams-agent multi-review papers.tsv src/streams_agent/template/streams.csv \
  --delimiter $'\t'
```

The `multi-review` command:
- Accepts CSV or TSV files with `paper_id` and `pdf_path` columns
- Auto-detects delimiter based on file extension (.csv or .tsv)
- Creates one JSON output file per paper in the output directory
- Shows progress and summary statistics
- Continues processing even if some papers fail

## Test Data

We've included a real environmental microbiome research paper (`test_paper.pdf`) for testing:

- **Paper**: "The quest for environmental analytical microbiology: absolute quantitative microbiome using cellular internal standards"
- **Journal**: Microbiome (2025)
- **Authors**: Wang et al.
- **DOI**: https://doi.org/10.1186/s40168-024-02009-2

## What the Reviewer Does

1. **Extracts text** from the PDF using pymupdf
2. **Loads STREAMS checklist** from CSV template (67 items)
3. **Uses pydantic-ai agent** to review each checklist item against the paper
4. **Provides structured output** with ratings (Yes/No/Partial/NA) and comments
5. **Validates results** using existing Pydantic models

## Example Output

The reviewer produces a `ChecklistAssessment` with:

```json
{
  "checklist_name": "STREAMS",
  "checklist_version": "1.0",
  "paper_id": "microbiome_2024_study",
  "evaluator_id": "ai_evaluator",
  "assessments": [
    {
      "item_id": "1",
      "rating": "Yes",
      "comments": "Abstract is well-structured and includes background, methods, results, and conclusions"
    },
    {
      "item_id": "1.1",
      "rating": "Yes",
      "comments": "Study design clearly stated as comparative analysis using cellular internal standards"
    }
    // ... 65 more assessments
  ]
}
```

## Architecture

Simple, focused design inspired by Aurelian/Monarch:

- **Single agent** with one clear responsibility
- **Structured output** using existing Pydantic models
- **Type-safe** validation with automatic retries
- **Template compatible** with existing STREAMS CSV formats
- **Lazy initialization** - no API key needed until evaluation

## Files Created

- `src/streams_agent/review_engine.py` - Main review engine class
- `src/streams_agent/cli.py` - Updated CLI with review command
- `test_paper.pdf` - Example research paper for testing