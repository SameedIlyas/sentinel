"""Script to run the Policy Engine service"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "policy_engine.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
