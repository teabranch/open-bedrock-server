---
title: Home
nav_order: 0
permalink: /
---

# Open Bedrock Server

A unified, provider-agnostic chat completions API server supporting OpenAI and AWS Bedrock.

<p><em>Find this useful? Star the repo to follow updates and show support!</em>
<iframe src="https://ghbtns.com/github-btn.html?user=teabranch&repo=open-bedrock-server&type=star&count=true&size=large" frameborder="0" scrolling="0" width="170" height="30" title="Star on GitHub" style="vertical-align: middle;"></iframe></p>

> **Install from PyPI** — `pip install open-bedrock-server` and run `bedrock-chat serve`.
> See [CLI Reference](cli-reference) for all options.

---

## Quick Start

### Installation

```bash
# From PyPI
pip install open-bedrock-server

# Or from source
git clone https://github.com/teabranch/open-bedrock-server.git
cd open-bedrock-server
uv pip install -e .
```

### Configure

```bash
bedrock-chat config set
```

Or set environment variables:

```bash
export OPENAI_API_KEY=sk-your-key
export AWS_PROFILE=your-profile
export API_KEY=your-server-auth-key
```

### Run

```bash
bedrock-chat serve --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
```

### Basic Usage

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

---

## Unified Endpoint

The `/v1/chat/completions` endpoint is the **only endpoint you need**. It:

1. **Auto-detects** your input format (OpenAI, Bedrock Claude, Bedrock Titan)
2. **Routes** to the appropriate provider based on model ID
3. **Converts** between formats as needed
4. **Streams** responses in real-time when requested

### Format Combinations

| Input Format | Output Format | Use Case | Streaming |
|-------------|---------------|----------|-----------|
| OpenAI | OpenAI | Standard OpenAI usage | Yes |
| OpenAI | Bedrock Claude | OpenAI clients to Bedrock response | Yes |
| OpenAI | Bedrock Titan | OpenAI clients to Titan response | Yes |
| Bedrock Claude | OpenAI | Bedrock clients to OpenAI response | Yes |
| Bedrock Claude | Bedrock Claude | Claude format preserved | Yes |
| Bedrock Titan | OpenAI | Titan clients to OpenAI response | Yes |
| Bedrock Titan | Bedrock Titan | Titan format preserved | Yes |

---

## Documentation

### Core

- **[Getting Started](getting-started)** - Installation, setup, and first steps
- **[API Reference](api-reference)** - Complete API documentation
- **[CLI Reference](cli-reference)** - Command-line interface guide

### Advanced Features

- **[Knowledge Bases (RAG)](knowledge_bases)** - Bedrock Knowledge Bases integration
- **[Files API](FILES_API)** - File upload and management capabilities

### Guides

- **[Usage Guide](guides/usage)** - Programming examples and use cases
- **[AWS Authentication](guides/aws-authentication)** - AWS credential configuration
- **[Architecture](guides/architecture)** - System design and architecture
- **[Core Components](guides/core-components)** - Detailed component documentation
- **[Testing](guides/testing)** - Testing strategies and coverage
- **[Packaging](guides/packaging)** - Building and distributing the package

### Development

- **[Development Guide](development)** - Extending and customizing the server
- **[Test Suite](testing)** - Test suite organization
- **[Real API Testing](real-api-testing)** - Real API integration tests

---

## Key Features

### Unified Interface

- **Single Endpoint**: `/v1/chat/completions` handles everything
- **Auto-Detection**: Intelligent format detection
- **Model-Based Routing**: Automatic provider selection
- **Format Conversion**: Seamless translation between formats

### File Query System

- **File Upload**: Upload documents to S3 storage with OpenAI-compatible API
- **Smart Processing**: Automatic content extraction from CSV, JSON, HTML, XML, Markdown, and text files
- **Chat Integration**: Use `file_ids` parameter to include file content as context in conversations
- **File Management**: Complete CRUD operations for uploaded files

### Enterprise Ready

- **Authentication**: Secure API key-based authentication
- **Streaming**: Real-time response streaming
- **Error Handling**: Comprehensive error management
- **Monitoring**: Request/response logging and health checks

### Developer Friendly

- **CLI Tools**: Interactive chat, configuration, and server management
- **OpenAI Compatible**: Drop-in replacement for OpenAI Chat Completions API
- **Extensible**: Easy to add new providers and formats
- **Well Tested**: Comprehensive test coverage

---

## Quick Links

- **[GitHub Repository](https://github.com/teabranch/open-bedrock-server)**
- **[Issues & Support](https://github.com/teabranch/open-bedrock-server/issues)**
- **[OpenAI API Reference](https://platform.openai.com/docs/api-reference/chat)**
- **[AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)**

---

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/teabranch/open-bedrock-server/blob/main/LICENSE) file for details.
