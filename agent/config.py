import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

API_KEY = os.getenv('OPENAI_API_KEY', '').strip()
API_BASE_URL = os.getenv('OPENAI_BASE_URL', '').strip() or None
VISION_MODEL = os.getenv('VISION_MODEL', 'gpt-4o-mini').strip()
VOSK_MODEL_PATH = Path(os.getenv('VOSK_MODEL_PATH', 'models/vosk-es'))
if not VOSK_MODEL_PATH.is_absolute():
    VOSK_MODEL_PATH = ROOT / VOSK_MODEL_PATH

try:
    ANALYSIS_INTERVAL = max(1.0, min(60.0, float(os.getenv('VISION_INTERVAL_SECONDS', '8'))))
except ValueError:
    ANALYSIS_INTERVAL = 8.0

MAX_ACTIONS_PER_TASK = 12
MAX_ANALYSES_PER_TASK = 20
PROPOSAL_TIMEOUT_SECONDS = 25
