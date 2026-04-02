---
title: Real API Testing
nav_order: 8
description: Real API integration tests with live credentials
---

# Real API Integration Tests

This directory contains comprehensive integration tests that use real API credentials from your `.env` file to test the actual functionality of OpenAI and AWS Bedrock services.

## ⚠️ IMPORTANT SAFETY NOTICE

**These tests make REAL API calls and incur costs!**

The tests are designed with safety in mind:

- 🛡️ __Protected by `real_api` marker__: Tests only run when explicitly requested
- 💰 **Cost warnings**: Interactive prompts before running costly tests
- 📊 **Minimal usage**: Designed to use minimal tokens to reduce costs
- 🚫 **No accidental runs**: Regular test runs will skip these tests

## Overview

The `test_real_api_integration.py` file contains tests that:

- Use real OpenAI API keys to test chat completions (streaming and non-streaming)
- Use real AWS Bedrock credentials to test Claude and Titan models
- Compare responses between different providers
- Test configuration validation and error handling
- Test performance characteristics and token usage tracking

## Prerequisites

1. **Environment Configuration**: Ensure your `.env` file is properly configured with API credentials:

```ini
# OpenAI Configuration
OPENAI_API_KEY="sk-proj-..."

# AWS Bedrock Configuration
AWS_ACCESS_KEY_ID="AKIA..."
AWS_SECRET_ACCESS_KEY="..."
AWS_SESSION_TOKEN="..."  # If using temporary credentials
AWS_REGION="us-east-1"
```

2. **Dependencies**: Make sure all required packages are installed:

```bash
pip install pytest pytest-asyncio pytest-cov
```

## Running the Tests

### 🚨 Safety First: Understanding the Markers

- __`real_api` marker__: Tests that make actual API calls and cost money
- **No marker**: Safe configuration tests that don't make API calls

```bash
# Safe: Run only configuration tests (NO API CALLS)
pytest tests/test_real_api_integration.py -k "not real_api"

# COSTS MONEY: Run real API tests (requires explicit marker)
pytest tests/test_real_api_integration.py -m real_api
```

### Using the Test Runner Script (Recommended)

The test runner includes safety prompts and cost warnings:

```bash
# Run quick smoke tests (includes cost warning)
python run_real_api_tests.py

# Skip the cost confirmation prompt
python run_real_api_tests.py --yes

# Run all real API tests
python run_real_api_tests.py --mode all

# Run only OpenAI tests
python run_real_api_tests.py --mode openai

# Run only Bedrock tests
python run_real_api_tests.py --mode bedrock

# Run ONLY configuration tests (NO API CALLS, NO COSTS)
python run_real_api_tests.py --mode config

# Run with verbose output
python run_real_api_tests.py --verbose

# Stop on first failure
python run_real_api_tests.py --failfast
```

### Using pytest directly

**⚠️ These commands make real API calls and cost money!**

```bash
# Run all real API tests (COSTS MONEY)
pytest tests/test_real_api_integration.py -m real_api -v

# Run only OpenAI tests (COSTS MONEY)
pytest tests/test_real_api_integration.py -m real_api -k "TestRealOpenAI" -v

# Run only Bedrock tests (COSTS MONEY)
pytest tests/test_real_api_integration.py -m real_api -k "TestRealBedrock" -v

# Run SAFE configuration tests only (NO API CALLS)
pytest tests/test_real_api_integration.py -k "not real_api" -v

# Run with logging (COSTS MONEY)
pytest tests/test_real_api_integration.py -m real_api --log-cli-level=INFO -s
```

## Test Categories

### 💰 TestRealOpenAIIntegration (Costs Money)

- __test_openai_chat_completion_basic__: Basic chat completion functionality
- __test_openai_streaming_chat_completion__: Streaming response handling
- __test_openai_multiple_models__: Testing different OpenAI models

### 💰 TestRealBedrockIntegration (Costs Money)

- __test_bedrock_claude_chat_completion__: Claude chat completion
- __test_bedrock_claude_streaming__: Claude streaming responses
- __test_bedrock_titan_chat_completion__: Titan text generation
- __test_bedrock_multiple_models__: Testing different Bedrock models

### 💰 TestRealAPIComparison (Costs Money)

- __test_compare_openai_vs_bedrock__: Side-by-side comparison of providers

### 🆓 TestConfigurationValidation (Free)

- __test_env_variables_loaded__: Verify environment configuration (no API calls)
- __test_factory_model_resolution__: Test model resolution logic (no API calls)
- __test_error_handling_invalid_model__: Error handling validation (costs money)

### 💰 TestPerformanceAndLimits (Costs Money)

- __test_concurrent_requests__: Concurrent API request handling
- __test_token_usage_tracking__: Token usage and billing tracking

## Test Markers

The tests use pytest markers to ensure safety:

- `@pytest.mark.real_api`: __REQUIRED__ for tests that make real API calls
- `@pytest.mark.skipif(not OPENAI_AVAILABLE)`: Skip if OpenAI not configured
- `@pytest.mark.skipif(not AWS_AVAILABLE)`: Skip if AWS not configured

## Expected Behavior

### Successful Test Run

When tests pass, you should see:

- ✅ API credentials validated
- 💰 Cost warnings (for real API tests)
- 📋 Test execution with detailed logging
- 🔍 Response content and usage metrics
- ✅ All assertions passing

### Skipped Tests

Tests will be automatically skipped if:

- Required API credentials are not configured
- You don't use the `real_api` marker (for safety)
- Specific models are not available in your region
- Rate limits are encountered (for some tests)

### Cost Considerations

**💰 API Usage Costs:**

- OpenAI: Typically a few cents per test run
- AWS Bedrock: Varies by model and region
- **Quick mode**: ~$0.01-0.02 per run
- **Full test suite**: ~$0.05-0.10 per run

**Cost Minimization Features:**

- Use the quick test mode for regular validation
- Interactive cost confirmations before running expensive tests
- Minimal token usage in all test prompts
- Configuration-only tests that make no API calls

## Safety Features

### 1. **Marker Protection**

```bash
# This will NOT run real API tests (safe)
pytest tests/test_real_api_integration.py

# This WILL run real API tests (costs money)
pytest tests/test_real_api_integration.py -m real_api
```

### 2. **Interactive Cost Warnings**

The test runner will prompt before running costly tests:

```yaml
⚠️  COST WARNING:
   These tests make REAL API calls that will incur costs!
   Estimated cost per run:
   • Quick mode: ~$0.01-0.02
   • Full test suite: ~$0.05-0.10

   Continue? [y/N]:
```

### 3. **Configuration-Only Mode**

```bash
# Run ONLY configuration tests (zero API calls)
python run_real_api_tests.py --mode config
```

## Troubleshooting

### Common Issues

1. **Tests Not Running**

```sh
No tests ran matching the given pattern
```

- __Solution__: You need to use `-m real_api` to run the real API tests
- **Safe alternative**: Use `--mode config` for configuration-only tests

2. **Authentication Errors**

```ini
ConfigurationError: API key not configured
```

- Verify your `.env` file contains valid credentials
- Check that keys are not expired or revoked

3. **Model Not Available**

```sh
ModelNotFoundError: Model not supported in region
```

- Some Bedrock models are region-specific
- Update the test model IDs for your region

4. **Rate Limiting**

```ini
RateLimitError: Too many requests
```

- Add delays between tests if needed
- Use smaller batch sizes for concurrent tests

### Debugging

To debug test failures:

1. **Test configuration safely**:

```bash
python run_real_api_tests.py --mode config
```

2. **Enable verbose logging**:

```bash
python run_real_api_tests.py --verbose --yes
```

3. **Run individual test methods**:

```bash
pytest tests/test_real_api_integration.py::TestRealOpenAIIntegration::test_openai_chat_completion_basic -m real_api -v -s
```

## Integration with CI/CD

### Recommended CI/CD Setup

For automated testing, consider these safety measures:

1. **Manual Triggers Only**: Never run real API tests on every commit
2. **Separate API Keys**: Use dedicated testing API keys with spending limits
3. **Cost Monitoring**: Set up billing alerts
4. **Conditional Execution**: Only run on specific branches

Example GitHub Actions configuration:

```yaml
- name: Run Configuration Tests (Safe)
  run: python run_real_api_tests.py --mode config
  # This runs on every push - no API calls

- name: Run Real API Tests (Costs Money)
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: python run_real_api_tests.py --mode quick --yes
  if: github.event_name == 'workflow_dispatch'  # Manual trigger only
```

## Contributing

When adding new tests:

1. __Always use the `real_api` marker__ for tests that make API calls
2. **Test configuration separately** without the marker for free validation
3. **Include proper assertions** for response validation
4. **Add logging** for debugging and monitoring
5. **Consider cost implications** of new API calls
6. **Test both success and failure scenarios**
7. **Use minimal tokens** to keep costs low

## Quick Start Examples

### Safe Configuration Check

```bash
# Test your setup without any API calls (FREE)
python run_real_api_tests.py --mode config
```

### Quick Validation

```bash
# Test that your APIs work with minimal cost (~$0.01)
python run_real_api_tests.py --mode quick
```

### Direct Script Execution

```python
# Run basic validation directly (costs money)
PYTHONPATH=. python tests/test_real_api_integration.py
```

Remember: **Always check your API usage dashboards** after running real API tests to monitor costs!