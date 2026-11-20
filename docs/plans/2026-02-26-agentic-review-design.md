# Agentic Review: Claude Agent SDK Rewrite

**Date:** 2026-02-26
**Status:** Approved

## Summary

Replace the pydantic-ai based review engine with a new implementation using the Anthropic Claude Agent SDK (`claude-agent-sdk`). The new agent works by reading a PDF and iteratively editing a CSV checklist file, leveraging Claude's built-in Read and Edit tools.

The existing pydantic-ai engine (`review_engine.py`) remains in place. The new code lives in `src/streams_agent/agentic_review/`.

## Design

### Package structure

```
src/streams_agent/agentic_review/
├── __init__.py          # exports run_review()
├── engine.py            # run_review() using claude-agent-sdk query()
├── csv_utils.py         # prepare blank CSV, parse completed CSV → ChecklistAssessment
├── system_prompt.md     # STREAMS review instructions (markdown)
└── user_prompt.md       # user prompt template with {pdf_path}, {csv_path} placeholders
```

### Flow

1. `run_review(pdf_path, template_path, paper_id, ...)` is the entry point
2. `csv_utils.prepare_workspace()` copies the template CSV into a temp dir with blank rating/comments columns
3. `engine.py` calls `query()` with:
   - System prompt loaded from `system_prompt.md`
   - User prompt from `user_prompt.md` with `{pdf_path}` and `{csv_path}` substituted
   - `allowed_tools=["Read", "Edit"]`
   - `permission_mode="bypassPermissions"`
4. Claude reads the PDF, reads the CSV, edits each row with rating and comments
5. `csv_utils.parse_completed_csv()` reads the filled CSV back into a `ChecklistAssessment`

### Prompts

Stored as markdown files in the package directory. Loaded at runtime via `importlib.resources`. Use `{variable}` placeholders filled with `.format()`.

### Auth

`ANTHROPIC_API_KEY` environment variable. The Agent SDK picks this up natively. No auth code needed.

### Data model reuse

The existing models are reused without modification:
- `ChecklistAssessment` / `ItemAssessment` (output)
- `Checklist` / `ChecklistItem` (input)
- `TemplateLoader` (for loading the checklist template)

### CLI

New `agentic-review` subcommand added to `cli.py`.

### Dependencies

Add `claude-agent-sdk` to pyproject.toml.

### Testing

- **Unit tests** for `csv_utils` (prepare + parse) and prompt loading — no API needed
- **Integration test** for `run_review()` — marked `@pytest.mark.integration`
