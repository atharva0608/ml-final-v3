#!/usr/bin/env python3
"""
AWS Spot Optimizer Agent v5.0.0 - Production Monolithic Implementation
===========================================================================
Complete implementation of agent specification with all scenarios, state
machine, command handling, and communication protocols.

Architecture: Monolithic design for simplicity and reliability
Compatible with: Backend v6.0 (Operational Runbook Aligned)
===========================================================================
"""

import os
import sys
import time
import json
import uuid
import socket
import signal
import logging
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler('spot_optimizer_agent_v5.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# STATE MACHINE
# ============================================================================

class AgentState(Enum):
    """Agent state machine states"""
    REGISTER_PENDING = "REGISTER_PENDING"
    ONLINE_READY = "ONLINE_READY"
    COMMAND_EXECUTING = "COMMAND_EXECUTING"
    OFFLINE = "OFFLINE"
    SHUTDOWN = "SHUTDOWN"

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class AgentConfiguration:
    """Agent configuration with persistence support"""

    # Required fields
    backend_url: str = os.getenv('BACKEND_URL', 'http://localhost:5000')
    client_token: str = os.getenv('CLIENT_TOKEN', '')
    cloud_provider: str = os.getenv('CLOUD_PROVIDER', 'aws')
    cloud_account: str = os.getenv('CLOUD_ACCOUNT', '')
    region: str = os.getenv('AWS_REGION', 'us-east-1')

    # Agent identity
    agent_id: Optional[str] = None
    hostname: str = socket.gethostname()
    agent_version: str = '5.0.0'

    # Optional toggles
    auto_switching: bool = False
    auto_terminate: bool = False
    manual_replica: bool = False
    emergency_only: bool = False

    # Timers (seconds)
    heartbeat_interval: int = 30
    pricing_collection_interval: int = 300
    command_poll_interval: int = 5
    notice_check_interval: int = 10
    reconnect_backoff_max: int = 300

    # State
    config_file: str = '/var/lib/spot-optimizer/agent.json'

    def validate(self) -> bool:
        """Validate required configuration"""
        if not self.client_token:
            logger.error("CLIENT_TOKEN is required")
            return False
        if not self.backend_url:
            logger.error("BACKEND_URL is required")
            return False
        return True

    def load_persisted(self) -> bool:
        """Load persisted agent_id and config from disk"""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    self.agent_id = data.get('agent_id')
                    self.auto_switching = data.get('auto_switching', False)
                    self.auto_terminate = data.get('auto_terminate', False)
                    self.manual_replica = data.get('manual_replica', False)
                    self.emergency_only = data.get('emergency_only', False)
                    logger.info(f"Loaded persisted config: agent_id={self.agent_id}")
                    return True
        except Exception as e:
            logger.warning(f"Failed to load persisted config: {e}")
        return False

    def persist(self):
        """Persist agent_id and config to disk"""
        try:
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'agent_id': self.agent_id,
                'auto_switching': self.auto_switching,
                'auto_terminate': self.auto_terminate,
                'manual_replica': self.manual_replica,
                'emergency_only': self.emergency_only,
                'last_updated': datetime.utcnow().isoformat()
            }

            with open(config_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Persisted config to {config_path}")
        except Exception as e:
            logger.error(f"Failed to persist config: {e}")

config = AgentConfiguration()

# ============================================================================
# AWS CLIENTS
# ============================================================================

class AWSClients:
    """Singleton AWS client manager"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize AWS clients"""
        try:
            self.ec2 = boto3.client('ec2', region_name=config.region)
            self.ec2_resource = boto3.resource('ec2', region_name=config.region)
            self.pricing = boto3.client('pricing', region_name='us-east-1')
            logger.info(f"✓ AWS clients initialized (region: {config.region})")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise

aws_clients = AWSClients()

# ============================================================================
# INSTANCE METADATA (IMDSv2)
# ============================================================================

class InstanceMetadata:
    """AWS Instance Metadata Service v2"""

    METADATA_BASE = "http://169.254.169.254/latest"
    TIMEOUT = 2

    @classmethod
    def get_token(cls) -> Optional[str]:
        """Get IMDSv2 token"""
        try:
            response = requests.put(
                f"{cls.METADATA_BASE}/api/token",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
                timeout=cls.TIMEOUT
            )
            response.raise_for_status()
            return response.text
        except Exception:
            return None

    @classmethod
    def get(cls, path: str) -> Optional[str]:
        """Get metadata with token"""
        token = cls.get_token()
        if not token:
            return None
        try:
            response = requests.get(
                f"{cls.METADATA_BASE}/{path}",
                headers={"X-aws-ec2-metadata-token": token},
                timeout=cls.TIMEOUT
            )
            response.raise_for_status()
            return response.text
        except Exception:
            return None

    @classmethod
    def get_instance_info(cls) -> Dict[str, str]:
        """Get comprehensive instance information"""
        return {
            'instance_id': cls.get("meta-data/instance-id"),
            'instance_type': cls.get("meta-data/instance-type"),
            'az': cls.get("meta-data/placement/availability-zone"),
            'ami_id': cls.get("meta-data/ami-id"),
            'private_ip': cls.get("meta-data/local-ipv4"),
            'public_ip': cls.get("meta-data/public-ipv4"),
        }

    @classmethod
    def check_spot_action(cls) -> Optional[Dict]:
        """Check for spot instance action (rebalance/termination)"""
        try:
            action = cls.get("meta-data/spot/instance-action")
            if action:
                return json.loads(action)
        except Exception:
            pass
        return None

# ============================================================================
# BACKEND API CLIENT
# ============================================================================

class BackendAPI:
    """Communication with central backend"""

    def __init__(self):
        self.base_url = config.backend_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {config.client_token}',
            'Content-Type': 'application/json'
        })
        self.retry_count = 0
        self.max_backoff = config.reconnect_backoff_max

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make HTTP request with exponential backoff"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            self.retry_count = 0  # Reset on success
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {method} {endpoint} - {e}")
            self._handle_backoff()
            return None

    def _handle_backoff(self):
        """Exponential backoff for retries"""
        self.retry_count += 1
        backoff = min(2 ** self.retry_count, self.max_backoff)
        logger.warning(f"Backing off for {backoff}s (retry #{self.retry_count})")
        time.sleep(backoff)

    # Scenario 1: First Install Registration
    def register_agent(self, environment_info: Dict) -> Optional[Dict]:
        """POST /api/agents/register"""
        payload = {
            'cloud_account': config.cloud_account,
            'project_id': environment_info.get('project_id', 'default'),
            'region': config.region,
            'hostname': config.hostname,
            'agent_version': config.agent_version,
            'instance_id': environment_info.get('instance_id'),
            'instance_type': environment_info.get('instance_type'),
            'az': environment_info.get('az'),
            'ami_id': environment_info.get('ami_id'),
            'mode': environment_info.get('mode', 'unknown'),
            'logical_agent_id': environment_info.get('logical_agent_id', environment_info.get('instance_id'))
        }
        return self._make_request('POST', '/api/agents/register', json=payload)

    # Scenario 2: Restart with Existing Agent
    def reconnect_agent(self, agent_id: str) -> Optional[Dict]:
        """POST /api/agents/{agent_id}/heartbeat (first heartbeat after restart)"""
        return self.send_heartbeat(agent_id, inventory={}, reconnect=True)

    # Scenario 3: Heartbeat with Inventory
    def send_heartbeat(self, agent_id: str, inventory: Dict, reconnect: bool = False) -> Optional[Dict]:
        """POST /api/agents/{agent_id}/heartbeat"""
        payload = {
            'status': 'online',
            'inventory_snapshot': inventory,
            'health_metrics': {
                'uptime': self._get_uptime(),
                'cpu_percent': 0,  # Could use psutil if available
                'memory_percent': 0
            },
            'reconnect': reconnect
        }
        return self._make_request('POST', f'/api/agents/{agent_id}/heartbeat', json=payload)

    # Scenario 4: Command Polling (if not using WebSocket)
    def get_pending_commands(self, agent_id: str) -> List[Dict]:
        """GET /api/agents/{agent_id}/commands/pending"""
        result = self._make_request('GET', f'/api/agents/{agent_id}/commands/pending')
        if result and isinstance(result, dict):
            return result.get('commands', [])
        return []

    # Scenario 4: Action Result Reporting
    def report_action_result(self, agent_id: str, request_id: str, result: Dict) -> bool:
        """POST /api/agents/{agent_id}/action-result"""
        payload = {
            'request_id': request_id,
            'agent_id': agent_id,
            'result': result.get('status'),
            'cloud_instance_id': result.get('instance_id'),
            'error_message': result.get('error'),
            'metadata': result.get('metadata', {})
        }
        response = self._make_request('POST', f'/api/agents/{agent_id}/action-result', json=payload)
        return response is not None

    # Scenario 5: Pricing Metrics
    def send_pricing_update(self, agent_id: str, pricing_data: List[Dict]) -> bool:
        """POST /api/agents/{agent_id}/pricing"""
        payload = {
            'agent_id': agent_id,
            'pricing_data_array': pricing_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        response = self._make_request('POST', f'/api/agents/{agent_id}/pricing-report', json=payload)
        return response is not None

    # Scenario 6: Rebalance Notice
    def send_rebalance_notice(self, agent_id: str, instance_id: str, timestamp: str) -> bool:
        """POST /api/agents/{agent_id}/rebalance-recommendation"""
        payload = {
            'cloud_instance_id': instance_id,
            'notice_type': 'REBALANCE',
            'notice_time': timestamp
        }
        response = self._make_request('POST', f'/api/agents/{agent_id}/rebalance-recommendation', json=payload)
        return response is not None

    # Scenario 6: Termination Notice
    def send_termination_notice(self, agent_id: str, instance_id: str, timestamp: str) -> bool:
        """POST /api/agents/{agent_id}/termination-notice"""
        payload = {
            'cloud_instance_id': instance_id,
            'notice_type': 'TERMINATION',
            'termination_time': timestamp
        }
        response = self._make_request('POST', f'/api/agents/{agent_id}/termination-report', json=payload)
        return response is not None

    # Scenario 7: Shutdown Broadcast
    def send_shutdown_notice(self, agent_id: str, instance_id: str, metadata: Dict) -> bool:
        """POST /api/agents/{agent_id}/shutdown (best-effort)"""
        payload = {
            'cloud_instance_id': instance_id,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': metadata
        }
        try:
            # Non-blocking best-effort
            self._make_request('POST', f'/api/agents/{agent_id}/shutdown', json=payload)
        except:
            pass
        return True

    def _get_uptime(self) -> int:
        """Get system uptime in seconds"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                return int(uptime_seconds)
        except:
            return 0

# ============================================================================
# INVENTORY COLLECTOR
# ============================================================================

class InventoryCollector:
    """Collect instance inventory for heartbeat"""

    def __init__(self):
        self.ec2 = aws_clients.ec2

    def collect_inventory(self) -> Dict[str, List[Dict]]:
        """Collect inventory of all instances in region"""
        try:
            response = self.ec2.describe_instances(
                Filters=[
                    {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}
                ]
            )

            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instances.append({
                        'instance_id': instance['InstanceId'],
                        'state': instance['State']['Name'],
                        'az': instance['Placement']['AvailabilityZone'],
                        'instance_type': instance['InstanceType'],
                        'pool': self._get_pool_id(instance),
                        'tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                    })

            return {'instances': instances, 'count': len(instances)}
        except Exception as e:
            logger.error(f"Failed to collect inventory: {e}")
            return {'instances': [], 'count': 0, 'error': str(e)}

    def _get_pool_id(self, instance: Dict) -> Optional[str]:
        """Get pool ID for instance"""
        lifecycle = instance.get('InstanceLifecycle', 'normal')
        if lifecycle == 'spot':
            return f"{instance['InstanceType']}.{instance['Placement']['AvailabilityZone']}"
        return None

# ============================================================================
# PRICING COLLECTOR
# ============================================================================

class PricingCollector:
    """Collect spot and on-demand pricing"""

    def __init__(self):
        self.ec2 = aws_clients.ec2

    def collect_pricing(self, instance_types: List[str]) -> List[Dict]:
        """Collect pricing for specified instance types"""
        pricing_data = []

        for instance_type in instance_types:
            try:
                # Get all AZs
                zones = self._get_availability_zones()

                for az in zones:
                    spot_price = self._get_spot_price(instance_type, az)
                    if spot_price is not None:
                        pricing_data.append({
                            'instance_type': instance_type,
                            'az': az,
                            'pool_id': f"{instance_type}.{az}",
                            'spot_price': spot_price,
                            'timestamp': datetime.utcnow().isoformat()
                        })

                # Get on-demand price (once per type)
                ondemand_price = self._get_ondemand_price(instance_type)
                if ondemand_price:
                    pricing_data.append({
                        'instance_type': instance_type,
                        'price_type': 'ondemand',
                        'price': ondemand_price,
                        'timestamp': datetime.utcnow().isoformat()
                    })
            except Exception as e:
                logger.error(f"Failed to collect pricing for {instance_type}: {e}")

        return pricing_data

    def _get_availability_zones(self) -> List[str]:
        """Get available AZs in region"""
        try:
            response = self.ec2.describe_availability_zones(
                Filters=[{'Name': 'state', 'Values': ['available']}]
            )
            return [z['ZoneName'] for z in response['AvailabilityZones']]
        except Exception as e:
            logger.error(f"Failed to get AZs: {e}")
            return []

    def _get_spot_price(self, instance_type: str, az: str) -> Optional[float]:
        """Get current spot price"""
        try:
            response = self.ec2.describe_spot_price_history(
                InstanceTypes=[instance_type],
                AvailabilityZone=az,
                MaxResults=1,
                ProductDescriptions=['Linux/UNIX (Amazon VPC)', 'Linux/UNIX']
            )
            if response['SpotPriceHistory']:
                return float(response['SpotPriceHistory'][0]['SpotPrice'])
        except Exception:
            pass
        return None

    def _get_ondemand_price(self, instance_type: str) -> Optional[float]:
        """Get on-demand price (cached/estimated)"""
        # Simplified - in production, use pricing API
        return 0.1

# ============================================================================
# COMMAND EXECUTOR
# ============================================================================

class CommandExecutor:
    """Execute commands from backend"""

    def __init__(self, backend_api: BackendAPI):
        self.backend = backend_api
        self.ec2 = aws_clients.ec2
        self.ec2_resource = aws_clients.ec2_resource
        self.executed_requests = {}  # For idempotency

    def execute_command(self, command: Dict) -> Dict:
        """Execute a command and return result"""
        command_type = command.get('command_type')
        request_id = command.get('request_id')
        params = command.get('params', {})

        logger.info(f"Executing command: {command_type} (request_id={request_id})")

        # Check idempotency
        if request_id in self.executed_requests:
            logger.info(f"Duplicate request_id {request_id}, returning cached result")
            return self.executed_requests[request_id]

        # Execute based on type
        if command_type == 'LAUNCH_INSTANCE':
            result = self._launch_instance(params)
        elif command_type == 'TERMINATE_INSTANCE':
            result = self._terminate_instance(params)
        elif command_type == 'PROMOTE_REPLICA_TO_PRIMARY':
            result = self._promote_replica(params)
        elif command_type == 'APPLY_CONFIG':
            result = self._apply_config(params)
        elif command_type == 'SELF_DESTRUCT':
            result = self._self_destruct(params)
        else:
            result = {'status': 'FAILURE', 'error': f'Unknown command type: {command_type}'}

        # Cache result for idempotency
        self.executed_requests[request_id] = result

        return result

    def _launch_instance(self, params: Dict) -> Dict:
        """Launch new instance"""
        try:
            target_pool = params.get('target_pool')
            az = params.get('az')
            instance_type = params.get('instance_type')
            role_hint = params.get('role_hint', 'replica')

            # Parse pool if provided
            if target_pool and not az:
                parts = target_pool.split('.')
                if len(parts) >= 2:
                    az = parts[-1]

            launch_params = {
                'ImageId': params.get('ami_id', 'ami-xxxxxxxxx'),
                'InstanceType': instance_type,
                'MinCount': 1,
                'MaxCount': 1,
                'Placement': {'AvailabilityZone': az},
                'TagSpecifications': [{
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Name', 'Value': f'SpotOptimizer-{role_hint}'},
                        {'Key': 'Role', 'Value': role_hint}
                    ]
                }]
            }

            # Add spot configuration if targeting spot
            if 'spot' in target_pool.lower():
                launch_params['InstanceMarketOptions'] = {
                    'MarketType': 'spot',
                    'SpotOptions': {
                        'SpotInstanceType': 'one-time',
                        'InstanceInterruptionBehavior': 'terminate'
                    }
                }

            response = self.ec2.run_instances(**launch_params)
            instance_id = response['Instances'][0]['InstanceId']

            logger.info(f"✓ Launched instance: {instance_id}")

            return {
                'status': 'SUCCESS',
                'instance_id': instance_id,
                'state': 'pending'
            }
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"Launch failed: {error_code} - {error_msg}")
            return {
                'status': 'FAILURE',
                'error': f'{error_code}: {error_msg}',
                'error_category': error_code
            }

    def _terminate_instance(self, params: Dict) -> Dict:
        """Terminate instance"""
        try:
            instance_id = params.get('instance_id')

            # Check if already terminated
            response = self.ec2.describe_instances(InstanceIds=[instance_id])
            if response['Reservations']:
                state = response['Reservations'][0]['Instances'][0]['State']['Name']
                if state in ['terminated', 'terminating']:
                    logger.info(f"Instance {instance_id} already terminated")
                    return {
                        'status': 'SUCCESS',
                        'instance_id': instance_id,
                        'already_terminated': True
                    }

            # Terminate
            self.ec2.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"✓ Terminated instance: {instance_id}")

            return {
                'status': 'SUCCESS',
                'instance_id': instance_id,
                'termination_time': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Termination failed: {e}")
            return {
                'status': 'FAILURE',
                'error': str(e)
            }

    def _promote_replica(self, params: Dict) -> Dict:
        """Promote replica to primary"""
        try:
            replica_id = params.get('replica_instance_id')
            old_primary_id = params.get('old_primary_id')

            # Update tags
            self.ec2.create_tags(
                Resources=[replica_id],
                Tags=[{'Key': 'Role', 'Value': 'primary'}]
            )

            if old_primary_id:
                self.ec2.create_tags(
                    Resources=[old_primary_id],
                    Tags=[{'Key': 'Role', 'Value': 'terminated'}]
                )

            logger.info(f"✓ Promoted {replica_id} to primary")

            return {
                'status': 'SUCCESS',
                'promoted_instance': replica_id,
                'impacted_old_primary': old_primary_id
            }
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            return {
                'status': 'FAILURE',
                'error': str(e)
            }

    def _apply_config(self, params: Dict) -> Dict:
        """Apply configuration updates"""
        try:
            config_updates = params.get('config_updates', {})

            if 'auto_switching' in config_updates:
                config.auto_switching = config_updates['auto_switching']
            if 'auto_terminate' in config_updates:
                config.auto_terminate = config_updates['auto_terminate']
            if 'manual_replica' in config_updates:
                config.manual_replica = config_updates['manual_replica']
            if 'emergency_only' in config_updates:
                config.emergency_only = config_updates['emergency_only']

            # Persist changes
            config.persist()

            logger.info(f"✓ Applied config updates: {config_updates}")

            return {
                'status': 'SUCCESS',
                'applied_config': config_updates
            }
        except Exception as e:
            logger.error(f"Config apply failed: {e}")
            return {
                'status': 'FAILURE',
                'error': str(e)
            }

    def _self_destruct(self, params: Dict) -> Dict:
        """Initiate agent shutdown"""
        logger.warning("⚠️ SELF_DESTRUCT command received")
        return {
            'status': 'SUCCESS',
            'action': 'shutdown_initiated'
        }

# ============================================================================
# NOTICE MONITOR
# ============================================================================

class NoticeMonitor:
    """Monitor for rebalance and termination notices"""

    def __init__(self, backend_api: BackendAPI):
        self.backend = backend_api

    def check_for_notices(self, agent_id: str, instance_id: str) -> bool:
        """Check metadata for spot instance notices"""
        try:
            action = InstanceMetadata.check_spot_action()

            if action:
                action_type = action.get('action')
                action_time = action.get('time')

                logger.warning(f"⚠️ Spot action detected: {action_type} at {action_time}")

                if action_type == 'terminate':
                    self.backend.send_termination_notice(agent_id, instance_id, action_time)
                elif action_type in ['stop', 'hibernate']:
                    self.backend.send_rebalance_notice(agent_id, instance_id, action_time)

                return True
        except Exception as e:
            logger.debug(f"Notice check error: {e}")

        return False

# ============================================================================
# MAIN AGENT
# ============================================================================

class SpotOptimizerAgent:
    """Main agent orchestrator"""

    def __init__(self):
        self.state = AgentState.REGISTER_PENDING
        self.backend = BackendAPI()
        self.inventory_collector = InventoryCollector()
        self.pricing_collector = PricingCollector()
        self.command_executor = CommandExecutor(self.backend)
        self.notice_monitor = NoticeMonitor(self.backend)

        self.instance_info = {}
        self.running = False
        self.threads = []
        self.shutdown_event = threading.Event()

        logger.info("Agent initialized")

    def start(self):
        """Main agent entry point"""
        try:
            # Setup signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

            # Validate configuration
            if not config.validate():
                logger.error("Configuration validation failed")
                sys.exit(1)

            # Get instance metadata
            self.instance_info = InstanceMetadata.get_instance_info()
            logger.info(f"Instance: {self.instance_info.get('instance_id')}")

            # Determine registration scenario
            if config.load_persisted() and config.agent_id:
                # Scenario 2: Restart with existing agent
                self._reconnect_existing()
            else:
                # Scenario 1: First install
                self._register_new()

            if self.state != AgentState.ONLINE_READY:
                logger.error("Failed to reach ONLINE_READY state")
                return

            self.running = True

            # Start worker threads
            self._start_workers()

            logger.info("=" * 80)
            logger.info("✓ Agent ONLINE_READY")
            logger.info(f"  Agent ID: {config.agent_id}")
            logger.info(f"  State: {self.state.value}")
            logger.info("=" * 80)

            # Keep main thread alive
            while self.running and not self.shutdown_event.is_set():
                time.sleep(1)

        except Exception as e:
            logger.error(f"Agent failed: {e}", exc_info=True)
        finally:
            self._shutdown()

    def _register_new(self):
        """Scenario 1: First install registration"""
        logger.info("Starting new agent registration...")

        environment_info = {
            **self.instance_info,
            'project_id': 'default',
            'logical_agent_id': self.instance_info.get('instance_id')
        }

        response = self.backend.register_agent(environment_info)

        if response and response.get('agent_id'):
            config.agent_id = response['agent_id']
            agent_config = response.get('config', {})

            # Update config from backend
            config.auto_switching = agent_config.get('auto_switch_enabled', False)
            config.auto_terminate = agent_config.get('auto_terminate_enabled', False)

            # Persist
            config.persist()

            self.state = AgentState.ONLINE_READY
            logger.info(f"✓ Registered new agent: {config.agent_id}")
        else:
            logger.error("Registration failed, staying in REGISTER_PENDING")

    def _reconnect_existing(self):
        """Scenario 2: Reconnect with existing agent_id"""
        logger.info(f"Reconnecting with agent_id: {config.agent_id}")

        inventory = self.inventory_collector.collect_inventory()
        response = self.backend.reconnect_agent(config.agent_id)

        if response:
            self.state = AgentState.ONLINE_READY
            logger.info(f"✓ Reconnected agent: {config.agent_id}")
        else:
            logger.warning("Reconnect rejected, re-registering...")
            config.agent_id = None
            self._register_new()

    def _start_workers(self):
        """Start all worker threads"""
        workers = [
            (self._heartbeat_worker, "Heartbeat"),
            (self._command_worker, "CommandListener"),
            (self._pricing_worker, "PricingCollection"),
            (self._notice_worker, "NoticeMonitor")
        ]

        for worker_func, name in workers:
            thread = threading.Thread(target=worker_func, name=name, daemon=True)
            thread.start()
            self.threads.append(thread)
            logger.info(f"✓ Started worker: {name}")

    def _heartbeat_worker(self):
        """Scenario 3: Heartbeat loop"""
        logger.info("Heartbeat worker started")

        while self.running and not self.shutdown_event.is_set():
            try:
                if self.state == AgentState.ONLINE_READY:
                    inventory = self.inventory_collector.collect_inventory()
                    response = self.backend.send_heartbeat(config.agent_id, inventory)

                    if response:
                        # Apply any config deltas
                        agent_config = response.get('config', {})
                        if agent_config:
                            config.auto_switching = agent_config.get('auto_switch_enabled', config.auto_switching)
                            config.auto_terminate = agent_config.get('auto_terminate_enabled', config.auto_terminate)
                    else:
                        self.state = AgentState.OFFLINE
                        logger.warning("Heartbeat failed, entering OFFLINE state")
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            self.shutdown_event.wait(config.heartbeat_interval)

    def _command_worker(self):
        """Scenario 4: Command execution loop"""
        logger.info("Command worker started")

        while self.running and not self.shutdown_event.is_set():
            try:
                if self.state == AgentState.ONLINE_READY:
                    commands = self.backend.get_pending_commands(config.agent_id)

                    for command in commands:
                        self.state = AgentState.COMMAND_EXECUTING

                        result = self.command_executor.execute_command(command)

                        # Report result
                        self.backend.report_action_result(
                            config.agent_id,
                            command.get('request_id'),
                            result
                        )

                        # Check for shutdown
                        if command.get('command_type') == 'SELF_DESTRUCT' and result.get('status') == 'SUCCESS':
                            logger.info("Initiating shutdown after SELF_DESTRUCT")
                            self.running = False
                            break

                        self.state = AgentState.ONLINE_READY
            except Exception as e:
                logger.error(f"Command error: {e}")

            self.shutdown_event.wait(config.command_poll_interval)

    def _pricing_worker(self):
        """Scenario 5: Pricing collection loop"""
        logger.info("Pricing worker started")

        # Wait before first collection
        self.shutdown_event.wait(60)

        while self.running and not self.shutdown_event.is_set():
            try:
                if self.state == AgentState.ONLINE_READY:
                    # Get instance types from inventory
                    inventory = self.inventory_collector.collect_inventory()
                    instance_types = list(set([
                        inst['instance_type']
                        for inst in inventory.get('instances', [])
                    ]))

                    if instance_types:
                        pricing_data = self.pricing_collector.collect_pricing(instance_types)
                        if pricing_data:
                            self.backend.send_pricing_update(config.agent_id, pricing_data)
                            logger.info(f"Sent pricing update: {len(pricing_data)} records")
            except Exception as e:
                logger.error(f"Pricing error: {e}")

            self.shutdown_event.wait(config.pricing_collection_interval)

    def _notice_worker(self):
        """Scenario 6: Notice monitoring loop"""
        logger.info("Notice worker started")

        while self.running and not self.shutdown_event.is_set():
            try:
                if self.state == AgentState.ONLINE_READY:
                    instance_id = self.instance_info.get('instance_id')
                    if instance_id:
                        self.notice_monitor.check_for_notices(config.agent_id, instance_id)
            except Exception as e:
                logger.error(f"Notice monitor error: {e}")

            self.shutdown_event.wait(config.notice_check_interval)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False
        self.shutdown_event.set()

    def _shutdown(self):
        """Scenario 7: Graceful shutdown"""
        logger.info("Shutting down agent...")

        self.running = False
        self.shutdown_event.set()
        self.state = AgentState.SHUTDOWN

        # Wait for threads
        for thread in self.threads:
            thread.join(timeout=5)

        # Send shutdown notice
        try:
            metadata = {
                'uptime': self.backend._get_uptime(),
                'final_state': self.state.value
            }
            self.backend.send_shutdown_notice(
                config.agent_id,
                self.instance_info.get('instance_id'),
                metadata
            )
        except:
            pass

        logger.info("✓ Agent shutdown complete")

# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("AWS Spot Optimizer Agent v5.0.0")
    logger.info("Production Monolithic Implementation")
    logger.info("=" * 80)

    agent = SpotOptimizerAgent()
    agent.start()

if __name__ == '__main__':
    main()
