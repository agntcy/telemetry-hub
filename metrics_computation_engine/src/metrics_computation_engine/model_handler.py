# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Callable
import asyncio
import hashlib
import json
from importlib.metadata import entry_points

from metrics_computation_engine.models.requests import LLMJudgeConfig


MODEL_TIMEOUT = 3600  # one hour


class ModelContainer:
    def __init__(self, model, is_default: bool = False):
        self.model: Any = model
        self.last_accessed: datetime = datetime.now(timezone.utc)
        self.is_default: bool = is_default

    def get_model(self) -> Any:
        return self.model

    def is_default(self) -> bool:
        return self.is_default

    def set_last_accessed(self):
        self.last_accessed = datetime.now(timezone.utc)

    def get_last_accessed(self) -> datetime:
        return self.last_accessed


class ModelHandler:
    """Model handler, a centralised way to store LLMs models with plugin support"""

    def __init__(self):
        self.models_per_provider_map: Dict[str, Dict[str, ModelContainer]] = {}
        self.lock = asyncio.Lock()
        self._model_loaders: Dict[str, Callable[[LLMJudgeConfig], Any]] = {}
        self._register_plugin_providers()

    def _create_config_key(self, llm_config: LLMJudgeConfig) -> str:
        """Create a hashable key from LLMJudgeConfig"""
        # Extract the relevant fields and create a deterministic hash
        config_dict = {
            "LLM_BASE_MODEL_URL": getattr(llm_config, "LLM_BASE_MODEL_URL", ""),
            "LLM_MODEL_NAME": getattr(llm_config, "LLM_MODEL_NAME", ""),
            # Hashing the api key hash instead of the api key itself.
            "LLM_API_KEY_HASH": hashlib.sha256(
                getattr(llm_config, "LLM_API_KEY", "").encode()
            ).hexdigest()[:16],
        }

        config_str = json.dumps(config_dict, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    def _is_default_config(self, llm_config: LLMJudgeConfig) -> bool:
        """Check if this is the default configuration"""
        default_config = LLMJudgeConfig()
        return (
            getattr(llm_config, "LLM_BASE_MODEL_URL", "")
            == getattr(default_config, "LLM_BASE_MODEL_URL", "")
            and getattr(llm_config, "LLM_MODEL_NAME", "")
            == getattr(default_config, "LLM_MODEL_NAME", "")
            and getattr(llm_config, "LLM_API_KEY", "")
            == getattr(default_config, "LLM_API_KEY", "")
        )

    def _register_plugin_providers(self):
        """Register model loaders from plugins using entry points"""
        try:
            # Get entry points for model loader plugins
            eps = entry_points(group="metrics_computation_engine.model_loaders")
        except TypeError:
            # Fallback for older Python versions
            eps = entry_points().get("metrics_computation_engine.model_loaders", [])

        for entry_point in eps:
            try:
                loader_func = entry_point.load()
                provider_name = entry_point.name
                self.register_provider(provider_name, loader_func)
                print(f"Registered model loader for provider: {provider_name}")
            except Exception as e:
                print(f"Warning: Failed to load model loader '{entry_point.name}': {e}")

    def register_provider(
        self, provider_name: str, loader_func: Callable[[LLMJudgeConfig], Any]
    ):
        """Register a model loader function for a specific provider"""
        self._model_loaders[provider_name] = loader_func

    async def get_model(
        self, provider: str, llm_config: LLMJudgeConfig
    ) -> Optional[Any]:
        """Get a model for the specified provider and config, creating it if necessary"""
        config_key = self._create_config_key(llm_config)

        async with self.lock:
            # Check if model already exists
            provider_map = self.models_per_provider_map.get(provider, {})
            model_container = provider_map.get(config_key)

            if model_container is not None:
                # Model exists, update access time and return
                model_container.set_last_accessed()
                return model_container.get_model()

            # Model doesn't exist, try to create it
            model = await self._create_model(provider, llm_config)
            if model is not None:
                # Store the newly created model
                await self._store_model(provider, llm_config, model)
                return model

            return None

    async def _create_model(
        self, provider: str, llm_config: LLMJudgeConfig
    ) -> Optional[Any]:
        """Create a model using the registered loader for the provider"""
        loader_func = self._model_loaders.get(provider)
        if loader_func is None:
            print(f"Warning: No model loader registered for provider '{provider}'")
            return None

        try:
            model = loader_func(llm_config)
            return model
        except Exception as e:
            print(f"Error creating model for provider '{provider}': {e}")
            return None

    async def _store_model(self, provider: str, llm_config: LLMJudgeConfig, model: Any):
        """Store a model in the cache"""
        config_key = self._create_config_key(llm_config)

        if provider not in self.models_per_provider_map:
            self.models_per_provider_map[provider] = {}

        is_default_config = self._is_default_config(llm_config)
        model_container = ModelContainer(model, is_default=is_default_config)
        self.models_per_provider_map[provider][config_key] = model_container

    async def set_model(
        self, provider: str, llm_config: LLMJudgeConfig, model: Any
    ) -> bool:
        """Manually set a model for a provider and config"""
        if model is None:
            return False

        async with self.lock:
            await self._store_model(provider, llm_config, model)
            return True

    async def get_or_create_model(
        self, provider: str, llm_config: LLMJudgeConfig
    ) -> Optional[Any]:
        """Get existing model or create new one - this is the main method to use"""
        return await self.get_model(provider, llm_config)

    def garbage_collection(self):
        """Remove models that haven't been accessed for a while"""

        async def _async_garbage_collection():
            async with self.lock:
                current_time = datetime.now(timezone.utc)

                for provider_name, provider_map in self.models_per_provider_map.items():
                    erase_list = []

                    for config_key, model_container in provider_map.items():
                        if model_container.is_default():
                            # Don't delete default models
                            continue

                        delta = current_time - model_container.get_last_accessed()
                        if delta.total_seconds() > MODEL_TIMEOUT:
                            erase_list.append(config_key)

                    for config_key in erase_list:
                        del provider_map[config_key]
                        print(
                            f"Garbage collected model for provider '{provider_name}' with config key {config_key}"
                        )

        # If we're in an async context, await this
        return _async_garbage_collection()

    def list_providers(self) -> list[str]:
        """List all registered providers"""
        return list(self._model_loaders.keys())

    def list_cached_models(self) -> Dict[str, list[str]]:
        """List all currently cached models by provider (showing config keys)"""
        result = {}
        for provider, provider_map in self.models_per_provider_map.items():
            result[provider] = list(provider_map.keys())
        return result
