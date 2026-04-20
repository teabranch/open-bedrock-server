import logging

from fastapi import APIRouter, Depends

from src.open_bedrock_server.core.models import (
    ModelProviderInfo,
)  # Core model from service
from src.open_bedrock_server.services.llm_service_factory import (
    LLMServiceFactory,
)

from ..middleware.auth import verify_api_key
from ..schemas.responses import ModelInfo, ModelListResponse  # API response models

logger = logging.getLogger(__name__)
router = APIRouter()

# In a more complex scenario, you might want to list models from ALL configured providers
# or allow specifying a provider.
# For now, we'll try to list from OpenAI and Bedrock (when implemented) and combine.


@router.get(
    "/v1/models",
    response_model=ModelListResponse,
    dependencies=[Depends(verify_api_key)],
)
async def list_models_route():  # Renamed to avoid conflict with imported list_models
    """Lists available models from configured LLM providers, conforming to OpenAI spec."""
    all_provider_models: list[ModelProviderInfo] = []

    try:
        openai_service = LLMServiceFactory.get_service("openai")
        if hasattr(openai_service, "list_models") and callable(
            openai_service.list_models
        ):
            openai_models = await openai_service.list_models()
            all_provider_models.extend(openai_models)
            logger.info(f"Fetched {len(openai_models)} models from OpenAI.")
        else:
            logger.warning(
                "OpenAI service does not have a callable list_models method."
            )
    except Exception as e:
        logger.error(f"Error listing models from OpenAI: {e}")

    # Bedrock models (when BedrockService is implemented)
    try:
        bedrock_service = LLMServiceFactory.get_service("bedrock")
        if hasattr(bedrock_service, "list_models") and callable(
            bedrock_service.list_models
        ):
            bedrock_models = await bedrock_service.list_models()
            all_provider_models.extend(bedrock_models)
            logger.info(f"Fetched {len(bedrock_models)} models from Bedrock.")
        else:
            logger.warning("Bedrock service does not have a callable list_models method.")
    except NotImplementedError:
        logger.info("Bedrock service list_models not yet implemented, skipping.")
    except ValueError as e:
        logger.warning(f"Could not get Bedrock service from factory: {e}")
    except Exception as e:
        logger.error(f"Error listing models from Bedrock: {e}")

    # Map List[ModelProviderInfo] to List[ModelInfo] for the response
    api_model_list: list[ModelInfo] = []
    for p_model in all_provider_models:
        api_model_list.append(
            ModelInfo(
                id=p_model.id,
                # object="model", # Default in ModelInfo
                owned_by=p_model.provider,  # Map provider to owned_by
                # created=p_model.created, # If ModelProviderInfo had created timestamp
                # display_name=p_model.display_name # If you want to include this
            )
        )

    if not api_model_list:
        logger.warning("No models could be fetched or mapped.")
        # Return based on spec: an object with an empty data list

    return ModelListResponse(data=api_model_list)


# TODO: Implement model listing endpoint
# @router.get("/v1/models")
