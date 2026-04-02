---
title: Files API
nav_order: 9
description: File upload, management, and chat integration API
---

# Files API Documentation

## Overview

The Open Bedrock Server Server provides a comprehensive OpenAI-compatible file management API with S3 backend storage. This allows you to upload, manage, and use files in your chat completions for enhanced AI interactions.

## Features

- **File Upload**: Upload files via multipart form data to S3
- **File Retrieval**: List, get metadata, and download file content  
- **File Processing**: Automatic text extraction from various file types
- **Chat Integration**: Use uploaded files as context in chat completions
- **OpenAI Compatibility**: Full compatibility with OpenAI's files API format
- **S3 Storage**: Reliable, scalable storage with AWS S3
- **Authentication**: AWS credential support (static keys, profiles, roles, web identity)

## API Endpoints

### File Management

#### Upload File
```http
POST /v1/files
Content-Type: multipart/form-data

file: <file_data>
purpose: <purpose_string>
```

#### List Files
```http
GET /v1/files?purpose=<purpose>&limit=<limit>
```

#### Get File Metadata
```http
GET /v1/files/{file_id}
```

#### Download File Content
```http
GET /v1/files/{file_id}/content
```

#### Delete File
```http
DELETE /v1/files/{file_id}
```

### Chat Completions with Files

#### Enhanced Chat Completions
```http
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "claude-3-sonnet",
  "messages": [
    {"role": "user", "content": "Analyze the uploaded data"}
  ],
  "file_ids": ["file-abc123", "file-def456"]
}
```

## Supported File Types

The file processing service supports automatic text extraction from:

- **Text files**: `.txt`, `.md`, `.py`, `.js`, `.html`
- **Structured data**: `.json`, `.csv`, `.xml`
- **Formats**: `text/plain`, `application/json`, `text/csv`, `application/xml`, `text/html`

Unsupported file types are stored but won't be processed for chat completions.

## Configuration

### Environment Variables

```bash
# Required
S3_FILES_BUCKET=your-files-bucket

# AWS Authentication (choose one method)
# Method 1: Static credentials
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Method 2: AWS Profile  
AWS_PROFILE=your-profile

# Method 3: IAM Role (for EC2/ECS)
AWS_ROLE_ARN=arn:aws:iam::account:role/your-role
AWS_EXTERNAL_ID=your-external-id

# Method 4: Web Identity (for EKS/Fargate)
AWS_WEB_IDENTITY_TOKEN_FILE=/var/run/secrets/eks.amazonaws.com/serviceaccount/token
AWS_ROLE_ARN=arn:aws:iam::account:role/your-role

# Optional
AWS_REGION=us-east-1
```

### CLI Configuration

```bash
# Start server with file support
amazon-chat-completions-server \
  --s3-files-bucket your-files-bucket \
  --aws-region us-east-1 \
  --aws-profile your-profile
```

## Usage Examples

### Python Client

#### Basic File Upload and Chat
```python
import requests

# Upload a file
files = {"file": ("data.csv", open("data.csv", "rb"), "text/csv")}
data = {"purpose": "assistants"}
response = requests.post(
    "http://localhost:8000/v1/files", 
    files=files, 
    data=data,
    headers={"Authorization": "Bearer your-api-key"}
)
file_info = response.json()
file_id = file_info["id"]

# Use file in chat completion
chat_request = {
    "model": "claude-3-sonnet",
    "messages": [
        {"role": "user", "content": "Analyze the data in the uploaded CSV file"}
    ],
    "file_ids": [file_id]
}
response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json=chat_request,
    headers={"Authorization": "Bearer your-api-key"}
)
print(response.json()["choices"][0]["message"]["content"])
```

#### File Management
```python
# List all files
response = requests.get(
    "http://localhost:8000/v1/files",
    headers={"Authorization": "Bearer your-api-key"}
)
files = response.json()["data"]

# Get specific file metadata
response = requests.get(
    f"http://localhost:8000/v1/files/{file_id}",
    headers={"Authorization": "Bearer your-api-key"}
)
file_metadata = response.json()

# Download file content
response = requests.get(
    f"http://localhost:8000/v1/files/{file_id}/content",
    headers={"Authorization": "Bearer your-api-key"}
)
file_content = response.content

# Delete file
response = requests.delete(
    f"http://localhost:8000/v1/files/{file_id}",
    headers={"Authorization": "Bearer your-api-key"}
)
```

### cURL Examples

#### Upload File
```bash
curl -X POST "http://localhost:8000/v1/files" \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@data.json" \
  -F "purpose=assistants"
```

#### Chat with File Context
```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-sonnet",
    "messages": [
      {"role": "user", "content": "What insights can you derive from the uploaded data?"}
    ],
    "file_ids": ["file-abc123"]
  }'
```

#### List Files with Filter
```bash
curl "http://localhost:8000/v1/files?purpose=assistants&limit=10" \
  -H "Authorization: Bearer your-api-key"
```

### JavaScript/Node.js

```javascript
// Upload file
const formData = new FormData();
formData.append('file', fs.createReadStream('document.txt'));
formData.append('purpose', 'assistants');

const uploadResponse = await fetch('http://localhost:8000/v1/files', {
  method: 'POST',
  headers: { 'Authorization': 'Bearer your-api-key' },
  body: formData
});
const fileInfo = await uploadResponse.json();

// Use in chat completion  
const chatResponse = await fetch('http://localhost:8000/v1/chat/completions', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer your-api-key',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    model: 'claude-3-sonnet',
    messages: [
      { role: 'user', content: 'Summarize the uploaded document' }
    ],
    file_ids: [fileInfo.id]
  })
});
```

## File Processing

When files are used in chat completions, they undergo automatic processing:

1. **Content Extraction**: Text content is extracted based on file type
2. **Context Formation**: File content is formatted with metadata
3. **Message Integration**: Context is prepended to the first user message
4. **AI Processing**: The LLM receives both the original prompt and file content

### Processing Examples

**Text File Processing:**
```
=== UPLOADED FILES CONTEXT ===
The following files have been uploaded and their content is provided below for your reference:

=== File: document.txt (ID: file-abc123) ===
This is the content of the text file.
Multiple lines are preserved.

=== END OF FILES CONTEXT ===

Original user message content...
```

**JSON File Processing:**
```
=== File: data.json (ID: file-def456) ===
JSON File: data.json
Object at root with 3 keys:
  name: str = "John Doe"
  age: int = 30
  items: list

JSON Content:
{
  "name": "John Doe",
  "age": 30,
  "items": ["a", "b", "c"]
}
```

**CSV File Processing:**
```
=== File: sales.csv (ID: file-ghi789) ===
CSV File: sales.csv
Headers: date, product, quantity, price
Total rows: 100

Row 0 (Headers): date, product, quantity, price
Row 1: 2024-01-01, Widget A, 10, 29.99
Row 2: 2024-01-02, Widget B, 5, 49.99
... and 97 more rows
```

## Response Formats

### File Upload Response
```json
{
  "id": "file-abc123def456",
  "object": "file",
  "bytes": 1024,
  "created_at": 1234567890,
  "filename": "document.txt",
  "purpose": "assistants",
  "status": "processed"
}
```

### File List Response
```json
{
  "object": "list", 
  "data": [
    {
      "id": "file-abc123",
      "object": "file",
      "bytes": 1024,
      "created_at": 1234567890,
      "filename": "document.txt", 
      "purpose": "assistants",
      "status": "processed"
    }
  ]
}
```

### File Deletion Response
```json
{
  "id": "file-abc123",
  "object": "file",
  "deleted": true
}
```

## Error Handling

### Common Error Responses

**File Not Found (404):**
```json
{
  "detail": "File file-nonexistent not found"
}
```

**Invalid File ID Format (422):**
```json
{
  "detail": "Invalid file ID format: invalid-id. File IDs must start with 'file-'"
}
```

**S3 Configuration Error (500):**
```json
{
  "detail": "S3_FILES_BUCKET is not configured. Cannot upload files."
}
```

**File Processing Error:**
Files that fail to process are still stored and usable, but show error context:
```
=== File: document.pdf (ID: file-abc123) ===
[File content could not be processed: Unsupported file type: application/pdf]
```

## Health Checks

### Files Service Health
```bash
curl "http://localhost:8000/v1/files/health"
```

Response:
```json
{
  "status": "healthy",
  "service": "files", 
  "s3_configured": true
}
```

## Best Practices

### File Management
- Use descriptive filenames for better context
- Set appropriate `purpose` values for organization
- Delete unused files to manage storage costs
- Monitor file sizes (large files may impact performance)

### Chat Completions with Files
- Limit file_ids to relevant files only (3-5 files max recommended)
- Use specific prompts that reference the uploaded content
- Consider file processing time for large files
- Handle cases where files may not be processed successfully

### Security
- Ensure proper S3 bucket permissions
- Use least-privilege IAM roles
- Validate file content before upload in production
- Monitor API access logs

## Troubleshooting

### File Upload Issues
1. **Check S3 bucket configuration**
2. **Verify AWS credentials** 
3. **Confirm bucket permissions**
4. **Check file size limits**

### File Processing Issues
1. **Verify file type support**
2. **Check file encoding (use UTF-8 when possible)**
3. **Monitor processing logs**
4. **Handle unsupported types gracefully**

### Integration Issues
1. **Validate file_ids format**
2. **Ensure files exist before chat completion**
3. **Check authentication on both endpoints**
4. **Monitor request/response sizes**

## Limitations

- **File Size**: Large files may impact processing time and memory usage
- **File Types**: Only text-extractable formats are processed for chat context
- **Concurrent Access**: S3 provides eventual consistency
- **Rate Limits**: Subject to AWS S3 rate limits
- **Processing Depth**: Complex file structures may be simplified in processing

For additional support, check the application logs and AWS CloudWatch for detailed error information. 