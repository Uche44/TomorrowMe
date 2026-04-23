import logging

import httpx

from app.config import settings
from app.exceptions import (
    PersonaNotFoundError,
    ScenarioNotFoundError,
    UpstreamServiceError,
    UpstreamTimeoutError,
)
from app.models.upstream import Persona, Scenario

logger = logging.getLogger(__name__)


class UpstreamClient:
    def __init__(self) -> None:
        self._timeout = settings.upstream_timeout_sec

    async def get_persona(self, persona_id: str) -> Persona:
        url = f"{settings.persona_api_base_url}/persona/{persona_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
        except httpx.TimeoutException as exc:
            logger.error("UpstreamClient timeout fetching persona %s from %s", persona_id, url)
            raise UpstreamTimeoutError(f"Timeout fetching persona {persona_id}") from exc

        if response.status_code == 404:
            logger.error("PersonaGenerator_API 404 for persona_id=%s url=%s", persona_id, url)
            raise PersonaNotFoundError(f"Persona '{persona_id}' not found")
        if response.status_code >= 500:
            logger.error(
                "PersonaGenerator_API %d for persona_id=%s url=%s",
                response.status_code, persona_id, url,
            )
            raise UpstreamServiceError(
                f"PersonaGenerator_API returned {response.status_code} for persona {persona_id}"
            )
        response.raise_for_status()
        return Persona.model_validate(response.json())

    async def get_scenario(self, scenario_id: str) -> Scenario:
        url = f"{settings.scenario_api_base_url}/scenario/{scenario_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
        except httpx.TimeoutException as exc:
            logger.error("UpstreamClient timeout fetching scenario %s from %s", scenario_id, url)
            raise UpstreamTimeoutError(f"Timeout fetching scenario {scenario_id}") from exc

        if response.status_code == 404:
            logger.error("ScenarioEngine_API 404 for scenario_id=%s url=%s", scenario_id, url)
            raise ScenarioNotFoundError(f"Scenario '{scenario_id}' not found")
        if response.status_code >= 500:
            logger.error(
                "ScenarioEngine_API %d for scenario_id=%s url=%s",
                response.status_code, scenario_id, url,
            )
            raise UpstreamServiceError(
                f"ScenarioEngine_API returned {response.status_code} for scenario {scenario_id}"
            )
        response.raise_for_status()
        return Scenario.model_validate(response.json())
