from pathlib import Path
import yaml

PROMPT_FILE = (
    Path(__file__).resolve().parents[1]
    / "prompt"
    / "system_prompt.yml"
)

def load_system_prompt() -> str:
    with PROMPT_FILE.open("r", encoding="utf-8") as file:
        prompt_data = yaml.safe_load(file)

    template = prompt_data.get("system_prompt", {}).get("template")

    if not template:
        raise ValueError(
            f"Missing 'template' in prompt file: {PROMPT_FILE}"
        )

    return template
