# STREAMS Agent Gradio Web Interface

A simple web interface for evaluating microbiome research papers against the STREAMS checklist.

## Features

- **PDF Upload & Evaluation**: Upload a research paper (PDF) and automatically evaluate it against the STREAMS checklist
- **Model Selection**: Choose between real Claude models or mock mode for testing
- **Chat Interface**: Ask questions about STREAMS guidelines and get expert guidance
- **Results Export**: Download evaluation results as JSON

## Quick Start

### Launch the UI

```bash
uv run streams-agent ui
```

The interface will be available at http://localhost:7860

### Launch with Custom Port

```bash
uv run streams-agent ui --port 8080
```

### Create Public Share Link

```bash
uv run streams-agent ui --share
```

This creates a temporary public URL that can be accessed from anywhere (useful for demos).

## Usage

### Tab 1: Evaluate Paper

1. **Upload PDF**: Click "Upload PDF Paper" and select your microbiome research paper
2. **Enter Paper ID**: Provide a unique identifier (e.g., `smith2024_gut_microbiome`)
3. **Enter Reviewer ID**: (Optional) Your identifier as reviewer (defaults to `gradio_user`)
4. **Select Model**:
   - `mock`: Fast testing mode with fake results (no API calls)
   - `claude-3-5-sonnet-20241022`: Best quality (default for real evaluations)
   - `claude-3-5-haiku-20241022`: Faster, lower cost
   - `claude-3-opus-20240229`: Highest quality, slower
5. **Click "Evaluate"**: Wait for results (mock is instant, real models take 30-60 seconds)
6. **View Results**: See summary statistics and detailed item-by-item assessment
7. **Download JSON**: (Optional) Export results for further analysis

### Tab 2: Chat

Ask questions about STREAMS guidelines, such as:
- "What is the STREAMS checklist?"
- "What should be reported in the abstract section?"
- "How do I improve compliance with methods reporting?"
- "What's the difference between Yes, Partial, and No ratings?"

## Mock Mode for Testing

The `mock` model is perfect for:
- **Testing the interface** without using API credits
- **Demonstrating the workflow** to colleagues
- **Debugging issues** without waiting for real API calls

Mock mode generates fake but realistic-looking assessments with alternating ratings (Yes, No, Partial, NA).

## Model Selection Guide

| Model | Best For | Speed | Cost | Quality |
|-------|----------|-------|------|---------|
| `mock` | Testing | Instant | Free | N/A |
| `claude-3-5-haiku-20241022` | Quick drafts | Fast | Low | Good |
| `claude-3-5-sonnet-20241022` | Production use | Medium | Medium | Excellent |
| `claude-3-opus-20240229` | Critical reviews | Slow | High | Best |

## Environment Variables

For real evaluations (not mock mode), you need:

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

Get your API key from https://console.anthropic.com/

## Example Workflow

1. Start with **mock mode** to test the interface:
   ```bash
   uv run streams-agent ui
   ```

2. Upload a PDF, enter a paper ID, keep "mock" selected, and click Evaluate

3. Review the interface and results format

4. Switch to **real model** (`claude-3-5-sonnet-20241022`) for actual evaluation

5. **Export JSON** for record-keeping or further analysis

## Troubleshooting

### Error: "ANTHROPIC_API_KEY not set"
- Set your API key: `export ANTHROPIC_API_KEY="sk-..."`
- Or use `mock` model for testing

### Gradio not found
- Run: `uv add gradio`

### Slow evaluation
- Use `claude-3-5-haiku-20241022` for faster results
- Or use `mock` for instant testing

## Command-Line Alternative

If you prefer CLI over web interface:

```bash
# Single paper
uv run streams-agent review paper.pdf template.csv --paper-id paper123 --output result.json

# Multiple papers
uv run streams-agent multi-review batch.csv template.csv --output-dir output/

# With mock model
uv run streams-agent review paper.pdf template.csv --paper-id test --model mock
```

## Architecture

- **Frontend**: Gradio (Python web framework)
- **Backend**: Pydantic-AI with Claude
- **PDF Processing**: Native Claude PDF support (no text extraction)
- **Models**: Anthropic Claude models via API

## Files

- `src/streams_agent/gradio_app.py` - Main Gradio interface
- `src/streams_agent/cli.py` - CLI commands including `ui`
- `src/streams_agent/review_engine.py` - Evaluation engine with mock support
- `src/streams_agent/template/streams.csv` - STREAMS checklist template
