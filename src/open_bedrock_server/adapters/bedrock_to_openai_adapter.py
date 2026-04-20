import logging
from collections.abc import AsyncGenerator
from typing import Any

from ..core.bedrock_models import (
    BedrockClaudeRequest,
    BedrockClaudeResponse,
    BedrockClaudeStreamChunk,
    BedrockContentBlock,
    BedrockTitanRequest,
    BedrockTitanResponse,
    BedrockTitanStreamChunk,
    BedrockToolChoice,
)
from ..core.exceptions import LLMIntegrationError
from ..core.models import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Message,
)
from .base_adapter import BaseLLMAdapter
from .openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)


class BedrockToOpenAIAdapter(BaseLLMAdapter):
    """Adapter that accepts Bedrock format and converts to OpenAI"""

    def __init__(self, openai_model_id: str, **kwargs):
        super().__init__(openai_model_id, **kwargs)
        self.openai_model_id = openai_model_id
        self._openai_adapter = None
        self._openai_adapter_kwargs = kwargs
        logger.info(
            f"BedrockToOpenAIAdapter initialized for OpenAI model: {self.openai_model_id}"
        )

    @property
    def openai_adapter(self) -> OpenAIAdapter:
        """Lazily initialize OpenAIAdapter only when needed for API calls."""
        if self._openai_adapter is None:
            self._openai_adapter = OpenAIAdapter(
                model_id=self.openai_model_id, **self._openai_adapter_kwargs
            )
        return self._openai_adapter

    def convert_bedrock_to_openai_request(
        self, bedrock_request: BedrockClaudeRequest | BedrockTitanRequest
    ) -> ChatCompletionRequest:
        """Convert Bedrock format request to OpenAI format"""
        if isinstance(bedrock_request, BedrockClaudeRequest):
            return self._convert_claude_to_openai(bedrock_request)
        elif isinstance(bedrock_request, BedrockTitanRequest):
            return self._convert_titan_to_openai(bedrock_request)
        else:
            raise ValueError(
                f"Unsupported Bedrock request type: {type(bedrock_request)}"
            )

    def _convert_claude_to_openai(
        self, claude_request: BedrockClaudeRequest
    ) -> ChatCompletionRequest:
        """Convert Claude format to OpenAI format"""
        messages = []

        # Add system message if present
        if claude_request.system:
            messages.append(Message(role="system", content=claude_request.system))

        # Convert Claude messages to OpenAI format
        for bedrock_msg in claude_request.messages:
            openai_content = self._convert_bedrock_content_to_openai(
                bedrock_msg.content
            )
            messages.append(Message(role=bedrock_msg.role, content=openai_content))

        # Ensure we have at least one message
        if not messages:
            # This should not happen with valid Bedrock requests, but add safeguard
            logger.warning("No messages found in Bedrock Claude request, adding default user message")
            messages.append(Message(role="user", content="Hello"))

        # Convert tools if present
        openai_tools = None
        if claude_request.tools:
            openai_tools = []
            for tool in claude_request.tools:
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.input_schema,
                        },
                    }
                )

        # Convert tool choice
        openai_tool_choice = None
        if claude_request.tool_choice:
            if isinstance(claude_request.tool_choice, str):
                openai_tool_choice = claude_request.tool_choice
            elif isinstance(claude_request.tool_choice, BedrockToolChoice):
                if claude_request.tool_choice.type in ["auto", "any"]:
                    openai_tool_choice = claude_request.tool_choice.type
                elif claude_request.tool_choice.type == "tool":
                    openai_tool_choice = {
                        "type": "function",
                        "function": {"name": claude_request.tool_choice.name},
                    }

        return ChatCompletionRequest(
            model=self.openai_model_id,
            messages=messages,
            max_tokens=claude_request.max_tokens,
            temperature=claude_request.temperature,
            tools=openai_tools,
            tool_choice=openai_tool_choice,
        )

    def _convert_titan_to_openai(
        self, titan_request: BedrockTitanRequest
    ) -> ChatCompletionRequest:
        """Convert Titan format to OpenAI format"""
        # Titan uses simple inputText, convert to user message
        messages = [Message(role="user", content=titan_request.inputText)]

        return ChatCompletionRequest(
            model=self.openai_model_id,
            messages=messages,
            max_tokens=titan_request.textGenerationConfig.maxTokenCount,
            temperature=titan_request.textGenerationConfig.temperature,
        )

    def _convert_bedrock_content_to_openai(
        self, content: str | list[BedrockContentBlock]
    ) -> str | list[dict[str, Any]]:
        """Convert Bedrock content blocks to OpenAI format"""
        if isinstance(content, str):
            return content

        openai_content = []
        for block in content:
            if block.type == "text":
                openai_content.append({"type": "text", "text": block.text})
            elif block.type == "image":
                # Convert Bedrock image format to OpenAI format
                if block.source and block.source.get("type") == "base64":
                    image_url = f"data:{block.source.get('media_type', 'image/jpeg')};base64,{block.source.get('data', '')}"
                    openai_content.append(
                        {"type": "image_url", "image_url": {"url": image_url}}
                    )

        return openai_content

    def convert_openai_to_bedrock_response(
        self, openai_response: ChatCompletionResponse, original_format: str
    ) -> BedrockClaudeResponse | BedrockTitanResponse:
        """Convert OpenAI response back to Bedrock format"""
        if original_format.lower() == "claude":
            return self._convert_openai_to_claude_response(openai_response)
        elif original_format.lower() == "titan":
            return self._convert_openai_to_titan_response(openai_response)
        else:
            raise ValueError(f"Unsupported original format: {original_format}")

    def _convert_openai_to_claude_response(
        self, openai_response: ChatCompletionResponse
    ) -> BedrockClaudeResponse:
        """Convert OpenAI response to Claude format"""
        if not openai_response.choices:
            raise LLMIntegrationError("OpenAI response has no choices")

        choice = openai_response.choices[0]
        message = choice.message

        # Convert content to Claude format
        content_blocks = []
        if message.content:
            content_blocks.append(
                BedrockContentBlock(type="text", text=message.content)
            )

        # Map finish reasons
        finish_reason_map = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
            "content_filter": "stop_sequence",
        }
        stop_reason = finish_reason_map.get(choice.finish_reason, "end_turn")

        # Extract usage information
        usage = {}
        if openai_response.usage:
            usage = {
                "input_tokens": openai_response.usage.prompt_tokens,
                "output_tokens": openai_response.usage.completion_tokens or 0,
            }

        return BedrockClaudeResponse(
            id=openai_response.id,
            role="assistant",
            content=content_blocks,
            model=openai_response.model,
            stop_reason=stop_reason,
            usage=usage,
        )

    def _convert_openai_to_titan_response(
        self, openai_response: ChatCompletionResponse
    ) -> BedrockTitanResponse:
        """Convert OpenAI response to Titan format"""
        if not openai_response.choices:
            raise LLMIntegrationError("OpenAI response has no choices")

        choice = openai_response.choices[0]
        message = choice.message

        # Map finish reasons
        finish_reason_map = {
            "stop": "FINISH",
            "length": "LENGTH",
            "content_filter": "CONTENT_FILTERED",
        }
        completion_reason = finish_reason_map.get(choice.finish_reason, "FINISH")

        # Create Titan result
        result = {
            "tokenCount": openai_response.usage.completion_tokens
            if openai_response.usage
            else 0,
            "outputText": message.content or "",
            "completionReason": completion_reason,
        }

        return BedrockTitanResponse(
            inputTextTokenCount=openai_response.usage.prompt_tokens
            if openai_response.usage
            else 0,
            results=[result],
        )

    # Required abstract methods from BaseLLMAdapter
    def convert_to_provider_request(self, request: ChatCompletionRequest) -> Any:
        """This adapter works in reverse - converts Bedrock to OpenAI, not the other way"""
        return self.openai_adapter.convert_to_provider_request(request)

    def convert_from_provider_response(
        self, provider_response: Any
    ) -> ChatCompletionResponse:
        """Convert provider response using the OpenAI adapter"""
        return self.openai_adapter.convert_from_provider_response(provider_response)

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Process chat completion using the OpenAI adapter"""
        return await self.openai_adapter.chat_completion(request)

    def convert_from_provider_stream_chunk(
        self, provider_chunk: Any, original_request: ChatCompletionRequest
    ) -> ChatCompletionChunk:
        """Convert streaming chunk using the OpenAI adapter"""
        return self.openai_adapter.convert_from_provider_stream_chunk(
            provider_chunk, original_request
        )

    async def stream_chat_completion(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Process streaming chat completion using the OpenAI adapter"""
        async for chunk in self.openai_adapter.stream_chat_completion(request):
            yield chunk

    # Bedrock-specific methods
    async def chat_completion_bedrock(
        self,
        bedrock_request: BedrockClaudeRequest | BedrockTitanRequest,
        original_format: str,
    ) -> BedrockClaudeResponse | BedrockTitanResponse:
        """Process Bedrock format request and return Bedrock format response"""
        # Convert Bedrock request to OpenAI format
        openai_request = self.convert_bedrock_to_openai_request(bedrock_request)

        # Process using OpenAI adapter
        openai_response = await self.openai_adapter.chat_completion(openai_request)

        # Convert back to Bedrock format
        return self.convert_openai_to_bedrock_response(openai_response, original_format)

    async def stream_chat_completion_bedrock(
        self,
        bedrock_request: BedrockClaudeRequest | BedrockTitanRequest,
        original_format: str,
    ) -> AsyncGenerator[BedrockClaudeStreamChunk | BedrockTitanStreamChunk, None]:
        """Process streaming Bedrock format request and return Bedrock format chunks"""
        # Convert Bedrock request to OpenAI format
        openai_request = self.convert_bedrock_to_openai_request(bedrock_request)

        # Process streaming using OpenAI adapter
        async for openai_chunk in self.openai_adapter.stream_chat_completion(
            openai_request
        ):
            # Convert OpenAI chunk to Bedrock format
            bedrock_chunk = self._convert_openai_chunk_to_bedrock(
                openai_chunk, original_format
            )
            if bedrock_chunk:
                yield bedrock_chunk

    def _convert_openai_chunk_to_bedrock(
        self, openai_chunk: ChatCompletionChunk, original_format: str
    ) -> BedrockClaudeStreamChunk | BedrockTitanStreamChunk | None:
        """Convert OpenAI streaming chunk to Bedrock format"""
        if not openai_chunk.choices:
            return None

        choice = openai_chunk.choices[0]
        delta = choice.delta

        if original_format.lower() == "claude":
            return BedrockClaudeStreamChunk(
                type="content_block_delta",
                index=choice.index,
                delta={"text": delta.content} if delta.content else {},
            )
        elif original_format.lower() == "titan":
            return BedrockTitanStreamChunk(
                outputText=delta.content or "", index=choice.index
            )

        return None
