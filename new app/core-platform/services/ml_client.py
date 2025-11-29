"""
ML Server Client

Sends requests to ML Server for decision-making
Core Platform does NOT make optimization decisions - only executes them
"""

import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MLServerClient:
    """Client to communicate with ML Server for decision-making"""

    def __init__(self, ml_server_url: str, api_key: str):
        """
        Initialize ML Server client

        Args:
            ml_server_url: ML Server base URL (e.g., http://ml-server:8001)
            api_key: API key for authentication
        """
        self.base_url = ml_server_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0
        )
        logger.info(f"ML Server client initialized: {ml_server_url}")

    async def request_spot_optimization(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Request Spot instance optimization from ML Server

        Args:
            cluster_state: Current cluster state (nodes, pods, metrics)
            requirements: Optimization requirements
            constraints: Safety constraints

        Returns:
            Decision response with Spot recommendations
        """
        payload = {
            "cluster_state": cluster_state,
            "requirements": requirements,
            "constraints": constraints or {}
        }
       
        logger.info("Requesting Spot optimization from ML Server...")
        response = await self.client.post("/api/v1/ml/decision/spot-optimize", json=payload)
        response.raise_for_status()
       
        decision = response.json()
        logger.info(f"Received {len(decision['recommendations'])} Spot recommendations")
        return decision

    async def request_bin_packing(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request bin packing (consolidation) optimization"""
        payload = {"cluster_state": cluster_state, "requirements": requirements}
        response = await self.client.post("/api/v1/ml/decision/bin-pack", json=payload)
        response.raise_for_status()
        return response.json()

    async def request_rightsizing(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request instance rightsizing recommendations"""
        payload = {"cluster_state": cluster_state, "requirements": requirements}
        response = await self.client.post("/api/v1/ml/decision/rightsize", json=payload)
        response.raise_for_status()
        return response.json()

    async def request_ghost_probe(
        self,
        ec2_instances: list,
        k8s_node_instance_ids: list
    ) -> Dict[str, Any]:
        """Request ghost instance detection (zombie EC2 instances)"""
        payload = {
            "requirements": {
                "ec2_instances": ec2_instances,
                "k8s_node_instance_ids": k8s_node_instance_ids
            }
        }
        response = await self.client.post("/api/v1/ml/decision/ghost-probe", json=payload)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> Dict[str, Any]:
        """Check ML Server health"""
        response = await self.client.get("/api/v1/ml/health")
        response.raise_for_status()
        return response.json()
