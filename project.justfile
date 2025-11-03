## Add your own just recipes here. This is imported by the main justfile.

# Launch the Gradio web interface
[group('ui')]
ui PORT="7860":
  uv run streams-agent ui --port {{PORT}}

# Launch the Gradio web interface with public share link
[group('ui')]
ui-share PORT="7860":
  uv run streams-agent ui --port {{PORT}} --share

# Generate HTML output from the item/group analysis notebook
[group('notebooks')]
notebook-html:
  uv run papermill notebooks/item_group_analysis_extension.ipynb output/notebooks/item_group_analysis_extension_executed.ipynb --log-output --progress-bar
  uv run jupyter nbconvert output/notebooks/item_group_analysis_extension_executed.ipynb --to html --output item_group_analysis_extension_executed.html
  @echo "📊 Generated: output/notebooks/item_group_analysis_extension_executed.html"
