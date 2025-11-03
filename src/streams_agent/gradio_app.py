"""Gradio web interface for STREAMS Agent.

This module provides a simple web UI for:
- Uploading and evaluating PDF papers against STREAMS checklist
- Chatting about STREAMS guidelines and evaluation results
"""

from pathlib import Path
from typing import Optional, Tuple
import json
from datetime import datetime

import gradio as gr
from pydantic_ai import Agent

from streams_agent.review_engine import StreamsReviewEngine
from streams_agent.template.loader import TemplateLoader
from streams_agent.models.checklist import ChecklistAssessment


# Initialize components
TEMPLATE_PATH = Path(__file__).parent / "template" / "streams.csv"
template_loader = TemplateLoader()

# Load checklist for reference
checklist = template_loader.load_checklist_from_template(str(TEMPLATE_PATH))

# Available models - configurable list
# Format: "provider:model_name" or just "model_name" for Anthropic
DEFAULT_MODELS = [
    "mock",
    # Anthropic Claude models (latest)
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251015",
    "claude-sonnet-4-20250514",
    # OpenAI GPT models (latest)
    "openai:gpt-5",
    "openai:gpt-5-mini",
    "openai:o3-mini",
    # CBORG proxy - Anthropic models
    "cborg:anthropic/claude-sonnet",
    "cborg:anthropic/claude-haiku",
    # CBORG proxy - OpenAI models
    "cborg:gpt-5",
    "cborg:gpt-5-mini",
    # CBORG proxy - LBL-hosted free models
    "cborg:lbl/cborg-chat:latest",
    "cborg:lbl/cborg-coder",
]

# Load custom models from environment variable if set
# Format: STREAMS_AGENT_MODELS="provider:model1,provider:model2,model3"
import os
_custom_models = os.environ.get("STREAMS_AGENT_MODELS", "").strip()
AVAILABLE_MODELS = _custom_models.split(",") if _custom_models else DEFAULT_MODELS

# Chat agent for STREAMS guidance - lazy initialization to avoid requiring API key on startup
_chat_agent = None

def get_chat_agent() -> Agent:
    """Get or create the chat agent (lazy initialization)."""
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = Agent(
            "claude-sonnet-4-5-20250929",
            system_prompt=f"""You are a helpful assistant expert in the STREAMS (Standards for Technical Reporting
in Environmental and host-Associated Microbiome Studies) checklist.

You help researchers understand STREAMS requirements, interpret evaluation results, and improve their
manuscript compliance with reporting standards.

The STREAMS checklist has {len(checklist.items)} items organized into sections covering abstract,
introduction, methods, results, and discussion. Each item specifies required reporting elements for
microbiome research papers.

Be concise, helpful, and reference specific checklist items when relevant.""",
        )
    return _chat_agent


def parse_model_spec(model_spec: str) -> Tuple[str, str, bool]:
    """Parse model specification into provider, model name, and use_cborg flag.

    Args:
        model_spec: Model specification in format "provider:model" or just "model"
                   Supported providers: "openai", "cborg", or none (Anthropic default)
                   CBORG models can use format "cborg:provider/model" or "cborg:model"

    Returns:
        Tuple of (model_name, provider, use_cborg)

    Examples:
        >>> parse_model_spec("claude-sonnet-4-5-20250929")
        ('claude-sonnet-4-5-20250929', 'anthropic', False)
        >>> parse_model_spec("openai:gpt-5")
        ('gpt-5', 'openai', False)
        >>> parse_model_spec("cborg:anthropic/claude-sonnet")
        ('anthropic/claude-sonnet', 'anthropic', True)
        >>> parse_model_spec("cborg:gpt-5")
        ('gpt-5', 'openai', True)
        >>> parse_model_spec("cborg:lbl/cborg-chat:latest")
        ('lbl/cborg-chat:latest', 'anthropic', True)
        >>> parse_model_spec("mock")
        ('mock', 'mock', False)
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


def evaluate_pdf(
    pdf_file,
    paper_id: str,
    reviewer_id: str,
    model_spec: str,
) -> Tuple[str, str, str]:
    """Evaluate a PDF against the STREAMS checklist.

    Args:
        pdf_file: Uploaded PDF file from Gradio
        paper_id: Unique identifier for the paper
        reviewer_id: Identifier for the reviewer
        model_spec: Model specification (format: "provider:model" or just "model")

    Returns:
        Tuple of (summary_html, detailed_html, json_str) for display
    """
    if pdf_file is None:
        return "❌ Please upload a PDF file", "", ""

    if not paper_id.strip():
        return "❌ Please provide a paper ID", "", ""

    try:
        # Parse model specification
        model_name, provider, use_cborg = parse_model_spec(model_spec)

        # Create engine with selected model
        review_engine = StreamsReviewEngine(model=model_name, use_cborg=use_cborg, provider=provider)

        # Run evaluation
        assessment: ChecklistAssessment = review_engine.review_pdf(
            pdf_path=pdf_file.name,
            template_path=str(TEMPLATE_PATH),
            paper_id=paper_id.strip(),
            reviewer_id=reviewer_id.strip() or "gradio_user",
        )

        # Check assessment against checklist for comprehensive metrics
        checklist_check = assessment.check_against_checklist(checklist)

        # Generate summary with completion metrics
        rating_counts = {"Yes": 0, "No": 0, "Partial": 0, "NA": 0}

        for item_assessment in assessment.assessments:
            if item_assessment.rating:
                rating_value = item_assessment.rating.value
                rating_counts[rating_value] = rating_counts.get(rating_value, 0) + 1

        # Display model info with provider
        if model_name == "mock":
            model_display = "🧪 MOCK (Testing Mode)"
        elif use_cborg:
            model_display = f"🔬 {model_name} (via CBORG proxy)"
        elif provider == "openai":
            model_display = f"🔬 {model_name} (OpenAI)"
        else:
            model_display = f"🔬 {model_name} (Anthropic)"

        # Build missing items list if any
        missing_items_html = ""
        if checklist_check["missing_items"]:
            missing_items_list = []
            for item_id in checklist_check["missing_items"][:5]:  # Show first 5
                item = checklist.get_item(item_id)
                if item:
                    missing_items_list.append(f"<li>{item_id}: {item.title}</li>")

            remaining = len(checklist_check["missing_items"]) - 5
            if remaining > 0:
                missing_items_list.append(f"<li><em>...and {remaining} more</em></li>")

            missing_items_html = f"""
            <div style="margin-top: 15px; padding: 10px; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
                <p style="margin: 0 0 8px 0;"><strong>⚠️ Missing Items ({len(checklist_check["missing_items"])} of {checklist_check["total_items"]}):</strong></p>
                <ul style="margin: 0; padding-left: 20px;">
                    {''.join(missing_items_list)}
                </ul>
            </div>
            """

        # Build extra items warning if any
        extra_items_html = ""
        if checklist_check["extra_items"]:
            extra_items_html = f"""
            <div style="margin-top: 10px; padding: 10px; background: #fee2e2; border-left: 4px solid #ef4444; border-radius: 4px;">
                <p style="margin: 0;"><strong>⚠️ Warning:</strong> {len(checklist_check["extra_items"])} assessment(s) reference items not in the checklist: {', '.join(checklist_check["extra_items"][:3])}</p>
            </div>
            """

        summary_html = f"""
        <div style="padding: 20px; background: #f0f9ff; border-radius: 8px; margin: 10px 0;">
            <h2 style="color: #0369a1; margin-top: 0;">📊 Evaluation Summary</h2>
            <p><strong>Paper ID:</strong> {assessment.paper_id}</p>
            <p><strong>Model:</strong> {model_display}</p>
            <p><strong>Coverage:</strong> <span style="font-size: 24px; color: #059669;">{checklist_check['proportion_completed']:.1%}</span>
               <span style="font-size: 14px; color: #6b7280;">({checklist_check['assessed_items']} of {checklist_check['total_items']} items)</span></p>
            <p><strong>Ratings:</strong></p>
            <ul>
                <li>✅ Yes: {rating_counts.get('Yes', 0)}</li>
                <li>❌ No: {rating_counts.get('No', 0)}</li>
                <li>⚠️ Partial: {rating_counts.get('Partial', 0)}</li>
                <li>➖ N/A: {rating_counts.get('NA', 0)}</li>
            </ul>
            <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            {missing_items_html}
            {extra_items_html}
        </div>
        """

        # Generate detailed table
        rows = []
        for item_assessment in assessment.assessments:
            rating_emoji = {
                "Yes": "✅",
                "No": "❌",
                "Partial": "⚠️",
                "NA": "➖",
            }.get(item_assessment.rating.value if item_assessment.rating else "", "")

            rows.append(f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item_assessment.item_id}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{rating_emoji} {item_assessment.rating.value if item_assessment.rating else 'N/A'}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item_assessment.comments or ''}</td>
                </tr>
            """)

        detailed_html = f"""
        <div style="margin: 10px 0;">
            <h3>📋 Detailed Assessment</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <thead>
                    <tr style="background: #f3f4f6;">
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Item ID</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Rating</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Comments</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """

        # Generate JSON for download
        json_str = json.dumps(assessment.model_dump(), indent=2, default=str)

        return summary_html, detailed_html, json_str

    except Exception as e:
        error_msg = f"❌ Error during evaluation: {str(e)}"
        return error_msg, "", ""


def chat_with_agent(message: str, history: list) -> str:
    """Chat with the STREAMS guidance agent.

    Args:
        message: User's message
        history: Chat history (list of [user, assistant] pairs)

    Returns:
        Agent's response
    """
    try:
        # Get chat agent (lazy initialization)
        agent = get_chat_agent()
        result = agent.run_sync(message)
        return result.data
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"


def create_app() -> gr.Blocks:
    """Create the Gradio application."""

    with gr.Blocks(title="STREAMS Agent", theme=gr.themes.Soft()) as app:
        gr.Markdown("""
        # 🔬 STREAMS Agent

        **AI-powered evaluation of microbiome research papers against STREAMS checklist**

        Upload a PDF to evaluate compliance with STREAMS reporting standards, or chat to learn about the guidelines.
        """)

        with gr.Tabs():
            # Tab 1: PDF Evaluation
            with gr.Tab("📄 Evaluate Paper"):
                gr.Markdown("""
                ### Upload and Evaluate
                Upload a microbiome research paper (PDF) to automatically evaluate it against the STREAMS checklist.
                """)

                with gr.Row():
                    with gr.Column(scale=1):
                        pdf_input = gr.File(
                            label="Upload PDF Paper",
                            file_types=[".pdf"],
                            type="filepath"
                        )
                        paper_id_input = gr.Textbox(
                            label="Paper ID",
                            placeholder="e.g., smith2024_gut_microbiome",
                            info="Unique identifier for this paper"
                        )
                        reviewer_id_input = gr.Textbox(
                            label="Reviewer ID (optional)",
                            placeholder="gradio_user",
                            value="gradio_user",
                            info="Your identifier as reviewer"
                        )
                        model_selector = gr.Dropdown(
                            label="Model",
                            choices=AVAILABLE_MODELS,
                            value="mock",
                            info="Select 'mock' for fast testing without API calls"
                        )
                        evaluate_btn = gr.Button("🔍 Evaluate", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        summary_output = gr.HTML(label="Summary")
                        detailed_output = gr.HTML(label="Detailed Results")

                with gr.Row():
                    json_output = gr.Textbox(
                        label="JSON Output (for download)",
                        lines=10,
                        max_lines=20,
                        visible=False
                    )
                    download_btn = gr.DownloadButton(
                        label="💾 Download JSON Results",
                        visible=False
                    )

                # Wire up evaluation
                evaluate_btn.click(
                    fn=evaluate_pdf,
                    inputs=[pdf_input, paper_id_input, reviewer_id_input, model_selector],
                    outputs=[summary_output, detailed_output, json_output],
                ).then(
                    fn=lambda json_str: (
                        gr.update(visible=bool(json_str)),
                        gr.update(visible=bool(json_str), value=json_str)
                    ),
                    inputs=[json_output],
                    outputs=[json_output, download_btn]
                )

            # Tab 2: Chat
            with gr.Tab("💬 Chat"):
                gr.Markdown("""
                ### STREAMS Guidance Chat
                Ask questions about the STREAMS checklist, get help understanding requirements, or discuss evaluation results.
                """)

                chatbot = gr.Chatbot(
                    height=500,
                    label="STREAMS Assistant",
                    avatar_images=(None, "🔬"),
                )
                msg_input = gr.Textbox(
                    label="Your message",
                    placeholder="Ask me anything about STREAMS checklist...",
                    lines=2,
                )

                with gr.Row():
                    submit_btn = gr.Button("Send", variant="primary")
                    clear_btn = gr.Button("Clear Chat")

                gr.Examples(
                    examples=[
                        "What is the STREAMS checklist?",
                        "What should be reported in the abstract section?",
                        "How do I improve compliance with methods reporting?",
                        "What's the difference between Yes, Partial, and No ratings?",
                    ],
                    inputs=msg_input,
                )

                # Wire up chat
                def respond(message, chat_history):
                    bot_response = chat_with_agent(message, chat_history)
                    chat_history.append((message, bot_response))
                    return "", chat_history

                msg_input.submit(respond, [msg_input, chatbot], [msg_input, chatbot])
                submit_btn.click(respond, [msg_input, chatbot], [msg_input, chatbot])
                clear_btn.click(lambda: [], None, chatbot)

        gr.Markdown("""
        ---
        **About STREAMS**: Standards for Technical Reporting in Environmental and host-Associated Microbiome Studies

        Built with [Pydantic AI](https://ai.pydantic.dev/) and [Gradio](https://gradio.app/)
        """)

    return app


def launch(share: bool = False, **kwargs):
    """Launch the Gradio app.

    Args:
        share: Whether to create a public share link
        **kwargs: Additional arguments passed to gr.Blocks.launch()
    """
    app = create_app()
    app.launch(share=share, **kwargs)


if __name__ == "__main__":
    launch()
