from pathlib import Path

_PROMPTS_ROOT = Path(__file__).resolve().parent


def load_prompt(relative_path: str) -> str:
    path = _PROMPTS_ROOT / relative_path
    return path.read_text(encoding="utf-8").strip()
