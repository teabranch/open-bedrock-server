---
title: Testing
nav_order: 7
description: Test suite organization and CI/CD testing strategies
---

# Test Suite Organization

This directory contains a comprehensive test suite organized for different CI/CD scenarios. The tests are carefully separated to ensure **safe CI execution** while still providing **real API validation**.

## 🎯 Test Categories

### 1. **Unit Tests** (`unit` marker)
- **Purpose**: Fast, isolated tests with no external dependencies
- **CI Safe**: ✅ Always safe to run
- **Cost**: 🆓 Free
- **When to run**: Every commit, every PR
- **Examples**: Model validation, utility functions, core logic

### 2. **Integration Tests** (`integration` marker)
- **Purpose**: Component integration with mocked external services
- **CI Safe**: ✅ Safe when excluding `real_api` marker
- **Cost**: 🆓 Free (uses mocks)
- **When to run**: Every commit, every PR
- **Examples**: Service integrations with mocked APIs

### 3. **Real API Tests** (`real_api` marker)
- **Purpose**: End-to-end validation with actual API services
- **CI Safe**: ❌ Only run manually or on schedule
- **Cost**: 💰 Costs money (API calls)
- **When to run**: Manual trigger, scheduled validation
- **Examples**: OpenAI API calls, AWS Bedrock integration

## 🚀 Running Tests

### Quick Start

```bash
# Run all safe tests (recommended for CI)
python run_tests.py --mode mock

# Run only unit tests (fastest)
python run_tests.py --mode unit

# Run integration tests with mocks
python run_tests.py --mode integration
```

### CI/CD Modes

```bash
# CI Safe modes (no API calls, no costs)
python run_tests.py --mode unit           # Unit tests only
python run_tests.py --mode integration    # Integration tests with mocks
python run_tests.py --mode mock           # All safe tests (default)
python run_tests.py --mode all-safe       # All safe tests (explicit)

# Manual/Scheduled modes (cost money)
python run_tests.py --mode real-api       # Real API tests (with confirmation)
python run_tests.py --mode all            # Everything (with confirmation)
```

### Direct pytest Usage

```bash
# Safe for CI (no API calls)
pytest -m "not real_api"                  # All safe tests
pytest -m "unit"                          # Unit tests only
pytest -m "integration and not real_api"  # Integration tests with mocks

# Costs money (manual only)
pytest -m "real_api"                      # Real API tests
pytest -m "openai_integration"            # OpenAI specific tests
pytest -m "bedrock_integration"           # Bedrock specific tests
```

## 🔧 GitHub Actions Integration

### CI Workflow (Automatic)
File: `.github/workflows/ci-tests.yml`

```yaml
# Runs on every push/PR - SAFE
- Push to main/develop
- Pull requests
- Multiple Python versions
- Coverage reporting
- No API calls, no costs
```

### Real API Workflow (Manual)
File: `.github/workflows/real-api-tests.yml`

```yaml
# Manual trigger only - COSTS MONEY
- workflow_dispatch with confirmation
- Optional scheduled runs
- Uses secrets for API keys
- Cost acknowledgment required
```

## 📊 Test Organization

### Directory Structure
```
tests/
├── test_*.py                    # Main test files
├── api/                         # API-specific tests
├── core/                        # Core functionality tests
├── services/                    # Service layer tests
├── utils/                       # Utility tests
├── conftest.py                  # Test configuration
├── README.md                    # This file
└── README_REAL_API_TESTS.md     # Real API test details
```

### Test File Organization

| File | Type | Markers | Description |
|------|------|---------|-------------|
| `test_models.py` | Unit | `unit` | Data model validation |
| `test_auth.py` | Unit | `unit` | Authentication logic |
| `test_chat.py` | Mixed | `integration`, some `real_api` | Chat functionality |
| `test_bedrock_chat.py` | Mixed | `integration`, some `real_api` | Bedrock integration |
| `test_real_api_integration.py` | Real API | `real_api` | Comprehensive API tests |

## 🔒 Safety Features

### 1. **Marker Protection**
- Tests with `real_api` marker only run when explicitly requested
- Default test runs exclude expensive tests
- Clear separation between mock and real tests

### 2. **Cost Warnings**
- Interactive prompts before running expensive tests
- Clear cost estimates for different test modes
- Confirmation required for real API tests

### 3. **CI/CD Safety**
- GitHub Actions workflows separated by cost/safety
- Real API tests require manual trigger and confirmation
- Environment variable validation before API calls

## 📋 Test Markers Reference

| Marker | Purpose | CI Safe | Cost | Usage |
|--------|---------|---------|------|-------|
| `unit` | Fast unit tests | ✅ | 🆓 | `-m unit` |
| `integration` | Integration with mocks | ✅ | 🆓 | `-m integration` |
| `real_api` | Real API calls | ❌ | 💰 | `-m real_api` |
| `openai_integration` | OpenAI specific | ❌ | 💰 | `-m openai_integration` |
| `bedrock_integration` | Bedrock specific | ❌ | 💰 | `-m bedrock_integration` |
| `slow` | Slow tests | ✅ | 🆓 | `-m "not slow"` |

## 🎮 Development Workflow

### During Development
```bash
# Quick validation
python run_tests.py --mode unit --verbose

# Full local validation (safe)
python run_tests.py --mode mock --verbose

# Before committing
python run_tests.py --mode all-safe
```

### Before Release
```bash
# Validate real API integration (costs money)
python run_tests.py --mode real-api
```

### CI/CD Pipeline
```bash
# Automated (safe)
- Every commit: unit tests
- Every PR: all safe tests
- Merge to main: full safe test suite

# Manual (costs money)  
- Release validation: real API tests
- Weekly scheduled: comprehensive API tests
```

## 🛡️ Best Practices

### For CI/CD
1. **Never run real API tests automatically** - always require manual trigger
2. **Use cost confirmations** - require explicit acknowledgment of costs
3. **Set spending limits** - configure API key spending limits
4. **Monitor usage** - set up billing alerts for API usage
5. **Separate environments** - use different API keys for testing vs production

### For Development
1. **Start with unit tests** - write fast, isolated tests first
2. **Mock external dependencies** - use mocks for integration tests
3. **Validate with real APIs sparingly** - only when necessary
4. **Document cost implications** - clearly mark expensive tests
5. **Use minimal API calls** - keep real API tests lightweight

### For Testing
1. **Layer your tests** - unit → integration → real API
2. **Mark tests appropriately** - use correct markers for each test
3. **Handle credentials safely** - never commit API keys
4. **Test error scenarios** - include negative test cases
5. **Monitor test costs** - track spending on API calls

## 🔍 Troubleshooting

### Common Issues

1. **Tests not running in CI**
   - Check that you're using safe markers (`not real_api`)
   - Verify GitHub Actions workflow configuration

2. **Real API tests failing**
   - Check API credentials in environment/secrets
   - Verify API key permissions and limits
   - Check service availability and quotas

3. **Unexpected costs**
   - Ensure real API tests have `real_api` marker
   - Check that CI workflows exclude expensive tests
   - Review API usage dashboards

### Debugging Commands

```bash
# Check test discovery
pytest --collect-only

# Dry run without execution
pytest --collect-only -m real_api

# Run with maximum verbosity
python run_tests.py --mode unit --verbose -v

# Check marker filtering
pytest -m "not real_api" --collect-only
```

## 📈 Continuous Improvement

### Metrics to Track
- Test execution time (aim for fast CI)
- API usage costs (minimize for validation)
- Test coverage (maintain high coverage with safe tests)
- Flaky test rates (especially for real API tests)

### Regular Reviews
- Weekly: Review test execution times
- Monthly: Review API costs and usage patterns
- Quarterly: Review test organization and effectiveness
- Before releases: Validate real API functionality

This organization ensures **safe, fast CI execution** while maintaining **comprehensive validation** through carefully managed real API testing. 