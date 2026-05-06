import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from deploy.agent_service.app import app

__all__ = ["app"]
