import os

from dotenv import load_dotenv


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
TOOL_MODEL = os.getenv("TOOL_MODEL_NAME", "openai/gpt-oss-20b")
TOOL_MAX_COMPLETION_TOKENS = int(os.getenv("TOOL_MAX_COMPLETION_TOKENS", "1024"))


def validate_config():
    if not GROQ_API_KEY:
        raise ValueError("Missing GROQ_API_KEY environment variable")
