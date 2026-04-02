import logging
from datetime import datetime
from typing import Any

from ..core.exceptions import (
    ConfigurationError,
    ServiceApiError,
)
from ..core.knowledge_base_models import (
    Citation,
    KnowledgeBaseQueryRequest,
    RetrievalResult,
    RetrieveAndGenerateRequest,
    RetrieveAndGenerateResponse,
)
from ..core.models import ChatCompletionRequest, Message
from ..services.knowledge_base_service import get_knowledge_base_service
from ..utils.knowledge_base_detector import KnowledgeBaseDetector

logger = logging.getLogger(__name__)


class KnowledgeBaseIntegrationService:
    """
    Service for integrating Knowledge Base functionality into chat completions.

    Provides:
    - Smart routing between regular chat and RAG-enhanced responses
    - Automatic detection of retrieval intent
    - Citation formatting and integration
    - Context augmentation from knowledge bases
    """

    def __init__(self):
        try:
            self.kb_service = get_knowledge_base_service()
        except ConfigurationError as e:
            logger.warning(
                "Knowledge Base service unavailable: %s", e, exc_info=True
            )
            self.kb_service = None
        self.detector = KnowledgeBaseDetector()

    async def enhance_chat_request(
        self,
        request: ChatCompletionRequest,
        request_data: dict[str, Any] | None = None,
    ) -> ChatCompletionRequest:
        """
        Enhance a chat completion request with Knowledge Base context if applicable.

        Args:
            request: The original chat completion request
            request_data: Raw request data for additional parameter extraction

        Returns:
            ChatCompletionRequest: Enhanced request with KB context if applicable
        """
        if not self.kb_service:
            return request

        try:
            # Extract KB parameters from request or request_data
            kb_id = request.knowledge_base_id
            auto_kb = request.auto_kb or False

            if request_data:
                kb_id = kb_id or self.detector.extract_knowledge_base_id_from_request(
                    request_data
                )
                auto_kb = auto_kb or request_data.get("auto_kb", False)

            # Determine if KB should be used
            should_use_kb = self.detector.should_use_knowledge_base(
                request=request, knowledge_base_id=kb_id, auto_kb=auto_kb
            )

            if not should_use_kb:
                logger.debug("Knowledge Base not needed for this request")
                return request

            if not kb_id:
                logger.warning("Knowledge Base usage detected but no KB ID provided")
                return request

            # Generate knowledge base query
            kb_query = self.detector.suggest_knowledge_base_query(request.messages)
            if not kb_query:
                logger.debug("Could not generate effective KB query")
                return request

            logger.info(f"Enhancing request with KB {kb_id}, query: {kb_query}")

            # Retrieve relevant context from knowledge base
            retrieval_request = KnowledgeBaseQueryRequest(
                query=kb_query,
                knowledgeBaseId=kb_id,
                maxResults=request.retrieval_config.get("max_results", 5)
                if request.retrieval_config
                else 5,
                retrievalConfiguration=request.retrieval_config,
            )

            retrieval_response = await self.kb_service.retrieve(retrieval_request)

            if not retrieval_response.retrievalResults:
                logger.debug("No relevant results found in knowledge base")
                return request

            # Enhance the request with retrieved context
            enhanced_request = await self._augment_request_with_context(
                request, retrieval_response.retrievalResults, kb_query
            )

            return enhanced_request

        except Exception as e:
            logger.error(f"Error enhancing chat request with KB: {e}")
            # Return original request on error to maintain service availability
            return request

    async def _augment_request_with_context(
        self,
        request: ChatCompletionRequest,
        retrieval_results: list[RetrievalResult],
        query: str,
    ) -> ChatCompletionRequest:
        """
        Augment the chat request with retrieved knowledge base context.

        Args:
            request: Original chat completion request
            retrieval_results: Results from knowledge base retrieval
            query: The query used for retrieval

        Returns:
            ChatCompletionRequest: Request with augmented context
        """
        # Format the retrieved context
        context_parts = []
        for i, result in enumerate(retrieval_results[:5], 1):  # Limit to top 5 results
            context_parts.append(f"Context {i}: {result.content}")

            # Add metadata if available
            if result.metadata:
                source_info = []
                if "source" in result.metadata:
                    source_info.append(f"Source: {result.metadata['source']}")
                if "title" in result.metadata:
                    source_info.append(f"Title: {result.metadata['title']}")
                if source_info:
                    context_parts.append(f"({', '.join(source_info)})")

        context_text = "\n\n".join(context_parts)

        # Create context prompt
        context_prompt = f"""Based on the following relevant information from the knowledge base, please answer the user's question:

{context_text}

Instructions:
- Use the provided context to answer the user's question accurately
- If the context doesn't contain relevant information, mention that the information isn't available in the knowledge base
- Cite specific context sections when referencing information (e.g., "According to Context 1...")
- Be concise but comprehensive in your response

User's question: {query}"""

        # Clone the request and modify messages
        enhanced_messages = []

        # Add context as a system message if no system message exists
        # Or prepend to existing system message
        has_system_message = any(msg.role == "system" for msg in request.messages)

        if has_system_message:
            for msg in request.messages:
                if msg.role == "system":
                    # Prepend context to existing system message
                    enhanced_content = (
                        f"{context_prompt}\n\n{msg.content}"
                        if msg.content
                        else context_prompt
                    )
                    enhanced_messages.append(
                        Message(role="system", content=enhanced_content)
                    )
                else:
                    enhanced_messages.append(msg)
        else:
            # Add context as new system message
            enhanced_messages.append(Message(role="system", content=context_prompt))
            enhanced_messages.extend(request.messages)

        # Create enhanced request
        enhanced_request = request.model_copy()
        enhanced_request.messages = enhanced_messages

        return enhanced_request

    async def process_rag_request(
        self,
        request: ChatCompletionRequest,
        knowledge_base_id: str,
        model_arn: str,
        request_data: dict[str, Any] | None = None,
    ) -> RetrieveAndGenerateResponse:
        """
        Process a request using Bedrock's native retrieve-and-generate functionality.

        Args:
            request: Chat completion request
            knowledge_base_id: Knowledge Base ID
            model_arn: Model ARN for generation
            request_data: Raw request data

        Returns:
            RetrieveAndGenerateResponse: Native Bedrock RAG response
        """
        try:
            # Extract query from the latest user message
            user_messages = [msg for msg in request.messages if msg.role == "user"]
            if not user_messages:
                raise ServiceApiError("No user messages found for RAG processing")

            query = user_messages[-1].content
            if not query:
                raise ServiceApiError("Empty query in user message")

            # Prepare retrieve and generate request
            rag_request = RetrieveAndGenerateRequest(
                query=query,
                knowledgeBaseId=knowledge_base_id,
                modelArn=model_arn,
                retrievalConfiguration=request.retrieval_config,
                generationConfiguration={
                    "inferenceConfig": {
                        "textInferenceConfig": {
                            "temperature": request.temperature,
                            "maxTokens": request.max_tokens or 1000,
                        }
                    }
                }
                if request.temperature or request.max_tokens
                else None,
            )

            # Execute retrieve and generate
            response = await self.kb_service.retrieve_and_generate(rag_request)

            logger.info(
                f"RAG request processed successfully for KB {knowledge_base_id}"
            )
            return response

        except Exception as e:
            logger.error(f"Error processing RAG request: {e}")
            raise

    def format_citations_for_openai(
        self, response_text: str, citations: list[Citation]
    ) -> str:
        """
        Format Bedrock citations in OpenAI-compatible format.

        Args:
            response_text: Generated response text
            citations: List of Bedrock citations

        Returns:
            str: Response text with formatted citations
        """
        if not citations:
            return response_text

        formatted_response = response_text
        citation_notes = []

        for i, citation in enumerate(citations, 1):
            # Extract citation information
            for ref in citation.retrievedReferences:
                location = ref.get("location", {})
                content = ref.get("content", {}).get("text", "")

                # Extract source information
                source_info = []
                if "s3Location" in location:
                    s3_location = location["s3Location"]
                    source_info.append(f"Document: {s3_location.get('uri', 'Unknown')}")

                if "type" in location:
                    source_info.append(f"Type: {location['type']}")

                citation_notes.append(f"[{i}] {', '.join(source_info)}")

                # Add snippet if available
                if content and len(content) > 50:
                    snippet = content[:100] + "..." if len(content) > 100 else content
                    citation_notes.append(f'    Excerpt: "{snippet}"')

        if citation_notes:
            formatted_response += "\n\n**Sources:**\n" + "\n".join(citation_notes)

        return formatted_response

    def convert_rag_response_to_openai(
        self, rag_response: RetrieveAndGenerateResponse, request: ChatCompletionRequest
    ) -> dict[str, Any]:
        """
        Convert Bedrock RAG response to OpenAI chat completion format.

        Args:
            rag_response: Bedrock retrieve and generate response
            request: Original chat completion request

        Returns:
            Dict[str, Any]: OpenAI-compatible response
        """
        # Format citations based on preference
        response_text = rag_response.output
        if request.citation_format == "openai" and rag_response.citations:
            response_text = self.format_citations_for_openai(
                response_text, rag_response.citations
            )

        # Create OpenAI-compatible response
        openai_response = {
            "id": f"chatcmpl-kb-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(request.messages[-1].content.split())
                if request.messages[-1].content
                else 0,
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(request.messages[-1].content.split())
                + len(response_text.split())
                if request.messages[-1].content
                else len(response_text.split()),
            },
        }

        # Add Knowledge Base specific metadata
        if rag_response.citations or rag_response.sessionId:
            openai_response["kb_metadata"] = {
                "knowledge_base_used": True,
                "citations_count": len(rag_response.citations)
                if rag_response.citations
                else 0,
                "session_id": rag_response.sessionId,
            }

        return openai_response

    async def should_use_direct_rag(
        self, request: ChatCompletionRequest, knowledge_base_id: str | None = None
    ) -> bool:
        """
        Determine if direct RAG (retrieve-and-generate) should be used instead of context augmentation.

        Args:
            request: Chat completion request
            knowledge_base_id: Knowledge Base ID

        Returns:
            bool: True if direct RAG should be used
        """
        # Use direct RAG if:
        # 1. KB ID is explicitly provided
        # 2. High confidence retrieval intent
        # 3. Simple query structure (better for native RAG)

        if not knowledge_base_id or not self.kb_service:
            return False

        confidence = self.detector.get_retrieval_confidence_score(request.messages)

        # High confidence suggests direct RAG
        if confidence > 0.7:
            return True

        # Check for simple factual questions (good for direct RAG)
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if user_messages:
            latest_content = (
                user_messages[-1].content.lower() if user_messages[-1].content else ""
            )
            simple_question_indicators = [
                "what is",
                "who is",
                "when is",
                "where is",
                "how many",
                "define",
            ]
            if any(
                indicator in latest_content for indicator in simple_question_indicators
            ):
                return True

        return False


def get_knowledge_base_integration_service() -> KnowledgeBaseIntegrationService:
    """Get Knowledge Base integration service instance"""
    return KnowledgeBaseIntegrationService()
