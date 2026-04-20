import json
import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

# Import custom exceptions from the service layer and core
from src.open_bedrock_server.core.exceptions import (
    ConfigurationError,
    LLMIntegrationError,
    ModelNotFoundError,
    ServiceApiError,
    ServiceAuthenticationError,
    ServiceModelNotFoundError,
    ServiceUnavailableError,
)
from src.open_bedrock_server.core.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from src.open_bedrock_server.services.file_processing_service import (
    get_file_processing_service,
)
from src.open_bedrock_server.services.file_service import (
    get_file_service,
)
from src.open_bedrock_server.services.knowledge_base_integration_service import (
    get_knowledge_base_integration_service,
)
from src.open_bedrock_server.services.llm_service_factory import (
    LLMServiceFactory,
)

from ...adapters.bedrock_to_openai_adapter import BedrockToOpenAIAdapter
from ...core.bedrock_models import BedrockClaudeRequest, BedrockTitanRequest
from ...utils.request_detector import RequestFormat, RequestFormatDetector

# Imports for unified logic
from ..middleware.auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


# Helper function to determine target Bedrock type
def get_target_bedrock_type(target_format: str) -> str | None:
    if "claude" in target_format.lower():
        return "claude"
    if "titan" in target_format.lower():
        return "titan"
    return None


# Service retrieval logic
def get_service_and_format_details(
    request_data: dict[str, Any], target_format_query: str | None = None
):
    detected_input_format = RequestFormatDetector.detect_format(request_data)
    logger.debug(f"Detected input format: {detected_input_format}")

    model_id = None
    if detected_input_format == RequestFormat.OPENAI:
        model_id = request_data.get("model")
    elif detected_input_format == RequestFormat.BEDROCK_CLAUDE:
        model_id = request_data.get("model") or request_data.get("model_id")
    elif detected_input_format == RequestFormat.BEDROCK_TITAN:
        model_id = request_data.get("model")

    if not model_id:
        model_id = request_data.get("model")  # Generic fallback
        if not model_id:
            raise ModelNotFoundError(
                "Could not determine model_id from request for routing."
            )

    logger.debug(f"Extracted model_id for routing: {model_id}")

    service = LLMServiceFactory.get_service_for_model(model_id)
    actual_provider = service.provider_name
    logger.debug(
        f"Service obtained for model_id '{model_id}': Provider '{actual_provider}'"
    )

    # Determine target_format_enum based on query, provider, and input
    target_format_enum = RequestFormat.OPENAI  # Default output
    if target_format_query:
        if "claude" in target_format_query.lower():
            target_format_enum = RequestFormat.BEDROCK_CLAUDE
        elif "titan" in target_format_query.lower():
            target_format_enum = RequestFormat.BEDROCK_TITAN
        elif "openai" in target_format_query.lower():
            target_format_enum = RequestFormat.OPENAI
        else:
            logger.warning(
                f"Unsupported target_format query: {target_format_query}. Defaulting to OpenAI."
            )

    logger.debug(
        f"Input format: {detected_input_format}, Actual provider: {actual_provider}, Target output format: {target_format_enum.value}"
    )

    return service, model_id, detected_input_format, target_format_enum


@router.post(
    "/v1/chat/completions", dependencies=[Depends(verify_api_key)], response_model=None
)
async def unified_chat_completions(
    request_data: dict[str, Any],
    target_format: str | None = Query(
        None,
        description="Target response format: openai, bedrock_claude, bedrock_titan. If not specified, defaults to OpenAI or source format if applicable.",
        alias="target_format",
    ),
):
    """
    Unified OpenAI-compatible chat completions endpoint.

    Handles both streaming and non-streaming requests based on the 'stream' parameter.
    Routes requests based on model_id and supports format conversion.
    """
    try:
        (
            compute_service,
            actual_model_id_for_compute,
            input_request_format,
            target_format_enum,
        ) = get_service_and_format_details(request_data, target_format)

        # Parse the request into OpenAI DTO format
        openai_dto_request: ChatCompletionRequest
        if input_request_format == RequestFormat.OPENAI:
            try:
                # Add debug logging to help identify empty messages issues
                messages_data = request_data.get("messages", [])
                logger.debug(f"Parsing OpenAI request with {len(messages_data)} messages: {messages_data}")
                
                openai_dto_request = ChatCompletionRequest(**request_data)
            except ValidationError as e:
                logger.error(f"Validation error parsing OpenAI request: {e}")
                logger.error(f"Request data: {request_data}")
                
                # Provide more specific error for empty messages
                if "messages" in str(e) and ("too_short" in str(e) or "must not be empty" in str(e)):
                    messages_count = len(request_data.get("messages", []))
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error": {
                                "type": "validation_error",
                                "message": f"The 'messages' field must contain at least 1 message, but received {messages_count} messages.",
                                "code": "empty_messages",
                                "details": str(e)
                            }
                        }
                    )
                
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid OpenAI request format: {str(e)}",
                )
            except Exception as e:
                logger.error(f"Error parsing OpenAI request: {e}")
                logger.error(f"Request data: {request_data}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid OpenAI request format: {str(e)}",
                )
        elif input_request_format in [
            RequestFormat.BEDROCK_CLAUDE,
            RequestFormat.BEDROCK_TITAN,
        ]:
            try:
                bedrock_request_model = (
                    BedrockClaudeRequest
                    if input_request_format == RequestFormat.BEDROCK_CLAUDE
                    else BedrockTitanRequest
                )
                bedrock_request = bedrock_request_model(**request_data)
                adapter = BedrockToOpenAIAdapter(
                    openai_model_id=actual_model_id_for_compute
                )
                openai_dto_request = adapter.convert_bedrock_to_openai_request(
                    bedrock_request
                )
            except Exception as e:
                logger.error(f"Error converting Bedrock request to OpenAI DTO: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid Bedrock request or conversion error: {str(e)}",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported input request format: {input_request_format}",
            )

        # Ensure model matches the one determined for compute
        if openai_dto_request.model != actual_model_id_for_compute:
            logger.warning(
                f"Request model '{openai_dto_request.model}' overridden to '{actual_model_id_for_compute}' by routing logic."
            )
            openai_dto_request.model = actual_model_id_for_compute

        # Initialize Knowledge Base integration service
        kb_integration_service = get_knowledge_base_integration_service()

        # Check if Knowledge Base functionality should be used
        kb_id = getattr(
            openai_dto_request, "knowledge_base_id", None
        ) or kb_integration_service.detector.extract_knowledge_base_id_from_request(
            request_data
        )
        should_use_direct_rag = await kb_integration_service.should_use_direct_rag(
            openai_dto_request, kb_id
        )

        # Handle direct RAG requests (using Bedrock's native retrieve-and-generate)
        if should_use_direct_rag and kb_id:
            try:
                # Convert model ID to ARN for Bedrock
                model_arn = f"arn:aws:bedrock:us-east-1::foundation-model/{actual_model_id_for_compute}"

                # Process using native RAG
                rag_response = await kb_integration_service.process_rag_request(
                    openai_dto_request, kb_id, model_arn, request_data
                )

                # Convert to OpenAI format and return
                openai_response = kb_integration_service.convert_rag_response_to_openai(
                    rag_response, openai_dto_request
                )
                return openai_response

            except Exception as e:
                logger.error(
                    f"Direct RAG processing failed, falling back to regular chat: {e}"
                )
                # Continue with regular processing

        # Enhance request with Knowledge Base context (if applicable)
        try:
            openai_dto_request = await kb_integration_service.enhance_chat_request(
                openai_dto_request, request_data
            )
        except Exception as e:
            logger.error(
                f"Knowledge Base enhancement failed, continuing with original request: {e}"
            )

        # Process files if file_ids are provided
        if hasattr(openai_dto_request, "file_ids") and openai_dto_request.file_ids:
            logger.debug(
                f"Processing {len(openai_dto_request.file_ids)} files for context"
            )

            try:
                file_context = await process_files_for_context(
                    openai_dto_request.file_ids
                )

                if file_context:
                    # Add file context to the first user message or create a system message
                    if openai_dto_request.messages:
                        # Find the first user message and prepend the file context
                        for i, message in enumerate(openai_dto_request.messages):
                            if message.role == "user":
                                openai_dto_request.messages[
                                    i
                                ].content = f"{file_context}\n\n{message.content}"
                                break
                        else:
                            # No user message found, add as system message at the beginning
                            from src.open_bedrock_server.core.models import (
                                Message,
                            )

                            system_message = Message(
                                role="system", content=file_context
                            )
                            openai_dto_request.messages.insert(0, system_message)

                    logger.debug(
                        f"Added file context to request ({len(file_context)} characters)"
                    )

            except Exception as e:
                logger.error(
                    f"Error processing files, continuing without file context: {e}"
                )
                # Continue with the request even if file processing fails

        # Check if this is a streaming request
        is_streaming = openai_dto_request.stream or False

        if is_streaming:
            # Handle streaming response
            logger.debug(
                f"Processing streaming request for model: {actual_model_id_for_compute}"
            )

            async def generate_stream_response():
                try:
                    response = await compute_service.chat_completion_with_request(
                        openai_dto_request
                    )

                    # For streaming endpoints, we expect an async generator
                    if not (
                        hasattr(response, "__aiter__")
                        and hasattr(response, "__anext__")
                    ):
                        logger.error(
                            "Received non-streaming response from streaming service call"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Service configuration error: non-streaming response from streaming endpoint",
                        )

                    openai_stream = response

                    target_bedrock_type_for_conversion = None
                    if (
                        target_format_enum == RequestFormat.BEDROCK_CLAUDE
                        or target_format_enum == RequestFormat.BEDROCK_TITAN
                    ):
                        target_bedrock_type_for_conversion = get_target_bedrock_type(
                            target_format_enum.value
                        )
                        if not target_bedrock_type_for_conversion:
                            logger.error(
                                f"Streaming: Could not determine target Bedrock type from format enum: {target_format_enum.value}. No conversion will be applied."
                            )

                    # Initialize adapter with the model determined for compute
                    response_adapter = BedrockToOpenAIAdapter(
                        openai_model_id=actual_model_id_for_compute
                    )
                    first_chunk_processed = False

                    async for chunk in openai_stream:
                        # Update adapter if the first chunk from OpenAI contains a more specific model ID
                        if (
                            not first_chunk_processed
                            and chunk.model
                            and response_adapter.openai_model_id != chunk.model
                        ):
                            response_adapter = BedrockToOpenAIAdapter(
                                openai_model_id=chunk.model
                            )
                        first_chunk_processed = True

                        if target_bedrock_type_for_conversion:
                            bedrock_chunk = (
                                response_adapter._convert_openai_chunk_to_bedrock(
                                    chunk,
                                    original_format=target_bedrock_type_for_conversion,
                                )
                            )
                            if bedrock_chunk:
                                yield f"data: {json.dumps(bedrock_chunk.model_dump(exclude_none=True))}\n\n"
                        else:  # Yield OpenAI chunk
                            yield f"data: {json.dumps(chunk.model_dump(exclude_none=True))}\n\n"

                    yield "data: [DONE]\n\n"

                except HTTPException:
                    raise
                except Exception as e_stream:
                    logger.error(
                        f"Error during stream generation: {e_stream}", exc_info=True
                    )
                    error_payload = {
                        "error": {
                            "message": f"Streaming error: {str(e_stream)}",
                            "type": type(e_stream).__name__,
                        }
                    }
                    yield f"data: {json.dumps(error_payload)}\n\n"

            return StreamingResponse(
                generate_stream_response(), media_type="text/event-stream"
            )

        else:
            # Handle non-streaming response
            logger.debug(
                f"Processing non-streaming request for model: {actual_model_id_for_compute}"
            )

            response = await compute_service.chat_completion_with_request(
                openai_dto_request
            )

            # For non-streaming endpoints, we expect a ChatCompletionResponse object
            if hasattr(response, "__aiter__") and hasattr(response, "__anext__"):
                logger.error(
                    "Received streaming response from non-streaming service call"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error: streaming response from non-streaming endpoint",
                )

            # Ensure we have a proper ChatCompletionResponse object
            if not hasattr(response, "id") or not hasattr(response, "choices"):
                logger.error(f"Invalid response type from service: {type(response)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid response format from service",
                )

            openai_response_dto: ChatCompletionResponse = response

            # Convert response to target format if needed
            if (
                target_format_enum == RequestFormat.BEDROCK_CLAUDE
                or target_format_enum == RequestFormat.BEDROCK_TITAN
            ):
                target_bedrock_type = get_target_bedrock_type(target_format_enum.value)
                if not target_bedrock_type:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Could not determine target Bedrock type from format: {target_format_enum.value}",
                    )

                adapter = BedrockToOpenAIAdapter(
                    openai_model_id=openai_response_dto.model
                )
                bedrock_response = adapter.convert_openai_to_bedrock_response(
                    openai_response_dto, original_format=target_bedrock_type
                )
                return bedrock_response.model_dump(exclude_none=True)
            else:
                # Return OpenAI format
                return openai_response_dto.model_dump(exclude_none=True)

    except ModelNotFoundError as e:
        logger.warning(f"Model not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceAuthenticationError as e:
        logger.error(f"Service Authentication Error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except ServiceModelNotFoundError as e:
        logger.error(f"Service Model Not Found Error: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceUnavailableError as e:
        logger.error(f"Service Unavailable Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        )
    except (ServiceApiError, LLMIntegrationError, ConfigurationError) as e:
        logger.error(f"Service/Integration Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValueError as e:
        logger.warning(f"ValueError in unified endpoint: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Pydantic validation error in unified endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTPExceptions without modification
        raise
    except Exception as e:
        logger.error(f"Unexpected error in unified endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.get("/v1/chat/completions/health")
async def unified_health():
    """Health check for the unified chat completions endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T12:00:00Z",
        "version": "1.0.0",
        "message": "Unified chat completions endpoint operational",
        "supported_input_formats": ["openai", "bedrock_claude", "bedrock_titan"],
        "model_routing": "enabled",
        "streaming_support": "enabled",
        "routing_method": "model_id_based",
    }


async def process_files_for_context(file_ids: list[str] | None) -> str:
    """
    Process uploaded files and return their content as context for the chat completion.

    Args:
        file_ids: List of file IDs to process

    Returns:
        Formatted string containing file contents for context
    """
    if not file_ids:
        return ""

    try:
        file_service = get_file_service()
        file_processing_service = get_file_processing_service()

        file_contexts = []

        for file_id in file_ids:
            try:
                # Get file metadata and content
                metadata = await file_service.get_file_metadata(file_id)
                if not metadata:
                    logger.warning(f"File {file_id} not found, skipping")
                    continue

                content = await file_service.get_file_content(file_id)
                if not content:
                    logger.warning(f"No content found for file {file_id}, skipping")
                    continue

                # Process the file content
                processed_result = await file_processing_service.process_file(
                    content, metadata.content_type, metadata.filename
                )

                if processed_result["success"]:
                    file_contexts.append(
                        f"=== File: {metadata.filename} (ID: {file_id}) ===\n{processed_result['text_content']}\n"
                    )
                else:
                    logger.warning(
                        f"Failed to process file {file_id}: {processed_result.get('error', 'Unknown error')}"
                    )
                    # Still include basic info if processing fails
                    file_contexts.append(
                        f"=== File: {metadata.filename} (ID: {file_id}) ===\n[File content could not be processed: {processed_result.get('error', 'Unknown error')}]\n"
                    )

            except Exception as e:
                logger.error(f"Error processing file {file_id}: {e}")
                file_contexts.append(
                    f"=== File: {file_id} ===\n[Error processing file: {str(e)}]\n"
                )

        if file_contexts:
            return "\n".join(
                [
                    "=== UPLOADED FILES CONTEXT ===",
                    "The following files have been uploaded and their content is provided below for your reference:",
                    "",
                    *file_contexts,
                    "=== END OF FILES CONTEXT ===\n",
                ]
            )
        else:
            return ""

    except Exception as e:
        logger.error(f"Error processing files for context: {e}")
        return f"\n=== FILE PROCESSING ERROR ===\nError processing uploaded files: {str(e)}\n=== END ERROR ===\n"
