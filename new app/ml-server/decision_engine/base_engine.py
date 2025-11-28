"""
Base Decision Engine

Abstract base class for all decision engines
Defines fixed input/output contract for pluggable architecture
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class BaseDecisionEngine(ABC):
    """
    Base class for all decision engines

    All decision engines must:
    - Accept ClusterState as input
    - Return DecisionResponse with recommendations
    - Provide confidence scores
    - Include execution plans
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize decision engine

        Args:
            config: Engine-specific configuration
        """
        self.config = config or {}
        self.engine_name = self.__class__.__name__
        logger.info(f"Initialized decision engine: {self.engine_name}")

    @abstractmethod
    def decide(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Make optimization decision

        Args:
            cluster_state: Current cluster state
                - nodes: List of node information
                - pods: List of pod information
                - metrics: Resource usage metrics
            requirements: Decision-specific requirements
            constraints: Safety constraints (optional)

        Returns:
            DecisionResponse:
                - recommendations: List of recommended actions
                - confidence_score: Confidence in decision (0.0-1.0)
                - estimated_savings: Estimated monthly savings (USD)
                - execution_plan: Step-by-step execution plan
        """
        pass

    def validate_input(self, cluster_state: Dict[str, Any]) -> bool:
        """
        Validate input cluster state

        Args:
            cluster_state: Cluster state to validate

        Returns:
            True if valid, raises exception otherwise
        """
        required_keys = ["nodes", "pods", "metrics"]
        for key in required_keys:
            if key not in cluster_state:
                raise ValueError(f"Missing required key in cluster_state: {key}")
        return True

    def create_response(
        self,
        recommendations: List[Dict[str, Any]],
        confidence_score: float,
        estimated_savings: Decimal,
        execution_plan: List[Dict[str, Any]],
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create standardized decision response

        Args:
            recommendations: List of recommendations
            confidence_score: Confidence (0.0-1.0)
            estimated_savings: Estimated monthly savings
            execution_plan: Execution steps
            metadata: Additional metadata

        Returns:
            Standardized decision response
        """
        return {
            "engine": self.engine_name,
            "recommendations": recommendations,
            "confidence_score": round(confidence_score, 4),
            "estimated_savings": float(estimated_savings),
            "execution_plan": execution_plan,
            "metadata": metadata or {}
        }
