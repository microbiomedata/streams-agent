Review the research paper at `{pdf_path}` against the STREAMS checklist.

The checklist is at `{checklist_path}`. It is a YAML file with one entry per checklist item. Each entry has `id`, `title`, `rating`, and `comments` fields. Fill in `rating` and `comments` for every item.

For example, to rate item 1.1, change:

```yaml
- id: '1.1'
  title: Study design
  rating: null
  comments: null
```

to:

```yaml
- id: '1.1'
  title: Study design
  rating: 'Yes'
  comments: Described in abstract paragraph 1 as a cross-sectional amplicon study
```

Work through all items. When done, every item should have a rating.
