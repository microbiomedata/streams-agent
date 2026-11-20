# Model Configuration Guide

This guide explains how to configure and use different AI models and providers with STREAMS Agent.

## Overview

STREAMS Agent supports multiple AI providers:
- **Anthropic** (default) - Claude models via direct API
- **OpenAI** - GPT models via direct API
- **CBORG** - Proxy service for both Anthropic and OpenAI models (LBNL)
- **Mock** - Testing mode without API calls

## Model Specification Format

Models are specified using the format: `provider:model_name`

- If no provider is specified, Anthropic is assumed
- CBORG models can use `cborg:provider/model` format (e.g., `cborg:anthropic/claude-sonnet`)
- Examples:
  - `claude-sonnet-4-5-20250929` (Anthropic Claude Sonnet 4.5, default)
  - `claude-haiku-4-5-20251015` (Anthropic Claude Haiku 4.5)
  - `openai:gpt-5` (OpenAI GPT-5 direct)
  - `openai:gpt-5-mini` (OpenAI GPT-5 Mini)
  - `openai:o3-mini` (OpenAI o3-mini reasoning model)
  - `cborg:anthropic/claude-sonnet` (Claude via CBORG proxy)
  - `cborg:gpt-5` (GPT-5 via CBORG proxy)
  - `cborg:lbl/cborg-chat:latest` (LBL-hosted free Llama 4 Scout via CBORG)
  - `cborg:lbl/cborg-coder` (LBL-hosted free coding model via CBORG)
  - `mock` (testing mode)

## CLI Usage

### Basic Examples

```bash
# Use default Anthropic model (Claude Sonnet 4.5)
export ANTHROPIC_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "study1"

# Use Claude Haiku 4.5 (faster, cheaper)
export ANTHROPIC_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "study1" \
  --model "claude-haiku-4-5-20251015"

# Use OpenAI GPT-5
export OPENAI_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "study1" \
  --model "openai:gpt-5"

# Use CBORG proxy with Claude (requires LBNL account)
export CBORG_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "study1" \
  --model "cborg:anthropic/claude-sonnet"

# Use CBORG with LBL-hosted free model (Llama 4 Scout)
export CBORG_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "study1" \
  --model "cborg:lbl/cborg-chat:latest"

# Use mock mode (no API calls, for testing)
uv run streams-agent review paper.pdf template.csv --paper-id "study1" \
  --model "mock"
```

### Legacy --use-cborg Flag

The `--use-cborg` flag is still supported for backward compatibility:

```bash
export CBORG_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "study1" \
  --use-cborg
```

This is equivalent to using `--model "cborg:claude-sonnet-4-5-20250929"`.

## Gradio UI Configuration

### Default Models

The Gradio UI comes with these pre-configured models:
- `mock` - Testing mode (no API calls)
- `claude-sonnet-4-5-20250929` - Anthropic Claude Sonnet 4.5 (default, most capable)
- `claude-haiku-4-5-20251015` - Anthropic Claude Haiku 4.5 (fast, cost-effective)
- `claude-sonnet-4-20250514` - Anthropic Claude Sonnet 4
- `openai:gpt-5` - OpenAI GPT-5 (latest)
- `openai:gpt-5-mini` - OpenAI GPT-5 Mini
- `openai:o3-mini` - OpenAI o3-mini (reasoning model)
- `cborg:anthropic/claude-sonnet` - Claude Sonnet via CBORG proxy
- `cborg:anthropic/claude-haiku` - Claude Haiku via CBORG proxy
- `cborg:gpt-5` - GPT-5 via CBORG proxy
- `cborg:gpt-5-mini` - GPT-5 Mini via CBORG proxy
- `cborg:lbl/cborg-chat:latest` - LBL-hosted Llama 4 Scout (free via CBORG)
- `cborg:lbl/cborg-coder` - LBL-hosted coding model (free via CBORG)

### Custom Model List

You can customize the available models using the `STREAMS_AGENT_MODELS` environment variable:

```bash
# Set custom model list (comma-separated)
export STREAMS_AGENT_MODELS="mock,claude-sonnet-4-5-20250929,openai:gpt-5,cborg:lbl/cborg-chat:latest"

# Launch the UI
uv run streams-agent ui
```

### Launching the UI

The UI no longer requires API keys to start - they're only needed when you actually run an evaluation:

```bash
# Launch without API keys set
uv run streams-agent ui

# Or with a custom port
uv run streams-agent ui --port 8080

# Create a public share link
uv run streams-agent ui --share
```

When you select a model and click "Evaluate", the appropriate API key will be checked:
- Anthropic models → `ANTHROPIC_API_KEY`
- OpenAI models → `OPENAI_API_KEY`
- CBORG models → `CBORG_API_KEY`
- Mock mode → No API key needed

## API Key Setup

### Anthropic (Default)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Get your key from: https://console.anthropic.com/

### OpenAI

```bash
export OPENAI_API_KEY="sk-..."
```

Get your key from: https://platform.openai.com/api-keys

### CBORG (LBNL Proxy)

```bash
export CBORG_API_KEY="your-cborg-key"
```

CBORG is a proxy service available to LBNL researchers. It provides access to multiple AI models through a single endpoint.

More info: https://api.cborg.lbl.gov

## Batch Processing

The `multi-review` command also supports all model providers:

```bash
# Create input file
cat > papers.csv << EOF
paper_id,pdf_path
study001,papers/study001.pdf
study002,papers/study002.pdf
EOF

# Use OpenAI for batch processing
export OPENAI_API_KEY="your-key"
uv run streams-agent multi-review papers.csv template.csv \
  --model "openai:gpt-5-mini" \
  --output-dir results/

# Use Claude Haiku for fast, cost-effective batch processing
export ANTHROPIC_API_KEY="your-key"
uv run streams-agent multi-review papers.csv template.csv \
  --model "claude-haiku-4-5-20251015" \
  --output-dir results/

# Use CBORG with free LBL-hosted model
export CBORG_API_KEY="your-key"
uv run streams-agent multi-review papers.csv template.csv \
  --model "cborg:lbl/cborg-chat:latest" \
  --output-dir results/
```

## Troubleshooting

### "API key not set" Error

If you see an error about missing API keys, make sure:
1. The correct environment variable is set for your chosen provider
2. The key is valid and not expired
3. You've exported the variable in your current shell session

```bash
# Check which variables are set
env | grep -E "ANTHROPIC_API_KEY|OPENAI_API_KEY|CBORG_API_KEY"
```

### UI Won't Start

The UI should now start without any API keys. If it doesn't:
1. Check that gradio is installed: `uv add gradio`
2. Look for Python import errors in the output
3. Make sure you're in the correct directory

### Model Not Available in UI

To add a custom model to the UI dropdown:
1. Set the `STREAMS_AGENT_MODELS` environment variable
2. Use comma-separated format: `provider:model,provider:model`
3. Restart the UI

## Examples

### Research Workflow with Multiple Providers

```bash
# Quick test with mock mode
uv run streams-agent review paper.pdf template.csv --paper-id "test" \
  --model "mock" --output test-mock.json

# Full evaluation with Claude Sonnet 4.5 (most capable)
export ANTHROPIC_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "test" \
  --model "claude-sonnet-4-5-20250929" --output test-sonnet.json

# Compare with GPT-5
export OPENAI_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "test" \
  --model "openai:gpt-5" --output test-gpt5.json

# Fast evaluation with Claude Haiku 4.5
export ANTHROPIC_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "test" \
  --model "claude-haiku-4-5-20251015" --output test-haiku.json

# Use CBORG with free LBL-hosted model
export CBORG_API_KEY="your-key"
uv run streams-agent review paper.pdf template.csv --paper-id "test" \
  --model "cborg:lbl/cborg-chat:latest" --output test-cborg.json
```

### Setting Up for Interactive Use

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# STREAMS Agent API keys
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export CBORG_API_KEY="..."

# Custom models for UI
export STREAMS_AGENT_MODELS="mock,claude-sonnet-4-5-20250929,claude-haiku-4-5-20251015,openai:gpt-5,cborg:lbl/cborg-chat:latest"
```

Then the UI will always have your preferred models available:

```bash
uv run streams-agent ui
```
