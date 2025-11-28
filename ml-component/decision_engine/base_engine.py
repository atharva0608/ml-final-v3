"""
Base Decision Engine - Pluggable Architecture
All decision engines must inherit from this base class
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class DecisionInput:
    """Standardized input format for decision engine"""
    timestamp: datetime
    cluster_id: str
    current_state: Dict[str, Any]  # Current cluster state
    requirements: Dict[str, Any]   # Required resources
    constraints: Dict[str, Any]    # Business constraints
    metadata: Dict[str, Any]       # Additional context


@dataclass
class DecisionOutput:
    """Standardized output format from decision engine"""
    timestamp: datetime
    decision_type: str             # spot_selection, bin_packing, rightsizing, etc.
    recommendations: List[Dict[str, Any]]
    confidence_score: float        # 0.0 to 1.0
    estimated_savings: float       # USD per month
    risk_assessment: Dict[str, Any]
    execution_plan: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class BaseDecisionEngine(ABC):
    """
    Base class for all decision engines
    Implements pluggable architecture with fixed input/output contracts
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.version = config.get('version', '1.0.0')
        self.enabled = config.get('enabled', True)

    @abstractmethod
    def analyze(self, input_data: DecisionInput) -> DecisionOutput:
        """
        Main analysis method - must be implemented by all engines

        Args:
            input_data: Standardized input containing cluster state and requirements

        Returns:
            DecisionOutput: Recommendations and execution plan
        """
        pass

    @abstractmethod
    def validate_input(self, input_data: DecisionInput) -> bool:
        """
        Validate input data before processing

        Args:
            input_data: Input to validate

        Returns:
            bool: True if valid, False otherwise
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Return engine metadata"""
        return {
            'name': self.name,
            'version': self.version,
            'enabled': self.enabled,
            'config': self.config
        }

    def to_json(self, output: DecisionOutput) -> str:
        """Serialize output to JSON"""
        return json.dumps({
            'timestamp': output.timestamp.isoformat(),
            'decision_type': output.decision_type,
            'recommendations': output.recommendations,
            'confidence_score': output.confidence_score,
            'estimated_savings': output.estimated_savings,
            'risk_assessment': output.risk_assessment,
            'execution_plan': output.execution_plan,
            'metadata': output.metadata
        }, indent=2)


class EngineRegistry:
    """Registry to manage multiple decision engines"""

    def __init__(self):
        self._engines: Dict[str, BaseDecisionEngine] = {}

    def register(self, name: str, engine: BaseDecisionEngine):
        """Register a new engine"""
        self._engines[name] = engine

    def get_engine(self, name: str) -> BaseDecisionEngine:
        """Get an engine by name"""
        if name not in self._engines:
            raise ValueError(f"Engine '{name}' not found in registry")
        return self._engines[name]

    def list_engines(self) -> List[str]:
        """List all registered engines"""
        return list(self._engines.keys())

    def get_enabled_engines(self) -> List[BaseDecisionEngine]:
        """Get all enabled engines"""
        return [engine for engine in self._engines.values() if engine.enabled]


# Global registry instance
engine_registry = EngineRegistry()
