# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Open Bedrock Server is a unified, provider-agnostic chat completions API server. Its primary `/v1/chat/completions` endpoint auto-detects request format (OpenAI, Bedrock Claude, Bedrock Titan), routes to the appropriate provider based on model ID, and converts between formats seamlessly. Additional endpoints cover files, models, health, and knowledge bases. Built with FastAPI + Pydantic, uses boto3 for AWS Bedrock and the openai SDK for OpenAI.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run all safe tests (no real API calls) — default for development
uv run python run_tests.py --mode all-safe -v

# Run only unit tests
uv run python run_tests.py --mode unit -v

# Run a single test file
uv run pytest tests/test_chat.py -v

# Run a single test by name
uv run pytest -k "test_openai_format_detection" -v

# Run tests by marker
uv run pytest -m "unit" -v
uv run pytest -m "integration and not real_api" -v

# Run real API tests (requires credentials, costs money)
uv run python run_tests.py --mode real-api -v

# Lint
uv run black src tests
uv run isort src tests
uv run flake8 src tests
uv run mypy src

# Start the server
bedrock-chat serve --host 0.0.0.0 --port 8000

# Interactive chat
bedrock-chat chat --model gpt-4o-mini --stream
```

## Architecture

### Source layout: `src/open_bedrock_server/`

**Request flow:** Client → FastAPI routes (`api/routes/chat.py`) → `RequestFormatDetector` (detects OpenAI/Bedrock Claude/Bedrock Titan) → `LLMServiceFactory.get_service_for_model()` (routes by model ID prefix) → provider service → response conversion → client.

**Key layers:**

- **`api/`** — FastAPI app, routes (chat, files, health, models, knowledge_bases), auth + logging middleware, request/response schemas.
- **`services/`** — `AbstractLLMService` (ABC in `llm_service_abc.py`) defines the contract. `OpenAIService` and `BedrockService` implement it. `LLMServiceFactory` resolves provider from model ID (prefix-based: `gpt-*` → OpenAI, `anthropic.*`/`amazon.*`/`meta.*`/etc. → Bedrock). File services handle S3-backed file upload/query.
- **`adapters/`** — Format conversion layer. `BaseLLMAdapter` (ABC) defines convert-to/from-provider methods. `OpenAIAdapter` handles OpenAI. `BedrockToOpenAIAdapter` accepts Bedrock format and delegates to OpenAI. The `bedrock/` subdirectory uses a **strategy pattern**: `BedrockAdapterStrategy` base with per-vendor strategies (`claude_strategy.py`, `titan_strategy.py`, `nova_strategy.py`, `mistral_strategy.py`, `ai21_strategy.py`, `cohere_strategy.py`, `meta_strategy.py`, `stability_strategy.py`, `writer_strategy.py`).
- **`core/`** — Pydantic models (`models.py` for OpenAI-compatible types, `bedrock_models.py` for Bedrock types including `RequestFormat` enum), custom exceptions.
- **`utils/`** — `RequestFormatDetector` (auto-detects input format), `config_loader` (env-based config via `python-dotenv` + `os.getenv`), `knowledge_base_detector`.
- **`cli/`** — Click-based CLI (`bedrock-chat` entry point) for server management, interactive chat, config.

### Adding a new Bedrock model family

1. Create a new strategy in `adapters/bedrock/` implementing `BedrockAdapterStrategy`
2. Register the model prefix in `LLMServiceFactory.get_service_for_model()` and `BaseLLMAdapter._get_default_param()`
3. Add to `get_supported_models()` in `llm_service_factory.py`

## Test Markers

Defined in `pytest.ini`. CI runs `unit` + `integration and not real_api`. Key markers:

- `unit` — fast, no external deps
- `integration` — may use mocks
- `real_api` / `external_api` — real API calls, skipped in CI
- `openai_integration` — needs `OPENAI_API_KEY`
- `aws_integration` / `bedrock_integration` — needs AWS credentials

## CI

GitHub Actions (`ci-tests.yml`) runs on push/PR to main/develop with Python 3.12 + 3.13. Runs unit → mocked integration → all-safe tests. Real API tests are a separate manual workflow (`real-api-tests.yml`).

## Configuration

Uses environment variables loaded from a `.env` file via `python-dotenv`, with values read in `utils/config_loader.py`. Key vars: `API_KEY` (server auth), `OPENAI_API_KEY`, AWS credentials (`AWS_PROFILE`/`AWS_ACCESS_KEY_ID`+`AWS_SECRET_ACCESS_KEY`/`AWS_ROLE_ARN`), `AWS_REGION`, `S3_FILES_BUCKET` (for file query feature).
