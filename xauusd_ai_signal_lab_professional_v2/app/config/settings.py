from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    biquote_base_url: str = os.getenv("BIQUOTE_BASE_URL", "https://biquote.io")
    groq_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    gmail_sender: str = os.getenv("GMAIL_SENDER", "")
    gmail_app_password: str = os.getenv("GMAIL_APP_PASSWORD", "")
    gmail_recipient: str = os.getenv("GMAIL_RECIPIENT", "")

settings = Settings()
