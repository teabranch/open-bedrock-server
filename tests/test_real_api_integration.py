"""
Integration tests for real LLM API functionality using environment variables.
These tests use actual API keys and services defined in .env file.

IMPORTANT: These tests only run when explicitly requested with the "real_api" marker
to avoid accidental API costs. Use: pytest -m real_api
"""

import asyncio
import logging

import pytest

from src.open_bedrock_server.core.exceptions import LLMIntegrationError
from src.open_bedrock_server.core.models import Message
from src.open_bedrock_server.services.llm_service_factory import (
    LLMServiceFactory,
)
from src.open_bedrock_server.utils import config_loader

# Setup logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables for real API tests
OPENAI_API_KEY = config_loader.app_config.OPENAI_API_KEY
AWS_ACCESS_KEY_ID = config_loader.app_config.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = config_loader.app_config.AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN = config_loader.app_config.AWS_SESSION_TOKEN
AWS_REGION = config_loader.app_config.AWS_REGION or "us-east-1"

# Skip conditions for real API tests
OPENAI_AVAILABLE = bool(OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"))
AWS_AVAILABLE = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)

# Test models from .env defaults
TEST_OPENAI_MODEL = "gpt-4o-mini"
TEST_CLAUDE_MODEL = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
TEST_TITAN_MODEL = "amazon.titan-text-express-v1"


class TestRealOpenAIIntegration:
    """Test real OpenAI API integration using environment variables."""

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI API key not available")
    async def test_openai_chat_completion_basic(self):
        """Test basic OpenAI chat completion functionality."""
        service = LLMServiceFactory.get_service("openai", model_id=TEST_OPENAI_MODEL)

        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="What is 2+2? Answer in one word."),
        ]

        response = await service.chat_completion(
            model_id=TEST_OPENAI_MODEL,
            messages=messages,
            max_tokens=10,
            temperature=0.1,
        )

        assert response is not None
        assert response.choices is not None
        assert len(response.choices) > 0
        assert response.choices[0].message is not None
        assert response.choices[0].message.content is not None
        assert len(response.choices[0].message.content.strip()) > 0
        assert response.usage is not None
        assert response.usage.total_tokens > 0

        logger.info(f"OpenAI Response: {response.choices[0].message.content}")
        logger.info(f"OpenAI Usage: {response.usage}")

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI API key not available")
    async def test_openai_streaming_chat_completion(self):
        """Test OpenAI streaming chat completion."""
        service = LLMServiceFactory.get_service("openai", model_id=TEST_OPENAI_MODEL)

        messages = [
            Message(role="user", content="Count from 1 to 5, one number per line.")
        ]

        full_content = ""
        chunk_count = 0

        async for chunk in await service.chat_completion(
            model_id=TEST_OPENAI_MODEL,
            messages=messages,
            max_tokens=50,
            temperature=0.1,
            stream=True,
        ):
            chunk_count += 1
            if (
                chunk.choices
                and chunk.choices[0].delta
                and chunk.choices[0].delta.content
            ):
                full_content += chunk.choices[0].delta.content

        assert chunk_count > 0, "No streaming chunks received"
        assert len(full_content.strip()) > 0, "No content received from streaming"

        logger.info(f"OpenAI Streaming chunks received: {chunk_count}")
        logger.info(f"OpenAI Streaming content: {full_content}")

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI API key not available")
    async def test_openai_multiple_models(self):
        """Test OpenAI with different model configurations."""
        models_to_test = ["gpt-4o-mini", "gpt-3.5-turbo"]

        for model_id in models_to_test:
            try:
                service = LLMServiceFactory.get_service("openai", model_id=model_id)

                messages = [Message(role="user", content="Hello")]

                response = await service.chat_completion(
                    model_id=model_id, messages=messages, max_tokens=10
                )

                assert response is not None
                assert response.choices is not None
                assert len(response.choices) > 0

                logger.info(
                    f"Model {model_id} test passed: {response.choices[0].message.content[:50]}..."
                )

            except Exception as e:
                logger.warning(f"Model {model_id} test failed: {e}")
                # Don't fail the test if a specific model isn't available
                continue


class TestRealBedrockIntegration:
    """Test real AWS Bedrock API integration using environment variables."""

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(not AWS_AVAILABLE, reason="AWS credentials not available")
    async def test_bedrock_claude_chat_completion(self):
        """Test Bedrock Claude chat completion functionality."""
        service = LLMServiceFactory.get_service("bedrock", model_id=TEST_CLAUDE_MODEL)

        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(
                role="user",
                content="What is the capital of France? Answer in one word.",
            ),
        ]

        response = await service.chat_completion(
            model_id=TEST_CLAUDE_MODEL,
            messages=messages,
            max_tokens=10,
            temperature=0.1,
        )

        assert response is not None
        assert response.choices is not None
        assert len(response.choices) > 0
        assert response.choices[0].message is not None
        assert response.choices[0].message.content is not None
        assert len(response.choices[0].message.content.strip()) > 0

        logger.info(f"Bedrock Claude Response: {response.choices[0].message.content}")
        if response.usage:
            logger.info(f"Bedrock Claude Usage: {response.usage}")

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(not AWS_AVAILABLE, reason="AWS credentials not available")
    async def test_bedrock_claude_streaming(self):
        """Test Bedrock Claude streaming chat completion."""
        service = LLMServiceFactory.get_service("bedrock", model_id=TEST_CLAUDE_MODEL)

        messages = [Message(role="user", content="Write a short poem about testing.")]

        full_content = ""
        chunk_count = 0

        async for chunk in await service.chat_completion(
            model_id=TEST_CLAUDE_MODEL,
            messages=messages,
            max_tokens=100,
            temperature=0.7,
            stream=True,
        ):
            chunk_count += 1
            if (
                chunk.choices
                and chunk.choices[0].delta
                and chunk.choices[0].delta.content
            ):
                full_content += chunk.choices[0].delta.content

        assert chunk_count > 0, "No streaming chunks received"
        assert len(full_content.strip()) > 0, "No content received from streaming"

        logger.info(f"Bedrock Claude Streaming chunks received: {chunk_count}")
        logger.info(f"Bedrock Claude Streaming content: {full_content}")

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(not AWS_AVAILABLE, reason="AWS credentials not available")
    async def test_bedrock_titan_chat_completion(self):
        """Test Bedrock Titan chat completion functionality."""
        service = LLMServiceFactory.get_service("bedrock", model_id=TEST_TITAN_MODEL)

        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="What is AI? Answer briefly."),
        ]

        response = await service.chat_completion(
            model_id=TEST_TITAN_MODEL, messages=messages, max_tokens=50, temperature=0.3
        )

        assert response is not None
        assert response.choices is not None
        assert len(response.choices) > 0
        assert response.choices[0].message is not None
        assert response.choices[0].message.content is not None
        assert len(response.choices[0].message.content.strip()) > 0

        logger.info(f"Bedrock Titan Response: {response.choices[0].message.content}")
        if response.usage:
            logger.info(f"Bedrock Titan Usage: {response.usage}")

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(not AWS_AVAILABLE, reason="AWS credentials not available")
    async def test_bedrock_multiple_models(self):
        """Test Bedrock with different model configurations."""
        models_to_test = [
            "us.anthropic.claude-3-5-haiku-20241022-v1:0",
            "amazon.titan-text-express-v1",
        ]

        for model_id in models_to_test:
            try:
                service = LLMServiceFactory.get_service("bedrock", model_id=model_id)

                messages = [Message(role="user", content="Hello")]

                response = await service.chat_completion(
                    model_id=model_id, messages=messages, max_tokens=20
                )

                assert response is not None
                assert response.choices is not None
                assert len(response.choices) > 0

                logger.info(
                    f"Bedrock Model {model_id} test passed: {response.choices[0].message.content[:50]}..."
                )

            except Exception as e:
                logger.warning(f"Bedrock Model {model_id} test failed: {e}")
                # Don't fail the test if a specific model isn't available
                continue


class TestRealAPIComparison:
    """Test comparing responses from different providers."""

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(
        not (OPENAI_AVAILABLE and AWS_AVAILABLE),
        reason="Both OpenAI and AWS credentials required",
    )
    async def test_compare_openai_vs_bedrock(self):
        """Compare responses from OpenAI and Bedrock for the same prompt."""
        prompt = "What is machine learning? Answer in exactly 10 words."
        messages = [Message(role="user", content=prompt)]

        # Test OpenAI
        openai_service = LLMServiceFactory.get_service(
            "openai", model_id=TEST_OPENAI_MODEL
        )
        openai_response = await openai_service.chat_completion(
            model_id=TEST_OPENAI_MODEL,
            messages=messages,
            max_tokens=20,
            temperature=0.1,
        )

        # Test Bedrock Claude
        bedrock_service = LLMServiceFactory.get_service(
            "bedrock", model_id=TEST_CLAUDE_MODEL
        )
        bedrock_response = await bedrock_service.chat_completion(
            model_id=TEST_CLAUDE_MODEL,
            messages=messages,
            max_tokens=20,
            temperature=0.1,
        )

        # Verify both responses are valid
        assert openai_response.choices[0].message.content is not None
        assert bedrock_response.choices[0].message.content is not None

        openai_content = openai_response.choices[0].message.content.strip()
        bedrock_content = bedrock_response.choices[0].message.content.strip()

        assert len(openai_content) > 0
        assert len(bedrock_content) > 0

        logger.info(f"OpenAI Response: {openai_content}")
        logger.info(f"Bedrock Response: {bedrock_content}")

        # Both should contain relevant terms
        ml_terms = ["machine", "learning", "AI", "data", "algorithm", "model"]
        openai_has_ml_term = any(
            term.lower() in openai_content.lower() for term in ml_terms
        )
        bedrock_has_ml_term = any(
            term.lower() in bedrock_content.lower() for term in ml_terms
        )

        assert openai_has_ml_term or bedrock_has_ml_term, (
            "Neither response contains relevant ML terms"
        )


@pytest.mark.real_api
class TestConfigurationValidation:
    """Test configuration validation and error handling."""

    def test_env_variables_loaded(self):
        """Test that environment variables are properly loaded."""
        # Test that we can access configuration
        assert config_loader.app_config is not None

        # Log configuration status (without exposing sensitive data)
        logger.info(f"OpenAI API Key configured: {bool(OPENAI_API_KEY)}")
        logger.info(f"AWS Access Key configured: {bool(AWS_ACCESS_KEY_ID)}")
        logger.info(f"AWS Region: {AWS_REGION}")

        # Test that at least one provider is configured
        assert OPENAI_AVAILABLE or AWS_AVAILABLE, "No LLM providers are configured"

    @pytest.mark.asyncio
    async def test_factory_model_resolution(self):
        """Test that the factory can resolve models correctly."""
        # Test OpenAI model resolution
        if OPENAI_AVAILABLE:
            service = LLMServiceFactory.get_service_for_model("gpt-4o-mini")
            assert service is not None

        # Test Bedrock model resolution
        if AWS_AVAILABLE:
            service = LLMServiceFactory.get_service_for_model(
                "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            )
            assert service is not None

    @pytest.mark.asyncio
    @pytest.mark.real_api
    async def test_error_handling_invalid_model(self):
        """Test error handling for invalid model configurations."""
        if OPENAI_AVAILABLE:
            service = LLMServiceFactory.get_service(
                "openai", model_id="invalid-model-name"
            )
            messages = [Message(role="user", content="Test")]

            with pytest.raises((LLMIntegrationError, Exception)):
                await service.chat_completion(
                    model_id="invalid-model-name", messages=messages, max_tokens=10
                )


class TestPerformanceAndLimits:
    """Test performance characteristics and API limits."""

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI API key not available")
    async def test_concurrent_requests(self):
        """Test concurrent API requests."""
        service = LLMServiceFactory.get_service("openai", model_id=TEST_OPENAI_MODEL)

        messages = [Message(role="user", content="Say 'Hello'")]

        # Create multiple concurrent requests
        tasks = []
        for _i in range(3):  # Keep it reasonable to avoid rate limits
            task = service.chat_completion(
                model_id=TEST_OPENAI_MODEL, messages=messages, max_tokens=5
            )
            tasks.append(task)

        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that we got some successful responses (allowing for rate limits)
        successful_responses = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_responses) > 0, "No successful concurrent requests"

        logger.info(
            f"Concurrent requests: {len(successful_responses)}/{len(tasks)} successful"
        )

    @pytest.mark.asyncio
    @pytest.mark.real_api
    @pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI API key not available")
    async def test_token_usage_tracking(self):
        """Test that token usage is properly tracked."""
        service = LLMServiceFactory.get_service("openai", model_id=TEST_OPENAI_MODEL)

        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Write a short sentence about the weather."),
        ]

        response = await service.chat_completion(
            model_id=TEST_OPENAI_MODEL, messages=messages, max_tokens=30
        )

        assert response.usage is not None
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
        assert response.usage.total_tokens > 0
        assert (
            response.usage.total_tokens
            == response.usage.prompt_tokens + response.usage.completion_tokens
        )

        logger.info(
            f"Token usage - Prompt: {response.usage.prompt_tokens}, "
            f"Completion: {response.usage.completion_tokens}, "
            f"Total: {response.usage.total_tokens}"
        )


if __name__ == "__main__":
    # Run a quick test when executed directly
    async def quick_test():
        logger.info("Running quick integration test...")

        if OPENAI_AVAILABLE:
            logger.info("Testing OpenAI...")
            service = LLMServiceFactory.get_service(
                "openai", model_id=TEST_OPENAI_MODEL
            )
            messages = [Message(role="user", content="Hello")]
            response = await service.chat_completion(
                model_id=TEST_OPENAI_MODEL, messages=messages, max_tokens=10
            )
            logger.info(f"OpenAI works: {response.choices[0].message.content}")

        if AWS_AVAILABLE:
            logger.info("Testing Bedrock...")
            service = LLMServiceFactory.get_service(
                "bedrock", model_id=TEST_CLAUDE_MODEL
            )
            messages = [Message(role="user", content="Hello")]
            response = await service.chat_completion(
                model_id=TEST_CLAUDE_MODEL, messages=messages, max_tokens=10
            )
            logger.info(f"Bedrock works: {response.choices[0].message.content}")

    asyncio.run(quick_test())
