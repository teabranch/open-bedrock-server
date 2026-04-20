import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)

# Import custom exceptions
from src.open_bedrock_server.core.exceptions import (
    ConfigurationError,
    ServiceApiError,
    ServiceAuthenticationError,
    ServiceModelNotFoundError,
    ServiceRateLimitError,
    ServiceUnavailableError,
    StreamingError,
)
from src.open_bedrock_server.core.models import (
    ChatCompletionChoice as CoreChatCompletionChoice,  # For parsing Claude responses
)
from src.open_bedrock_server.core.models import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChoiceDelta,
    Message,
    ModelProviderInfo,
)

from .llm_service_abc import AbstractLLMService

logger = logging.getLogger(__name__)


# Helper to determine model provider from Bedrock model ID
def get_provider_from_bedrock_model_id(model_id: str) -> str:
    lower_model_id = model_id.lower()
    if (
        lower_model_id.startswith("anthropic.")
        or lower_model_id.startswith("us.anthropic.")
        or "claude" in lower_model_id
    ):
        return "anthropic"
    elif (
        lower_model_id.startswith("ai21.")
        or lower_model_id.startswith("us.ai21.")
        or "jJurassic" in lower_model_id
    ):  # AI21 Jurassic
        return "ai21"
    elif (
        lower_model_id.startswith("cohere.")
        or lower_model_id.startswith("us.cohere.")
        or "command" in lower_model_id
        or "embed" in lower_model_id
    ):  # Cohere Command, Embed
        return "cohere"
    elif (
        lower_model_id.startswith("meta.")
        or lower_model_id.startswith("us.meta.")
        or "llama" in lower_model_id
    ):  # Meta Llama
        return "meta"
    elif (
        lower_model_id.startswith("amazon.")
        or lower_model_id.startswith("us.amazon.")
        or "titan" in lower_model_id
    ):
        return "amazon"
    return "unknown_bedrock_provider"


class BedrockService(AbstractLLMService):
    def __init__(
        self,
        AWS_REGION: str | None = None,
        AWS_PROFILE: str | None = None,
        AWS_ROLE_ARN: str | None = None,
        AWS_EXTERNAL_ID: str | None = None,
        AWS_ROLE_SESSION_NAME: str | None = None,
        AWS_WEB_IDENTITY_TOKEN_FILE: str | None = None,
        validate_credentials: bool = True,
        **kwargs,
    ):
        self.AWS_REGION = AWS_REGION or os.getenv("AWS_REGION")
        self.AWS_PROFILE = AWS_PROFILE or os.getenv("AWS_PROFILE")
        self.AWS_ROLE_ARN = AWS_ROLE_ARN or os.getenv("AWS_ROLE_ARN")
        self.AWS_EXTERNAL_ID = AWS_EXTERNAL_ID or os.getenv("AWS_EXTERNAL_ID")
        self.AWS_ROLE_SESSION_NAME = AWS_ROLE_SESSION_NAME or os.getenv(
            "AWS_ROLE_SESSION_NAME", "bedrock-service-session"
        )
        self.AWS_WEB_IDENTITY_TOKEN_FILE = AWS_WEB_IDENTITY_TOKEN_FILE or os.getenv(
            "AWS_WEB_IDENTITY_TOKEN_FILE"
        )
        self.validate_credentials = validate_credentials

        if not self.AWS_REGION:
            logger.warning(
                "AWS_REGION not provided or found in environment. Bedrock calls may fail or use default region."
            )
            # It might still work if a default region is configured in AWS environment/profile.
            # However, explicit configuration is better.

        try:
            session = self._create_aws_session()

            # Test credentials early by trying to get caller identity (optional for testing)
            if self.validate_credentials:
                sts_client = session.client("sts")
                try:
                    caller_identity = sts_client.get_caller_identity()
                    logger.info(
                        f"AWS STS GetCallerIdentity successful. Account: {caller_identity.get('Account')}, "
                        f"User/Role: {caller_identity.get('Arn')}"
                    )
                except (NoCredentialsError, PartialCredentialsError) as e:
                    logger.error(f"AWS credentials not found or incomplete: {e}")
                    raise ConfigurationError(
                        f"AWS credentials not found or incomplete: {e}"
                    )
                except ClientError as e:
                    # Handle other STS ClientErrors that might indicate auth problems
                    error_code = e.response.get("Error", {}).get("Code")
                    if (
                        error_code == "InvalidClientTokenId"
                        or error_code == "SignatureDoesNotMatch"
                    ):
                        logger.error(f"AWS STS authentication failure: {e}")
                        raise ConfigurationError(
                            f"AWS authentication failed (STS): {e}"
                        )
                    logger.warning(
                        f"AWS STS GetCallerIdentity failed with ClientError (possibly ignorable if other services work): {e}"
                    )
                    # Not raising ConfigurationError here for all ClientErrors from STS, as it might be overly strict
                    # if the target Bedrock region/service is accessible via other means (e.g. instance profile)
            else:
                logger.info(
                    "Skipping AWS credential validation (validate_credentials=False)"
                )

            self.bedrock_runtime_client = session.client("bedrock-runtime")
            self.bedrock_client = session.client("bedrock")
            logger.info("BedrockService initialized with Bedrock clients.")

        except ConfigurationError:  # Re-raise ConfigurationError from STS check
            raise
        except (
            NoCredentialsError,
            PartialCredentialsError,
        ) as e:  # Should be caught by STS check, but as fallback
            logger.error(
                f"AWS credentials issue during Bedrock client initialization: {e}"
            )
            raise ConfigurationError(
                f"AWS credentials not found or incomplete for Bedrock: {e}"
            )
        except BotoCoreError as e:  # Catch other BotoCore errors like ProfileNotFound
            logger.error(f"BotoCoreError during Bedrock client initialization: {e}")
            raise ConfigurationError(
                f"AWS SDK (BotoCore) error during Bedrock init: {e}"
            )
        except Exception as e:  # General catch-all for other unexpected init errors
            logger.error(f"Failed to initialize BedrockService clients: {e}")
            raise ConfigurationError(f"Failed to initialize AWS Bedrock clients: {e}")

    def _create_aws_session(self) -> boto3.Session:
        """Create an AWS session using the configured authentication method."""
        # Check what authentication methods are available
        static_keys_present = bool(
            os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        profile_present = bool(self.AWS_PROFILE)
        role_arn_present = bool(self.AWS_ROLE_ARN)
        web_identity_present = bool(self.AWS_WEB_IDENTITY_TOKEN_FILE)

        # Check if this is an AWS SSO role that cannot assume itself
        is_sso_role = role_arn_present and "AWSReservedSSO" in self.AWS_ROLE_ARN

        logger.info(
            f"AWS authentication methods detected - Static keys: {static_keys_present}, "
            f"Profile: {profile_present}, Role ARN: {role_arn_present}, "
            f"Web identity: {web_identity_present}, SSO Role: {is_sso_role}"
        )

        # Priority order: static credentials > profile > role ARN > web identity > default
        if static_keys_present:
            logger.info("Creating boto3 session with static AWS credentials.")
            return boto3.Session(
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
                region_name=self.AWS_REGION,
            )
        elif profile_present and is_sso_role:
            # For AWS SSO roles, use the profile directly instead of role assumption
            logger.info(
                f"Creating boto3 session with AWS SSO profile: {self.AWS_PROFILE} (skipping role assumption for SSO role)"
            )
            return boto3.Session(
                profile_name=self.AWS_PROFILE, region_name=self.AWS_REGION
            )
        elif profile_present:
            logger.info(
                f"Creating boto3 session with profile: {self.AWS_PROFILE} and region: {self.AWS_REGION}"
            )
            return boto3.Session(
                profile_name=self.AWS_PROFILE, region_name=self.AWS_REGION
            )
        elif role_arn_present:
            logger.info(
                f"Creating boto3 session with role assumption: {self.AWS_ROLE_ARN}"
            )
            # Check if we have base credentials for role assumption
            base_creds_available = (
                static_keys_present
                or profile_present
                or bool(os.getenv("AWS_PROFILE"))  # Check env var directly
                or
                # Instance profile credentials are harder to detect, so we'll try anyway
                True  # Let the assume role method handle the validation
            )
            if not base_creds_available:
                logger.warning(
                    "Role assumption requested but no obvious base credentials detected. "
                    "Ensure AWS credentials are available via profile, environment variables, "
                    "or instance profile."
                )
            return self._create_assume_role_session()
        elif web_identity_present:
            logger.info(
                f"Creating boto3 session with web identity token: {self.AWS_WEB_IDENTITY_TOKEN_FILE}"
            )
            return self._create_web_identity_session()
        else:
            logger.info(
                f"Creating boto3 session with default credentials and region: {self.AWS_REGION}"
            )
            logger.info(
                "Using default credential chain (instance profile, environment, etc.)"
            )
            return boto3.Session(region_name=self.AWS_REGION)

    def _create_assume_role_session(self) -> boto3.Session:
        """Create a session by assuming a role."""
        try:
            # Create a base session to assume the role
            # The base session needs existing credentials (profile, env vars, or instance profile)
            base_session = boto3.Session(region_name=self.AWS_REGION)
            sts_client = base_session.client("sts")

            # Test that base credentials are available
            try:
                sts_client.get_caller_identity()
                logger.info("Base credentials validated for role assumption.")
            except (NoCredentialsError, PartialCredentialsError) as e:
                logger.error(f"No base credentials available for role assumption: {e}")
                raise ConfigurationError(
                    f"Role assumption requires base AWS credentials (profile, env vars, or instance profile): {e}"
                )
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code in ["InvalidClientTokenId", "SignatureDoesNotMatch"]:
                    logger.error(f"Invalid base credentials for role assumption: {e}")
                    raise ConfigurationError(
                        f"Invalid base AWS credentials for role assumption: {e}"
                    )
                # Other ClientErrors might be acceptable (e.g., permission issues that don't affect role assumption)
                logger.warning(
                    f"Base credentials check warning (may be acceptable): {e}"
                )

            # Prepare assume role parameters
            assume_role_params = {
                "RoleArn": self.AWS_ROLE_ARN,
                "RoleSessionName": self.AWS_ROLE_SESSION_NAME,
                "DurationSeconds": int(os.getenv("AWS_ROLE_SESSION_DURATION", "3600")),
            }

            # Add external ID if provided
            if self.AWS_EXTERNAL_ID:
                assume_role_params["ExternalId"] = self.AWS_EXTERNAL_ID
                logger.info("Using external ID for role assumption.")

            # Assume the role
            logger.info(f"Attempting to assume role: {self.AWS_ROLE_ARN}")
            response = sts_client.assume_role(**assume_role_params)
            credentials = response["Credentials"]

            logger.info(
                f"Successfully assumed role '{self.AWS_ROLE_ARN}'. "
                f"Session expires at: {credentials['Expiration']}"
            )

            # Create session with assumed role credentials
            return boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=self.AWS_REGION,
            )

        except ConfigurationError:
            # Re-raise ConfigurationError as-is
            raise
        except (NoCredentialsError, PartialCredentialsError) as e:
            logger.error(f"Credentials error during role assumption: {e}")
            raise ConfigurationError(
                f"AWS credentials not available for role assumption: {e}"
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "AccessDenied":
                logger.error(
                    f"Access denied when assuming role {self.AWS_ROLE_ARN}: {error_message}"
                )
                raise ConfigurationError(
                    f"Access denied when assuming role {self.AWS_ROLE_ARN}. "
                    f"Check role trust policy and permissions: {error_message}"
                )
            elif error_code == "InvalidParameterValue":
                logger.error(f"Invalid role ARN or parameters: {error_message}")
                raise ConfigurationError(
                    f"Invalid role ARN or assume role parameters: {error_message}"
                )
            elif error_code == "TokenRefreshRequired":
                logger.error(f"Base credentials expired or invalid: {error_message}")
                raise ConfigurationError(
                    f"Base AWS credentials expired or invalid for role assumption: {error_message}"
                )
            else:
                logger.error(
                    f"STS ClientError during role assumption: {error_code} - {error_message}"
                )
                raise ConfigurationError(
                    f"AWS STS error during role assumption: {error_message} (Code: {error_code})"
                )
        except BotoCoreError as e:
            logger.error(f"BotoCoreError during role assumption: {e}")
            raise ConfigurationError(f"AWS SDK error during role assumption: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error during role assumption: {type(e).__name__} - {e}"
            )
            raise ConfigurationError(f"Unexpected error during role assumption: {e}")

    def _create_web_identity_session(self) -> boto3.Session:
        """Create a session using web identity token."""
        try:
            # For web identity, we rely on boto3's built-in support
            # Set the environment variables that boto3 expects
            import os

            original_env = {}

            # Temporarily set environment variables for boto3
            env_vars = {
                "AWS_WEB_IDENTITY_TOKEN_FILE": self.AWS_WEB_IDENTITY_TOKEN_FILE,
                "AWS_ROLE_ARN": self.AWS_ROLE_ARN or "",
                "AWS_ROLE_SESSION_NAME": self.AWS_ROLE_SESSION_NAME,
            }

            # Validate required parameters
            if not self.AWS_WEB_IDENTITY_TOKEN_FILE:
                raise ConfigurationError(
                    "AWS_WEB_IDENTITY_TOKEN_FILE is required for web identity authentication"
                )

            if not os.path.exists(self.AWS_WEB_IDENTITY_TOKEN_FILE):
                raise ConfigurationError(
                    f"Web identity token file not found: {self.AWS_WEB_IDENTITY_TOKEN_FILE}"
                )

            # Set environment variables temporarily
            for key, value in env_vars.items():
                if value:
                    original_env[key] = os.environ.get(key)
                    os.environ[key] = value

            try:
                session = boto3.Session(region_name=self.AWS_REGION)
                # Test the session
                sts_client = session.client("sts")
                caller_identity = sts_client.get_caller_identity()
                logger.info(
                    f"Successfully initialized session with web identity token. Account: {caller_identity.get('Account')}"
                )
                return session
            finally:
                # Restore original environment
                for key in env_vars:
                    if original_env.get(key) is not None:
                        os.environ[key] = original_env[key]
                    elif key in os.environ:
                        del os.environ[key]

        except ConfigurationError:
            # Re-raise ConfigurationError as-is
            raise
        except (NoCredentialsError, PartialCredentialsError) as e:
            logger.error(f"Credentials error with web identity token: {e}")
            raise ConfigurationError(f"Web identity token authentication failed: {e}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "InvalidIdentityToken":
                logger.error(f"Invalid web identity token: {error_message}")
                raise ConfigurationError(f"Invalid web identity token: {error_message}")
            elif error_code == "ExpiredToken":
                logger.error(f"Expired web identity token: {error_message}")
                raise ConfigurationError(
                    f"Web identity token has expired: {error_message}"
                )
            elif error_code == "AccessDenied":
                logger.error(f"Access denied with web identity token: {error_message}")
                raise ConfigurationError(
                    f"Access denied with web identity token: {error_message}"
                )
            else:
                logger.error(
                    f"STS ClientError with web identity token: {error_code} - {error_message}"
                )
                raise ConfigurationError(
                    f"Web identity authentication error: {error_message} (Code: {error_code})"
                )
        except BotoCoreError as e:
            logger.error(f"BotoCoreError with web identity token: {e}")
            raise ConfigurationError(f"AWS SDK error with web identity token: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error with web identity token: {type(e).__name__} - {e}"
            )
            raise ConfigurationError(f"Unexpected error with web identity token: {e}")

    @property
    def provider_name(self) -> str:
        """Return the provider name for this service."""
        return "bedrock"

    def _handle_bedrock_client_error(self, e: ClientError, model_id: str):
        error_code = e.response.get("Error", {}).get("Code")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")

        logger.error(
            f"Bedrock API ClientError: Model={model_id}, Code={error_code}, Message={error_message}, Status={status_code}"
        )

        if error_code == "AccessDeniedException":
            raise ServiceAuthenticationError(
                f"Bedrock Access Denied for model {model_id}: {error_message}"
            )
        elif error_code == "ResourceNotFoundException":
            raise ServiceModelNotFoundError(
                f"Bedrock model {model_id} not found or access denied: {error_message}"
            )
        elif error_code == "ThrottlingException":
            raise ServiceRateLimitError(
                f"Bedrock API rate limit exceeded for model {model_id}: {error_message}"
            )
        elif (
            error_code == "ModelTimeoutException"
            or error_code == "ServiceUnavailableException"
            or (status_code and status_code == 503)
        ):
            raise ServiceUnavailableError(
                f"Bedrock service unavailable or model timeout for {model_id}: {error_message}"
            )
        elif error_code == "ValidationException":  # Input validation issues
            raise ServiceApiError(
                f"Bedrock validation error for model {model_id}: {error_message} (Request may be malformed)"
            )
        elif status_code and 500 <= status_code < 600:
            raise ServiceApiError(
                f"Bedrock server error (status: {status_code}) for model {model_id}: {error_message}"
            )
        else:  # Fallback for other ClientErrors
            raise ServiceApiError(
                f"Bedrock API ClientError for model {model_id}: {error_message} (Code: {error_code})"
            )

    def _prepare_anthropic_claude_messages(
        self, messages: list[Message]
    ) -> list[dict[str, Any]]:
        claude_messages = []
        system_prompt = None
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue
            if msg.role == "user" or msg.role == "assistant":
                claude_messages.append({"role": msg.role, "content": msg.content})
        return claude_messages, system_prompt

    def _prepare_amazon_titan_payload(
        self,
        messages: list[Message],
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        # Titan models generally expect a single 'inputText' string.
        # We'll concatenate messages, clearly delineating roles.
        # System prompts are typically prepended.
        prompt_parts = []
        system_content = ""

        for msg in messages:
            if msg.role == "system":
                # Titan doesn't have a separate system prompt field in the same way Claude v2+ does.
                # Prepend system instructions to the main prompt.
                system_content += msg.content + "\n\n"  # Add some separation
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")
            # Ignoring other roles for simplicity with Titan's simpler structure

        input_text = system_content + "\n".join(prompt_parts)

        text_generation_config = {}
        if max_tokens:
            text_generation_config["maxTokenCount"] = max_tokens
        else:
            text_generation_config["maxTokenCount"] = 2048  # Default if not provided
        if temperature is not None:
            text_generation_config["temperature"] = temperature
        # Titan also supports topP, stopSequences - not implemented here for brevity

        return {"inputText": input_text, "textGenerationConfig": text_generation_config}

    async def _invoke_anthropic_claude_stream(
        self, model_id: str, bedrock_payload: dict[str, Any]
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        try:
            response_stream = await asyncio.to_thread(
                self.bedrock_runtime_client.invoke_model_with_response_stream,
                modelId=model_id,
                body=json.dumps(bedrock_payload),
            )

            chunk_id_prefix = f"chatcmpl-br-{int(time.time())}"
            chunk_index = 0

            # Get the body stream
            event_stream = response_stream["body"]

            # Process events from the stream
            for event in event_stream:
                chunk_data = json.loads(event["chunk"]["bytes"])
                delta_content = ""
                finish_reason = None
                role = "assistant"

                if chunk_data["type"] == "content_block_delta":
                    delta_content = chunk_data.get("delta", {}).get("text", "")
                elif chunk_data["type"] == "message_delta":
                    delta_payload = chunk_data.get("delta", {})
                    finish_reason = self._map_finish_reason(
                        delta_payload.get("stop_reason")
                    )
                elif chunk_data["type"] == "message_stop":
                    # This might not have content but confirms end of message with metrics
                    # If finish_reason wasn't in message_delta, it might be inferred here or from invocation metrics
                    pass

                yield ChatCompletionChunk(
                    id=f"{chunk_id_prefix}-{chunk_index}",
                    object="chat.completion.chunk",
                    created=int(time.time()),
                    model=model_id,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChoiceDelta(
                                content=delta_content,
                                role=role
                                if delta_content or chunk_index == 0
                                else None,
                            ),
                            finish_reason=finish_reason,
                        )
                    ],
                )
                chunk_index += 1
                if finish_reason:
                    logger.debug(
                        f"Bedrock stream for {model_id} finished with reason: {finish_reason}"
                    )
                    break

            # Ensure we close the stream
            event_stream.close()

        except ClientError as e:
            self._handle_bedrock_client_error(e, model_id)
        except Exception as e:
            logger.error(
                f"Error processing Bedrock (Claude Stream) response for {model_id}: {e}"
            )
            raise StreamingError(
                f"Error during Bedrock stream processing for {model_id}: {str(e)}"
            )

    async def _invoke_anthropic_claude_non_stream(
        self, model_id: str, bedrock_payload: dict[str, Any]
    ) -> ChatCompletionResponse:
        try:
            response = await asyncio.to_thread(  # Wrap synchronous boto3 call
                self.bedrock_runtime_client.invoke_model,
                modelId=model_id,
                body=json.dumps(bedrock_payload),
            )
            response_body = json.loads(response["body"].read())

            assistant_content = ""
            if response_body.get("content") and isinstance(
                response_body["content"], list
            ):
                for block in response_body["content"]:
                    if block["type"] == "text":
                        assistant_content += block["text"]

            return ChatCompletionResponse(
                id=f"chatcmpl-br-{int(time.time())}",
                object="chat.completion",
                created=int(time.time()),
                model=model_id,
                choices=[
                    CoreChatCompletionChoice(
                        index=0,
                        message=Message(role="assistant", content=assistant_content),
                        finish_reason=self._map_finish_reason(
                            response_body.get("stop_reason")
                        ),
                    )
                ],
            )
        except ClientError as e:
            self._handle_bedrock_client_error(e, model_id)
        except Exception as e:  # Catch-all for other errors (e.g., JSON parsing)
            logger.error(
                f"Error processing Bedrock (Claude Non-Stream) response for {model_id}: {type(e).__name__} - {e}"
            )
            raise ServiceApiError(
                f"Unexpected error processing Bedrock response for {model_id}: {type(e).__name__} - {str(e)}"
            )

    async def _invoke_amazon_titan_non_stream(
        self, model_id: str, bedrock_payload: dict[str, Any]
    ) -> ChatCompletionResponse:
        try:
            response = await asyncio.to_thread(
                self.bedrock_runtime_client.invoke_model,
                modelId=model_id,
                body=json.dumps(bedrock_payload),
            )
            response_body = json.loads(response["body"].read().decode("utf-8"))

            # Titan response structure:
            # {
            #   "inputTextTokenCount": number,
            #   "results": [
            #     {
            #       "tokenCount": number,
            #       "outputText": string,
            #       "completionReason": string (e.g., "FINISH", "LENGTH")
            #     }
            #   ]
            # }

            assistant_content = ""
            finish_reason = None

            if (
                response_body.get("results")
                and isinstance(response_body["results"], list)
                and len(response_body["results"]) > 0
            ):
                first_result = response_body["results"][0]
                assistant_content = first_result.get("outputText", "")
                finish_reason = first_result.get("completionReason")
                if finish_reason == "FINISH":
                    finish_reason = "stop"
                elif finish_reason == "LENGTH":
                    finish_reason = "length"
                # Add other mappings if necessary, or leave as is if it's already a valid reason

            return ChatCompletionResponse(
                id=f"chatcmpl-br-titan-{int(time.time())}",
                object="chat.completion",
                created=int(time.time()),
                model=model_id,
                choices=[
                    CoreChatCompletionChoice(
                        index=0,
                        message=Message(role="assistant", content=assistant_content),
                        finish_reason=finish_reason,
                    )
                ],
                # Usage data can be extracted from response_body if needed
                # usage={"prompt_tokens": response_body.get("inputTextTokenCount"),
                #        "completion_tokens": first_result.get("tokenCount") if first_result else 0}
            )
        except ClientError as e:
            self._handle_bedrock_client_error(e, model_id)
        except Exception as e:
            logger.error(
                f"Error processing Bedrock (Titan Non-Stream) response for {model_id}: {type(e).__name__} - {e}"
            )
            raise ServiceApiError(
                f"Unexpected error processing Bedrock Titan response for {model_id}: {type(e).__name__} - {str(e)}"
            )

    async def _invoke_amazon_titan_stream(
        self, model_id: str, bedrock_payload: dict[str, Any]
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        try:
            response_stream = await asyncio.to_thread(
                self.bedrock_runtime_client.invoke_model_with_response_stream,
                modelId=model_id,
                body=json.dumps(bedrock_payload),
            )

            chunk_id_prefix = f"chatcmpl-br-titan-{int(time.time())}"
            chunk_index = 0
            event_stream = response_stream["body"]

            # Titan stream events:
            # {"outputText": "...", "index": 0, "totalOutputTextTokenCount": null, "completionReason": null, "inputTextTokenCount": N}
            # The last event might contain completionReason.

            for event in event_stream:
                chunk_data = json.loads(event["chunk"]["bytes"].decode("utf-8"))
                delta_content = chunk_data.get("outputText", "")
                finish_reason = chunk_data.get(
                    "completionReason"
                )  # Often null until the end
                if finish_reason == "FINISH":
                    finish_reason = "stop"
                elif finish_reason == "LENGTH":
                    finish_reason = "length"
                # Add other mappings if necessary

                role = "assistant"  # Titan output is always assistant

                yield ChatCompletionChunk(
                    id=f"{chunk_id_prefix}-{chunk_index}",
                    object="chat.completion.chunk",
                    created=int(time.time()),
                    model=model_id,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,  # Titan results are usually singular for text generation
                            delta=ChoiceDelta(
                                content=delta_content,
                                role=role
                                if delta_content or chunk_index == 0
                                else None,
                            ),
                            finish_reason=finish_reason,
                        )
                    ],
                )
                chunk_index += 1
                if finish_reason:
                    logger.debug(
                        f"Bedrock Titan stream for {model_id} finished with reason: {finish_reason}"
                    )
                    break

            event_stream.close()

        except ClientError as e:
            self._handle_bedrock_client_error(e, model_id)
        except Exception as e:
            logger.error(
                f"Error processing Bedrock (Titan Stream) response for {model_id}: {e}"
            )
            raise StreamingError(
                f"Error during Bedrock Titan stream processing for {model_id}: {str(e)}"
            )

    @staticmethod
    def _map_finish_reason(provider_reason: str | None) -> str | None:
        """Maps provider-specific finish/stop reasons to OpenAI-compatible reasons."""
        if provider_reason is None:
            return None
        mapping = {
            # Claude / Anthropic
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
            "tool_use": "tool_calls",
            # Titan
            "FINISH": "stop",
            "LENGTH": "length",
            "CONTENT_FILTERED": "content_filter",
        }
        return mapping.get(provider_reason, provider_reason)

    async def chat_completion(
        self,
        messages: list[Message],
        model_id: str | None = None,
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ChatCompletionResponse | AsyncGenerator[ChatCompletionChunk, None]:
        # Handle the standard interface (messages list)
        if not model_id:
            # This is a programming error if called without model_id from within the system
            raise ValueError("model_id must be provided for Bedrock chat completion.")

        provider = get_provider_from_bedrock_model_id(model_id)
        logger.info(
            f"BedrockService: chat_completion for model: {model_id} (Provider: {provider}), Stream: {stream}"
        )

        if provider == "anthropic":
            claude_messages, system_prompt = self._prepare_anthropic_claude_messages(
                messages
            )
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": claude_messages,
            }
            if system_prompt:
                payload["system"] = system_prompt
            if max_tokens:
                payload["max_tokens"] = max_tokens
            else:
                payload["max_tokens"] = 2048
            if temperature is not None:
                payload["temperature"] = temperature

            if stream:
                return self._invoke_anthropic_claude_stream(model_id, payload)
            else:
                return await self._invoke_anthropic_claude_non_stream(model_id, payload)
        elif provider == "amazon":
            payload = self._prepare_amazon_titan_payload(
                messages, temperature, max_tokens
            )
            if stream:
                return self._invoke_amazon_titan_stream(model_id, payload)
            else:
                return await self._invoke_amazon_titan_non_stream(model_id, payload)
        else:
            logger.error(
                f"Unsupported Bedrock provider '{provider}' for model_id '{model_id}'."
            )
            # This should ideally be ServiceModelNotFoundError or a more specific "UnsupportedModelError"
            raise ServiceModelNotFoundError(
                f"Provider '{provider}' for Bedrock model '{model_id}' is not supported or model is invalid."
            )

    async def chat_completion_with_request(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse | AsyncGenerator[ChatCompletionChunk, None]:
        """
        Handle chat completion with a ChatCompletionRequest DTO.
        This method is used by the API routes.
        """
        kwargs = {}
        if request.tools:
            kwargs["tools"] = request.tools
        if request.tool_choice:
            kwargs["tool_choice"] = request.tool_choice

        return await self.chat_completion(
            messages=request.messages,
            model_id=request.model,
            stream=request.stream or False,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            **kwargs,
        )

    async def list_models(self) -> list[ModelProviderInfo]:
        logger.info(
            f"BedrockService: Fetching on-demand models from Bedrock region: {self.AWS_REGION}"
        )
        all_bedrock_models = []
        seen_ids: set[str] = set()
        try:
            # Fetch foundation models
            fm_response = await asyncio.to_thread(
                lambda: self.bedrock_client.list_foundation_models(byInferenceType="ON_DEMAND")
            )
            for model_summary in fm_response.get("modelSummaries", []):
                if "TEXT" in model_summary.get("outputModalities", []):
                    model_id = model_summary["modelId"]
                    if model_id not in seen_ids:
                        seen_ids.add(model_id)
                        all_bedrock_models.append(
                            ModelProviderInfo(
                                id=model_id,
                                provider="bedrock",
                                display_name=model_summary.get(
                                    "modelName", model_id
                                ),
                            )
                        )

            # Fetch inference profiles (cross-region and application profiles)
            try:
                paginator = self.bedrock_client.get_paginator("list_inference_profiles")
                pages = await asyncio.to_thread(
                    lambda: list(paginator.paginate())
                )
                for page in pages:
                    for profile in page.get("inferenceProfileSummaries", []):
                        profile_id = profile.get("inferenceProfileId", "")
                        if profile_id and profile_id not in seen_ids:
                            seen_ids.add(profile_id)
                            all_bedrock_models.append(
                                ModelProviderInfo(
                                    id=profile_id,
                                    provider="bedrock",
                                    display_name=profile.get(
                                        "inferenceProfileName", profile_id
                                    ),
                                )
                            )
            except Exception as e:
                logger.warning(f"Could not list inference profiles: {e}")

            logger.info(f"Found {len(all_bedrock_models)} potential Bedrock models.")
            return all_bedrock_models
        except ClientError as e:
            logger.error(
                f"Bedrock API error listing models: {e}. Ensure Bedrock model access is enabled in region {self.AWS_REGION}."
            )
            self._handle_bedrock_client_error(
                e, "list_models"
            )
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing Bedrock models: {e}")
            raise ServiceApiError(f"Unexpected error listing Bedrock models: {str(e)}")
