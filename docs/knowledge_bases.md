---
title: Knowledge Bases
nav_order: 10
description: AWS Bedrock Knowledge Bases (RAG) integration
---

# Knowledge Bases (RAG) Integration

This guide covers the integrated AWS Bedrock Knowledge Bases functionality in the Open Bedrock Server Server, providing Retrieval-Augmented Generation (RAG) capabilities.

## Overview

The Knowledge Base integration allows you to:

- **Create and manage** AWS Bedrock Knowledge Bases
- **Query knowledge bases** directly for retrieval-only operations
- **Enhance chat completions** with contextual information from knowledge bases
- **Auto-detect** when to use RAG based on user queries
- **Access via API, CLI, and Python SDK** consistently

## Features

### 🧠 Smart RAG Integration
- **Auto-detection**: Automatically detects when queries need knowledge base retrieval
- **Smart routing**: Routes between regular chat and RAG-enhanced responses
- **Context augmentation**: Enhances prompts with relevant retrieved content
- **Citation support**: Includes source citations in OpenAI-compatible format

### 🔧 Management Capabilities
- **Knowledge Base CRUD**: Create, read, update, delete knowledge bases
- **Data Source management**: Add and sync S3, web, and other data sources
- **Real-time sync**: Monitor ingestion jobs and data source status

### 🌐 Multi-Interface Access
- **REST API**: Full API access with OpenAI-compatible endpoints
- **CLI commands**: Command-line tools for all operations
- **Python SDK**: Programmatic access (when using as a package)

## Quick Start

### 1. Prerequisites

Ensure you have:
- AWS credentials configured with Bedrock permissions
- An existing Bedrock Knowledge Base OR permissions to create one
- The server running with proper AWS configuration

### 2. Environment Setup

Add Knowledge Base configuration to your `.env` file:

```bash
# AWS Configuration (required)
AWS_REGION=us-east-1
AWS_PROFILE=your-profile  # OR use AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY

# Optional: Default Knowledge Base
DEFAULT_KNOWLEDGE_BASE_ID=your-kb-id
```

### 3. Basic Usage

#### Via CLI (Easiest)

```bash
# List available knowledge bases
accs kb list

# Get details of a specific knowledge base
accs kb get YOUR_KB_ID

# Query a knowledge base directly
accs kb query YOUR_KB_ID "What is the refund policy?"

# Start interactive chat with RAG
accs kb chat YOUR_KB_ID --model anthropic.claude-3-5-haiku-20241022-v1:0
```

#### Via API

```bash
# List knowledge bases
curl -X GET "http://localhost:8000/v1/knowledge-bases" \
  -H "Authorization: Bearer your-api-key"

# Enhanced chat completion with auto-KB detection
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic.claude-3-5-haiku-20241022-v1:0",
    "messages": [
      {"role": "user", "content": "What does the documentation say about refunds?"}
    ],
    "knowledge_base_id": "YOUR_KB_ID",
    "auto_kb": true
  }'
```

## API Reference

### Knowledge Base Management

#### List Knowledge Bases
```http
GET /v1/knowledge-bases
Authorization: Bearer your-api-key
```

**Query Parameters:**
- `max_results` (optional): Maximum results to return (1-100, default: 10)
- `next_token` (optional): Pagination token

**Response:**
```json
{
  "knowledgeBaseSummaries": [
    {
      "knowledgeBaseId": "kb-123456",
      "name": "Product Documentation",
      "description": "Company product documentation",
      "status": "ACTIVE",
      "createdAt": "2024-01-15T10:30:00Z",
      "updatedAt": "2024-01-15T10:30:00Z"
    }
  ],
  "nextToken": "optional-pagination-token"
}
```

#### Get Knowledge Base Details
```http
GET /v1/knowledge-bases/{knowledge_base_id}
Authorization: Bearer your-api-key
```

#### Delete Knowledge Base
```http
DELETE /v1/knowledge-bases/{knowledge_base_id}
Authorization: Bearer your-api-key
```

### Knowledge Base Querying

#### Direct Query (Retrieve-Only)
```http
POST /v1/knowledge-bases/{knowledge_base_id}/query
Authorization: Bearer your-api-key
```

**Query Parameters:**
- `query` (required): Search query text
- `max_results` (optional): Maximum results (1-100, default: 10)

**Response:**
```json
{
  "retrievalResults": [
    {
      "content": "Relevant document content...",
      "score": 0.95,
      "metadata": {
        "source": "s3://bucket/document.pdf",
        "title": "Refund Policy"
      },
      "location": {
        "type": "S3",
        "s3Location": {
          "uri": "s3://bucket/document.pdf"
        }
      }
    }
  ]
}
```

#### Retrieve and Generate
```http
POST /v1/knowledge-bases/{knowledge_base_id}/retrieve-and-generate
Authorization: Bearer your-api-key
Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "What is the refund policy?",
  "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0",
  "retrievalConfiguration": {
    "vectorSearchConfiguration": {
      "numberOfResults": 5
    }
  }
}
```

### Enhanced Chat Completions

The `/v1/chat/completions` endpoint supports additional Knowledge Base parameters:

```json
{
  "model": "anthropic.claude-3-5-haiku-20241022-v1:0",
  "messages": [
    {"role": "user", "content": "What does the documentation say about returns?"}
  ],
  
  // Knowledge Base parameters
  "knowledge_base_id": "kb-123456",           // Explicit KB ID
  "auto_kb": true,                            // Auto-detect when to use KB
  "retrieval_config": {                       // Retrieval configuration
    "max_results": 5,
    "score_threshold": 0.7
  },
  "citation_format": "openai"                 // Citation format: "openai" or "bedrock"
}
```

**Response with KB Metadata:**
```json
{
  "id": "chatcmpl-kb-20241201120000",
  "object": "chat.completion",
  "created": 1701432000,
  "model": "anthropic.claude-3-5-haiku-20241022-v1:0",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "According to the documentation, our refund policy allows...\n\n**Sources:**\n[1] Document: s3://docs/refund-policy.pdf\n    Excerpt: \"Refunds are processed within 5-7 business days...\""
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 150,
    "total_tokens": 175
  },
  "kb_metadata": {
    "knowledge_base_used": true,
    "citations_count": 2,
    "session_id": "session-abc123"
  }
}
```

## CLI Reference

### Knowledge Base Commands

The CLI provides a dedicated `kb` command group:

```bash
# List all knowledge bases
accs kb list [--max-results 10]

# Get knowledge base details
accs kb get KB_ID

# Query a knowledge base
accs kb query KB_ID "your question here" [--max-results 5]

# Interactive chat with knowledge base
accs kb chat KB_ID [--model MODEL] [--session SESSION_ID] [--session-name NAME]
```

### Examples

```bash
# List knowledge bases with more results
accs kb list --max-results 20

# Get detailed info about a specific KB
accs kb get kb-1234567890abcdef

# Query for specific information
accs kb query kb-1234567890abcdef "How do I process returns?" --max-results 3

# Start an interactive RAG chat session
accs kb chat kb-1234567890abcdef \
  --model anthropic.claude-3-5-haiku-20241022-v1:0 \
  --session-name "Customer Support Chat"

# Continue an existing session
accs kb chat kb-1234567890abcdef --session existing-session-id
```

## Auto-Detection Features

The system can automatically detect when to use Knowledge Base functionality:

### Detection Triggers

**Explicit Keywords:**
- "search", "find", "lookup", "retrieve"
- "according to", "based on", "from the document"
- "what does [document/KB] say about"

**Question Patterns:**
- "What does the documentation mention about..."
- "According to our policies..."
- "Find information about..."
- "Search for details on..."

**Context Indicators:**
- File IDs present in request
- Previous mentions of documents/knowledge in conversation
- Follow-up questions in document-heavy conversations

### Confidence Scoring

The system calculates confidence scores (0.0-1.0) for retrieval intent:

- **0.7-1.0**: High confidence - triggers direct RAG
- **0.4-0.7**: Medium confidence - context augmentation
- **0.0-0.4**: Low confidence - regular chat

### Smart Routing

Based on query analysis, the system chooses between:

1. **Direct RAG**: Uses Bedrock's native retrieve-and-generate
   - Best for simple factual questions
   - Provides built-in citations
   - High retrieval confidence

2. **Context Augmentation**: Retrieves context and enhances the prompt
   - Better for complex reasoning
   - Allows model flexibility
   - Preserves conversation flow

3. **Regular Chat**: No knowledge base involvement
   - For general conversation
   - Creative tasks
   - Questions outside KB scope

## Configuration

### Environment Variables

```bash
# Required AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=your-profile
# OR
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Optional: Role-based authentication
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/BedrockRole
AWS_EXTERNAL_ID=optional-external-id
AWS_ROLE_SESSION_NAME=kb-session

# Optional: Default Knowledge Base
DEFAULT_KNOWLEDGE_BASE_ID=kb-1234567890abcdef

# Optional: Auto-KB Detection
ENABLE_AUTO_KB=true
AUTO_KB_CONFIDENCE_THRESHOLD=0.5
```

### Server Configuration

In your server configuration, you can set default behavior:

```python
# If using programmatically
from open_bedrock_server.services.knowledge_base_service import get_knowledge_base_service

kb_service = get_knowledge_base_service(
    AWS_REGION="us-east-1",
    AWS_PROFILE="your-profile",
    validate_credentials=True
)
```

## Best Practices

### 1. Knowledge Base Design

**Data Organization:**
- Use clear, descriptive document titles
- Include metadata for better retrieval
- Organize content hierarchically
- Keep documents focused on specific topics

**Content Optimization:**
- Write clear, concise content
- Use consistent terminology
- Include relevant keywords
- Structure information logically

### 2. Query Optimization

**Effective Queries:**
- Be specific and clear
- Use domain-relevant terms
- Ask focused questions
- Provide sufficient context

**Poor Queries:**
- Overly broad questions
- Vague or ambiguous terms
- Questions outside KB scope
- Very short or generic queries

### 3. Integration Patterns

**API Integration:**
```python
# Explicit KB usage
response = client.chat.completions.create(
    model="anthropic.claude-3-5-haiku-20241022-v1:0",
    messages=[
        {"role": "user", "content": "What's our return policy?"}
    ],
    knowledge_base_id="kb-123456",
    auto_kb=True,
    citation_format="openai"
)

# Auto-detection mode
response = client.chat.completions.create(
    model="anthropic.claude-3-5-haiku-20241022-v1:0",
    messages=[
        {"role": "user", "content": "Find documentation about refunds"}
    ],
    auto_kb=True
)
```

**CLI Integration:**
```bash
# For customer support workflows
accs kb chat kb-support-docs \
  --session-name "Customer-$(date +%Y%m%d)" \
  --model anthropic.claude-3-5-haiku-20241022-v1:0

# For documentation queries
accs kb query kb-tech-docs "API rate limits" --max-results 3
```

## Troubleshooting

### Common Issues

**1. "Knowledge base not found" Error**
- Verify the KB ID is correct
- Check AWS permissions for Bedrock Agent
- Ensure KB is in the same region as your configuration

**2. "No results found" for Queries**
- Check if data sources are synced
- Verify query relevance to KB content
- Try broader or different search terms
- Check retrieval configuration

**3. Auto-detection Not Working**
- Enable auto_kb parameter
- Use more explicit retrieval language
- Check confidence threshold settings
- Verify KB ID is provided when needed

**4. Citations Not Appearing**
- Set citation_format to "openai"
- Verify direct RAG is being used
- Check response metadata
- Ensure sources have proper metadata

### Debug Mode

Enable debug logging to troubleshoot:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in .env file
LOG_LEVEL=DEBUG
```

Check logs for:
- KB detection decisions
- Retrieval queries generated
- Confidence scores
- Error details

### Health Checks

Verify service health:

```bash
# API health check
curl http://localhost:8000/v1/knowledge-bases/health

# CLI list (tests connectivity)
accs kb list --max-results 1
```

## Advanced Usage

### Custom Retrieval Configuration

```json
{
  "model": "anthropic.claude-3-5-haiku-20241022-v1:0",
  "messages": [...],
  "knowledge_base_id": "kb-123456",
  "retrieval_config": {
    "vectorSearchConfiguration": {
      "numberOfResults": 10,
      "overrideSearchType": "HYBRID"
    }
  }
}
```

### Session Management

For conversational RAG:

```python
# Maintain session across requests
session_id = None
for user_input in conversation:
    response = kb_service.retrieve_and_generate(
        query=user_input,
        knowledge_base_id="kb-123456",
        model_arn="arn:aws:bedrock:...",
        session_id=session_id  # Maintains conversation context
    )
    session_id = response.session_id
```

### Batch Processing

For processing multiple queries:

```python
import asyncio

async def process_queries(queries, kb_id):
    tasks = []
    for query in queries:
        task = kb_service.retrieve(
            KnowledgeBaseQueryRequest(
                query=query,
                knowledgeBaseId=kb_id,
                maxResults=5
            )
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return results
```

## Migration and Updates

### Upgrading from Previous Versions

If upgrading from a version without Knowledge Base support:

1. **Update Configuration:**
   ```bash
   # Add new environment variables
   accs config set AWS_REGION us-east-1
   accs config set DEFAULT_KNOWLEDGE_BASE_ID your-kb-id
   ```

2. **Test Connectivity:**
   ```bash
   accs kb list
   ```

3. **Update Client Code:**
   ```python
   # Old way
   response = client.chat.completions.create(...)
   
   # New way with KB
   response = client.chat.completions.create(
       ...,
       knowledge_base_id="kb-123456",
       auto_kb=True
   )
   ```

### Backward Compatibility

The Knowledge Base integration is fully backward compatible:
- Existing API calls work unchanged
- New parameters are optional
- Default behavior remains the same
- No breaking changes to existing functionality

## Support and Contributing

### Getting Help

- **Documentation**: Check this guide and API reference
- **CLI Help**: Use `accs kb --help` for command help
- **Logs**: Enable DEBUG logging for detailed troubleshooting
- **Issues**: Report issues with detailed logs and reproduction steps

### Contributing

To contribute to Knowledge Base functionality:

1. **Follow Architecture**: Use existing patterns for services and models
2. **Add Tests**: Include unit tests for new features
3. **Update Docs**: Update this documentation for new features
4. **Maintain Compatibility**: Ensure backward compatibility

See the main development guide for detailed contribution guidelines. 