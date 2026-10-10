import uvicorn
import sys
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from api.app.config import settings

if __name__ == "__main__":
    print(f"Starting {settings.APP_NAME} on http://{settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "api.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
