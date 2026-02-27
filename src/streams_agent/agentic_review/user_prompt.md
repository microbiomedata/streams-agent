Review the research paper at `{pdf_path}` against the STREAMS checklist.

The checklist is at `{checklist_path}`. It is a YAML file with one entry per checklist item. Each entry has `id`, `title`, `rating`, and `comments` fields. Fill in `rating` and `comments` for every item.

## Workflow

1. **Read** the PDF to understand the paper fully
2. **Read** the checklist YAML to see all items
3. **Write** the entire completed checklist in one shot — every item must have a `rating` and `comments`

Use the Write tool to write the complete YAML file with all items rated. For example, the output file should look like:

```yaml
- id: '1'
  title: Study design
  rating: 'Yes'
  comments: Cross-sectional amplicon study described in abstract paragraph 1
- id: '1.1'
  title: Environment or host
  rating: 'Yes'
  comments: Soil environment specified in Section 2.1
- id: '1.2'
  title: Sample type
  rating: 'Partial'
  comments: Sample type mentioned but collection method unclear (p.3)
```

Every item must have a valid rating (`Yes`, `No`, `NA`, or `Partial`). A validation hook will automatically check your output and give you feedback if anything needs fixing.
