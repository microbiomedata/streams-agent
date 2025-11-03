
# streams-agent

An AI agent system for evaluating microbiome research papers against the STREAMS (Standards for Technical Reporting in Environmental and host-Associated Microbiome Studies) checklist.

## Quick Start

### Single Paper Review

```bash
# Using Anthropic Claude Sonnet 4.5 (default, most capable)
export ANTHROPIC_API_KEY="your-api-key"
uv run streams-agent review paper.pdf src/streams_agent/template/streams.csv --paper-id "study123"

# Using Claude Haiku 4.5 (faster, more cost-effective)
export ANTHROPIC_API_KEY="your-api-key"
uv run streams-agent review paper.pdf src/streams_agent/template/streams.csv --paper-id "study123" \
  --model "claude-haiku-4-5-20251015"

# Using OpenAI GPT-5
export OPENAI_API_KEY="your-api-key"
uv run streams-agent review paper.pdf src/streams_agent/template/streams.csv --paper-id "study123" \
  --model "openai:gpt-5"

# Using CBORG proxy with Claude (LBNL)
export CBORG_API_KEY="your-api-key"
uv run streams-agent review paper.pdf src/streams_agent/template/streams.csv --paper-id "study123" \
  --model "cborg:anthropic/claude-sonnet"

# Using CBORG with free LBL-hosted Llama 4 Scout
export CBORG_API_KEY="your-api-key"
uv run streams-agent review paper.pdf src/streams_agent/template/streams.csv --paper-id "study123" \
  --model "cborg:lbl/cborg-chat:latest"

# Mock mode (no API calls, for testing)
uv run streams-agent review paper.pdf src/streams_agent/template/streams.csv --paper-id "study123" \
  --model "mock"
```

### Web Interface

Launch the interactive Gradio UI (no API key needed to start):

```bash
uv run streams-agent ui
```

The UI will prompt for the appropriate API key when you run an evaluation.

### Batch Review (Multiple Papers)

```bash
# Create a CSV with paper_id,pdf_path columns
cat > papers.csv << EOF
paper_id,pdf_path
study001,papers/study001.pdf
study002,papers/study002.pdf
EOF

# Review all papers
uv run streams-agent multi-review papers.csv src/streams_agent/template/streams.csv
```

See [EXAMPLE_USAGE.md](EXAMPLE_USAGE.md) for detailed usage instructions and [MODEL_CONFIGURATION.md](MODEL_CONFIGURATION.md) for model provider configuration.

## Documentation Website

[https://microbiomedata.github.io/streams-agent](https://microbiomedata.github.io/streams-agent)

## Repository Structure

* [docs/](docs/) - mkdocs-managed documentation
* [project/](project/) - project files (these files are auto-generated, do not edit)
* [src/](src/) - source files (edit these)
  * [streams_agent](src/streams_agent)
* [tests/](tests/) - Python tests
  * [data/](tests/data) - Example data

## Developer Tools

There are several pre-defined command-recipes available.
They are written for the command runner [just](https://github.com/casey/just/). To list all pre-defined commands, run `just` or `just --list`.

## Credits

This project uses the template [monarch-project-copier](https://github.com/monarch-initiative/monarch-project-copier)
