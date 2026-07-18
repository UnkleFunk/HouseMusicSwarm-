from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider


def create_ableton_dream_agent() -> Agent:
    return Agent(
        name="Ableton Dream Agent",
        description=(
            "Dreams up and ships new Ableton Live Extension song sketch templates every night. "
            "Generates complete TypeScript Extension code personalized to Unkle Funk's deep house DNA. "
            "Manages the nightly sketch library, stores feedback, and evolves the style over time."
        ),
        instructions="./instructions.md",
        files_folder="./files",
        tools_folder="./tools",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Dream up tonight's song sketch.",
            "What sketches have been generated so far?",
            "Rate 'Slow Burn on State Street' 5/5 — loved the rolling congas and the bass walk.",
            "Show me the idea file for today's sketch.",
        ],
    )
