# Sentinel AI

AI governance platform for securing autonomous AI agents with real-time policy enforcement and visibility.

## Installation

```bash
pip install sentinel-ai
```

## Quick Start

```python
from sentinel import secure_agent

@secure_agent(
    agent_id="my-agent",
    config={
        "api_key": "sentinel_key_xxx",
        "endpoint": "https://api.sentinel.ai"
    }
)
def my_agent():
    # Your agent implementation
    pass
```

## Features

- **One-line integration**: Secure your AI agents with a single decorator
- **Real-time policy enforcement**: Block dangerous actions before they happen
- **Comprehensive audit logging**: Track every action your agents take
- **Multi-LLM support**: Works with OpenAI, Anthropic, Azure OpenAI, and Google Gemini
- **Minimal overhead**: <100ms latency for 95% of requests

## Development

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Format code:

```bash
black .
isort .
```

Lint code:

```bash
flake8 sentinel
mypy sentinel
```

## License

MIT
