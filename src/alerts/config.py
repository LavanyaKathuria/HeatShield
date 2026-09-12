"""Load backend configuration consistently for API, scheduler and CLI imports."""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)
