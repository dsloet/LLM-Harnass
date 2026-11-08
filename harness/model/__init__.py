"""The model package: model clients and the factory that picks one."""
from harness.config import ModelSettings
from harness.model.base import ModelClient, ModelReply, ToolCall
from harness.model.ollama import ModelError, OllamaClient
from harness.model.scripted import ScriptedModel


def build_model(settings: ModelSettings) -> ModelClient:
    """Create the model client that the settings ask for.

    Args:
        settings: The model settings.

    Returns:
        A scripted model or an Ollama client.

    Raises:
        ValueError: If the provider is scripted but no scenario was given.
    """
    if settings.provider == "scripted":
        if not settings.scenario:
            raise ValueError("model.provider is 'scripted' but no scenario was given")
        return ScriptedModel(settings.scenario)
    return OllamaClient(settings)


__all__ = ["ModelClient", "ModelReply", "ToolCall", "ModelError", "build_model"]
