from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent


def render_prompt(name: str, **context) -> str:
    template = (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()
    return template.format(**context)
