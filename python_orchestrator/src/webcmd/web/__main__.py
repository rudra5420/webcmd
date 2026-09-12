"""Entry point for running python -m webcmd.web."""
import sys
import uvicorn
from webcmd.web.server import create_app

def main():
    host = "127.0.0.1"
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    print(f"Starting WebCMD Web Dashboard at http://{host}:{port}")
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
