"""Script to run the Policy Engine service"""

import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Sentinel Policy Engine")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    uvicorn.run(
        "policy_engine.main:app",
        host="0.0.0.0",
        port=8000,
        reload=args.reload,
        reload_dirs=["policy_engine"] if args.reload else None,
        log_level="info",
    )
