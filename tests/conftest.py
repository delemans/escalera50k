import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATOS_DIR", tempfile.mkdtemp(prefix="escalera-test-"))
os.environ.setdefault("TOKEN_BOT", "test")
os.environ["CHAT_ID"] = ""
os.environ["ENV_FILE"] = "/nonexistent"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
