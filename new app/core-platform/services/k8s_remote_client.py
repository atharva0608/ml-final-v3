"""
Remote Kubernetes API Client (AGENTLESS)

NO DaemonSets, NO client-side agents.
All operations via remote HTTPS calls to customer Kubernetes API server.
"""

from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class RemoteK8sClient:
    """
    Remote Kubernetes API Client
   
    Performs all operations via remote API calls (agentless architecture)
    """

    def __init__(self, api_endpoint: str, token: str):
        """
        Initialize remote K8s API client

        Args:
            api_endpoint: Kubernetes API server endpoint (https://...)
            token: Service account token
        """
        self.api_endpoint = api_endpoint
        self.token = token
        self.configuration = self._create_config()
        self.core_v1 = k8s_client.CoreV1Api(k8s_client.ApiClient(self.configuration))
        self.apps_v1 = k8s_client.AppsV1Api(k8s_client.ApiClient(self.configuration))
        logger.info(f"Initialized remote K8s client for {api_endpoint}")

    def _create_config(self):
        """Create Kubernetes API configuration"""
        config = k8s_client.Configuration()
        config.host = self.api_endpoint
        config.api_key = {"authorization": f"Bearer {self.token}"}
        config.verify_ssl = True  # TODO: Handle custom CAs
        return config

    # Node Operations
    def list_nodes(self) -> List[Dict[str, Any]]:
        """List all nodes in the cluster (remote API call)"""
        try:
            nodes = self.core_v1.list_node()
            return [
                {
                    "name": node.metadata.name,
                    "instance_id": node.spec.provider_id.split('/')[-1] if node.spec.provider_id else None,
                    "instance_type": node.metadata.labels.get("node.kubernetes.io/instance-type"),
                    "availability_zone": node.metadata.labels.get("topology.kubernetes.io/zone"),
                    "status": self._get_node_status(node),
                    "cpu_capacity": node.status.capacity.get("cpu"),
                    "memory_capacity": node.status.capacity.get("memory"),
                    "allocatable_cpu": node.status.allocatable.get("cpu"),
                    "allocatable_memory": node.status.allocatable.get("memory"),
                }
                for node in nodes.items
            ]
        except ApiException as e:
            logger.error(f"Failed to list nodes: {e}")
            raise

    def get_node_metrics(self) -> List[Dict[str, Any]]:
        """Get node metrics via Metrics API (remote API call)"""
        # TODO: Implement metrics API call
        # GET /apis/metrics.k8s.io/v1beta1/nodes
        logger.info("Fetching node metrics via remote Metrics API...")
        return []

    def drain_node(self, node_name: str, grace_period_seconds: int = 90) -> bool:
        """
        Drain node remotely (evict all pods)
       
        Args:
            node_name: Node to drain
            grace_period_seconds: Grace period for pod eviction
           
        Returns:
            True if successful
        """
        logger.info(f"Draining node {node_name} (grace period: {grace_period_seconds}s)")
       
        # 1. Cordon node first
        self.cordon_node(node_name)
       
        # 2. List pods on the node
        pods = self.core_v1.list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={node_name}"
        )
       
        # 3. Evict each pod
        for pod in pods.items:
            if pod.metadata.namespace == "kube-system":
                logger.info(f"Skipping kube-system pod: {pod.metadata.name}")
                continue
               
            try:
                eviction = k8s_client.V1Eviction(
                    metadata=k8s_client.V1ObjectMeta(
                        name=pod.metadata.name,
                        namespace=pod.metadata.namespace
                    ),
                    delete_options=k8s_client.V1DeleteOptions(
                        grace_period_seconds=grace_period_seconds
                    )
                )
                self.core_v1.create_namespaced_pod_eviction(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    body=eviction
                )
                logger.info(f"Evicted pod {pod.metadata.namespace}/{pod.metadata.name}")
            except ApiException as e:
                logger.warning(f"Failed to evict pod {pod.metadata.name}: {e}")
       
        return True

    def cordon_node(self, node_name: str) -> bool:
        """Cordon node remotely (mark as unschedulable)"""
        try:
            body = {"spec": {"unschedulable": True}}
            self.core_v1.patch_node(node_name, body)
            logger.info(f"Cordoned node {node_name}")
            return True
        except ApiException as e:
            logger.error(f"Failed to cordon node {node_name}: {e}")
            raise

    def uncordon_node(self, node_name: str) -> bool:
        """Uncordon node remotely (mark as schedulable)"""
        try:
            body = {"spec": {"unschedulable": False}}
            self.core_v1.patch_node(node_name, body)
            logger.info(f"Uncordoned node {node_name}")
            return True
        except ApiException as e:
            logger.error(f"Failed to uncordon node {node_name}: {e}")
            raise

    # Pod Operations
    def list_pods(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """List pods (all namespaces or specific namespace)"""
        try:
            if namespace:
                pods = self.core_v1.list_namespaced_pod(namespace)
            else:
                pods = self.core_v1.list_pod_for_all_namespaces()
           
            return [
                {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "node_name": pod.spec.node_name,
                    "status": pod.status.phase,
                    "cpu_request": self._get_resource_requests(pod, "cpu"),
                    "memory_request": self._get_resource_requests(pod, "memory"),
                }
                for pod in pods.items
            ]
        except ApiException as e:
            logger.error(f"Failed to list pods: {e}")
            raise

    # Deployment Operations
    def scale_deployment(self, namespace: str, deployment_name: str, replicas: int) -> bool:
        """Scale deployment remotely"""
        try:
            body = {"spec": {"replicas": replicas}}
            self.apps_v1.patch_namespaced_deployment_scale(
                name=deployment_name,
                namespace=namespace,
                body=body
            )
            logger.info(f"Scaled deployment {namespace}/{deployment_name} to {replicas} replicas")
            return True
        except ApiException as e:
            logger.error(f"Failed to scale deployment: {e}")
            raise

    # Helper methods
    def _get_node_status(self, node) -> str:
        """Get node status from conditions"""
        for condition in node.status.conditions:
            if condition.type == "Ready":
                return "Ready" if condition.status == "True" else "NotReady"
        return "Unknown"

    def _get_resource_requests(self, pod, resource_type: str) -> str:
        """Get total resource requests for a pod"""
        total = 0
        for container in pod.spec.containers:
            if container.resources and container.resources.requests:
                req = container.resources.requests.get(resource_type, "0")
                # TODO: Parse CPU/memory units properly
                total += 1
        return str(total)
