import os
from agency_swarm import Agent, ModelSettings
from openai.types.shared.reasoning import Reasoning
from agency_swarm.tools import LoadFileAttachment
from shared_tools import CopyFile

from config import get_default_model, is_openai_provider
from reference_finder_agent.tools import (
    ListAudioDevices,
    CaptureAudio,
    ExtractFeatures,
    BuildDatabase,
    SearchReferences,
    FormatResults,
)

current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.md")


def create_reference_finder() -> Agent:
    return Agent(
        name="Reference Finder",
        description=(
            "House music reference track specialist. Captures live audio or analyzes uploaded files, "
            "extracts sonic fingerprints, and returns the most similar recent Beatport/Traxsource "
            "chart tracks. Use for mix referencing, A/B comparison, and production benchmarking."
        ),
        instructions=instructions_path,
        tools_folder=os.path.join(current_dir, "tools"),
        model=get_default_model(),
        tools=[
            LoadFileAttachment,
            CopyFile,
            ListAudioDevices,
            CaptureAudio,
            ExtractFeatures,
            BuildDatabase,
            SearchReferences,
            FormatResults,
        ],
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
            truncation="auto",
            response_include=["web_search_call.action.sources"] if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Find reference tracks that match what I'm playing right now.",
            "Analyze my current track and find similar recent chart-toppers.",
            "Build the reference database from recent Beatport and Traxsource charts.",
            "Show me what's charting in tech house that sounds like this mix.",
        ],
    )
