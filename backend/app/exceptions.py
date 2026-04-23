class DialogueGeneratorError(Exception):
    pass


# Upstream errors
class UpstreamError(DialogueGeneratorError):
    pass


class PersonaNotFoundError(UpstreamError):
    pass


class ScenarioNotFoundError(UpstreamError):
    pass


class UpstreamServiceError(UpstreamError):
    pass


class UpstreamTimeoutError(UpstreamError):
    pass


# LLM errors
class LLMError(DialogueGeneratorError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMProviderError(LLMError):
    pass


class ScriptQualityError(LLMError):
    pass


# Store errors
class StoreError(DialogueGeneratorError):
    pass
