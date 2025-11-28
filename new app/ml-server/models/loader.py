"""
Model Loader Utilities

Handles loading, caching, and hot-reloading of ML models
"""

import logging
import pickle
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class ModelLoader:
    """
    ML Model Loader

    Manages loading and caching of uploaded ML models
    Supports hot-reloading without server restart
    """

    def __init__(self, models_dir: str = "/opt/ml-server/models/uploaded"):
        """
        Initialize model loader

        Args:
            models_dir: Directory containing uploaded models
        """
        self.models_dir = Path(models_dir)
        self.loaded_models: Dict[str, Any] = {}
        logger.info(f"Model loader initialized (dir: {models_dir})")

    def load_model(self, model_id: str, model_path: str) -> Any:
        """
        Load a model from file

        Args:
            model_id: Unique model identifier
            model_path: Path to model file (.pkl)

        Returns:
            Loaded model object

        Raises:
            FileNotFoundError: If model file doesn't exist
            ValueError: If model file is invalid
        """
        full_path = self.models_dir / model_path

        if not full_path.exists():
            raise FileNotFoundError(f"Model file not found: {full_path}")

        logger.info(f"Loading model {model_id} from {full_path}")

        try:
            with open(full_path, 'rb') as f:
                model = pickle.load(f)

            self.loaded_models[model_id] = model
            logger.info(f"✓ Model {model_id} loaded successfully")
            return model

        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            raise ValueError(f"Invalid model file: {e}")

    def get_model(self, model_id: str) -> Optional[Any]:
        """
        Get a loaded model from cache

        Args:
            model_id: Model identifier

        Returns:
            Model object or None if not loaded
        """
        return self.loaded_models.get(model_id)

    def reload_model(self, model_id: str, model_path: str) -> Any:
        """
        Reload a model (hot-reload)

        Args:
            model_id: Model identifier
            model_path: Path to model file

        Returns:
            Reloaded model object
        """
        logger.info(f"Reloading model {model_id}")

        # Remove from cache
        if model_id in self.loaded_models:
            del self.loaded_models[model_id]

        # Load fresh copy
        return self.load_model(model_id, model_path)

    def unload_model(self, model_id: str):
        """
        Unload a model from cache

        Args:
            model_id: Model identifier
        """
        if model_id in self.loaded_models:
            del self.loaded_models[model_id]
            logger.info(f"✓ Model {model_id} unloaded")

    def get_loaded_models(self) -> list:
        """
        Get list of loaded model IDs

        Returns:
            List of model IDs currently loaded
        """
        return list(self.loaded_models.keys())
