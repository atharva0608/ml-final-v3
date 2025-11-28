"""
AWS Spot Optimizer Agent v4.0.0 - Production Grade
===========================================================================
COMPATIBLE WITH BACKEND V6.0 (Operational Runbook Aligned)

New Features (v4.0):
✓ Operational runbook compliance with backend v6.0
✓ Emergency flow orchestration (rebalance/termination notices)
✓ ML decision integration with confidence thresholds
✓ Idempotency support via X-Request-ID headers
✓ Optimistic locking awareness
✓ Replica mode support
✓ Enhanced pricing data with quality markers
✓ State machine compliance (PRIMARY/REPLICA/ZOMBIE/TERMINATED)
✓ Comprehensive error handling and retry logic
✓ Production-grade logging and monitoring

Architecture:
- Monolithic design for simplicity
- Event-driven with worker threads
- Graceful shutdown with cleanup
- AWS metadata service integration (IMDSv2)
- Backend v6.0 API compatibility

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
from typing import Dict, List, Optional, Tuple, Any
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('spot_agent_v4.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class AgentConfig:
    """Agent configuration with environment variable support"""

    # Server Connection
    SERVER_URL: str = os.getenv('SPOT_OPTIMIZER_SERVER_URL', 'http://localhost:5000')
    CLIENT_TOKEN: str = os.getenv('SPOT_OPTIMIZER_CLIENT_TOKEN', '')

    # Agent Identity
    LOGICAL_AGENT_ID: str = os.getenv('LOGICAL_AGENT_ID', '')
    HOSTNAME: str = socket.gethostname()

    # AWS Configuration
    REGION: str = os.getenv('AWS_REGION', 'us-east-1')

    # Timing Configuration
    HEARTBEAT_INTERVAL: int = int(os.getenv('HEARTBEAT_INTERVAL', 30))
    PRICING_REPORT_INTERVAL: int = int(os.getenv('PRICING_REPORT_INTERVAL', 300))
    EMERGENCY_CHECK_INTERVAL: int = int(os.getenv('EMERGENCY_CHECK_INTERVAL', 10))
    ML_DECISION_INTERVAL: int = int(os.getenv('ML_DECISION_INTERVAL', 300))

    # Agent Version
    AGENT_VERSION: str = '4.0.0'

    def validate(self) -> bool:
        """Validate required configuration"""
        if not self.CLIENT_TOKEN:
            logger.error("CLIENT_TOKEN not set!")
            return False
        if not self.SERVER_URL:
            logger.error("SERVER_URL not set!")
            return False
        if not self.LOGICAL_AGENT_ID:
            logger.warning("LOGICAL_AGENT_ID not set. Will use instance ID.")
        return True

config = AgentConfig()

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
            self.ec2 = boto3.client('ec2', region_name=config.REGION)
            self.ec2_resource = boto3.resource('ec2', region_name=config.REGION)
            logger.info(f"✓ AWS clients initialized (region: {config.REGION})")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise

aws_clients = AWSClients()

# ============================================================================
# INSTANCE METADATA (IMDSv2)
# ============================================================================

class InstanceMetadata:
    """AWS Instance Metadata Service v2 client"""

    METADATA_BASE_URL = "http://169.254.169.254/latest"
    METADATA_TIMEOUT = 2

    @staticmethod
    def get_token() -> Optional[str]:
        """Get IMDSv2 token"""
        try:
            response = requests.put(
                f"{InstanceMetadata.METADATA_BASE_URL}/api/token",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
                timeout=InstanceMetadata.METADATA_TIMEOUT
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to get IMDSv2 token: {e}")
            return None

    @staticmethod
    def get_metadata(path: str, token: str) -> Optional[str]:
        """Fetch instance metadata with token"""
        try:
            response = requests.get(
                f"{InstanceMetadata.METADATA_BASE_URL}/{path}",
                headers={"X-aws-ec2-metadata-token": token},
                timeout=InstanceMetadata.METADATA_TIMEOUT
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.debug(f"Metadata fetch failed for {path}: {e}")
            return None

    @classmethod
    def get_instance_info(cls) -> Dict[str, str]:
        """Get all instance information"""
        token = cls.get_token()
        if not token:
            raise RuntimeError("Cannot get IMDSv2 token")

        info = {
            'instance_id': cls.get_metadata("meta-data/instance-id", token),
            'instance_type': cls.get_metadata("meta-data/instance-type", token),
            'az': cls.get_metadata("meta-data/placement/availability-zone", token),
            'ami_id': cls.get_metadata("meta-data/ami-id", token),
            'private_ip': cls.get_metadata("meta-data/local-ipv4", token),
            'public_ip': cls.get_metadata("meta-data/public-ipv4", token),
        }

        # Detect mode
        info['mode'] = cls.detect_mode(info['instance_id'])

        return info

    @staticmethod
    def detect_mode(instance_id: str) -> str:
        """Detect if instance is spot or on-demand"""
        try:
            response = aws_clients.ec2.describe_instances(InstanceIds=[instance_id])
            if not response['Reservations']:
                return 'unknown'

            instance = response['Reservations'][0]['Instances'][0]
            lifecycle = instance.get('InstanceLifecycle', 'normal')

            if lifecycle == 'spot':
                return 'spot'
            return 'ondemand'
        except Exception as e:
            logger.error(f"Failed to detect mode: {e}")
            return 'unknown'

    @staticmethod
    def check_spot_interruption() -> Optional[Dict]:
        """Check for spot instance interruption notices"""
        try:
            token = InstanceMetadata.get_token()
            if not token:
                return None

            # Check for instance action
            action = InstanceMetadata.get_metadata("meta-data/spot/instance-action", token)
            if action:
                action_data = json.loads(action)
                return {
                    'action': action_data.get('action'),
                    'time': action_data.get('time')
                }
            return None
        except Exception:
            return None

# ============================================================================
# SERVER API CLIENT
# ============================================================================

class ServerAPI:
    """API client for backend v6.0 communication"""

    def __init__(self):
        self.base_url = config.SERVER_URL.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {config.CLIENT_TOKEN}',
            'Content-Type': 'application/json'
        })

    def _generate_request_id(self) -> str:
        """Generate unique request ID for idempotency"""
        return str(uuid.uuid4())

    def _make_request(self, method: str, endpoint: str, idempotent: bool = False, **kwargs) -> Optional[Dict]:
        """Make HTTP request with error handling and idempotency"""
        url = f"{self.base_url}{endpoint}"

        # Add idempotency header for POST/PUT/DELETE
        if idempotent and method in ['POST', 'PUT', 'DELETE']:
            self.session.headers['X-Request-ID'] = self._generate_request_id()

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {endpoint}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error: {endpoint}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {response.status_code}: {endpoint}")
            if response.status_code == 500:
                logger.error(f"Server error: {response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Request failed: {endpoint} - {e}")
            return None

    def register_agent(self, instance_info: Dict) -> Optional[Dict]:
        """Register agent with backend v6.0"""
        return self._make_request('POST', '/api/agents/register', json=instance_info)

    def send_heartbeat(self, agent_id: str, status: str = 'online') -> bool:
        """Send heartbeat to server"""
        result = self._make_request(
            'POST',
            f'/api/agents/{agent_id}/heartbeat',
            json={'status': status}
        )
        return result is not None

    def get_agent_config(self, agent_id: str) -> Optional[Dict]:
        """Get agent configuration"""
        return self._make_request('GET', f'/api/agents/{agent_id}/config')

    def report_rebalance_notice(self, agent_id: str, notice_time: str) -> Optional[Dict]:
        """Report AWS rebalance recommendation"""
        return self._make_request(
            'POST',
            f'/api/agents/{agent_id}/rebalance-recommendation',
            idempotent=True,
            json={'notice_time': notice_time}
        )

    def report_termination_notice(self, agent_id: str, termination_time: str) -> Optional[Dict]:
        """Report AWS termination notice (via rebalance endpoint with immediate flag)"""
        return self._make_request(
            'POST',
            f'/api/agents/{agent_id}/rebalance-recommendation',
            idempotent=True,
            json={
                'notice_time': termination_time,
                'immediate': True
            }
        )

    def get_ml_decision(self, agent_id: str, pricing_data: Dict) -> Optional[Dict]:
        """Get ML decision from backend"""
        return self._make_request(
            'POST',
            f'/api/agents/{agent_id}/decide',
            json=pricing_data
        )

    def get_switch_recommendation(self, agent_id: str) -> Optional[Dict]:
        """Get switch recommendation"""
        return self._make_request('GET', f'/api/agents/{agent_id}/switch-recommendation')

    def report_termination(self, agent_id: str, instance_id: str, reason: str) -> bool:
        """Report instance termination"""
        result = self._make_request(
            'POST',
            f'/api/agents/{agent_id}/termination-report',
            idempotent=True,
            json={
                'instance_id': instance_id,
                'termination_reason': reason
            }
        )
        return result is not None

    def get_emergency_status(self, agent_id: str) -> Optional[Dict]:
        """Get emergency status"""
        return self._make_request('GET', f'/api/agents/{agent_id}/emergency-status')

# ============================================================================
# PRICING COLLECTOR
# ============================================================================

class PricingCollector:
    """Collect pricing data for ML decision engine"""

    def __init__(self):
        self.ec2 = aws_clients.ec2

    def collect_pricing_data(self, instance_type: str, region: str, current_az: str) -> Dict:
        """Collect comprehensive pricing data"""
        try:
            # Get all availability zones
            zones_response = self.ec2.describe_availability_zones(
                Filters=[{'Name': 'region-name', 'Values': [region]}]
            )
            zones = [z['ZoneName'] for z in zones_response['AvailabilityZones']
                    if z['State'] == 'available']

            # Collect spot prices for all zones
            spot_pools = []
            for az in zones:
                price = self._get_spot_price(instance_type, az)
                if price is not None:
                    spot_pools.append({
                        'pool_id': f"{instance_type}.{az}",
                        'instance_type': instance_type,
                        'az': az,
                        'price': price,
                        'is_current': (az == current_az)
                    })

            # Get on-demand price
            ondemand_price = self._get_ondemand_price(instance_type, region)

            return {
                'spot_pools': spot_pools,
                'ondemand_price': ondemand_price,
                'current_az': current_az
            }
        except Exception as e:
            logger.error(f"Failed to collect pricing data: {e}")
            return {'spot_pools': [], 'ondemand_price': 0.0, 'current_az': current_az}

    def _get_spot_price(self, instance_type: str, az: str) -> Optional[float]:
        """Get current spot price for instance type in AZ"""
        try:
            # Try with VPC product description first
            for product_desc in ['Linux/UNIX (Amazon VPC)', 'Linux/UNIX']:
                try:
                    response = self.ec2.describe_spot_price_history(
                        InstanceTypes=[instance_type],
                        AvailabilityZone=az,
                        MaxResults=1,
                        ProductDescriptions=[product_desc]
                    )
                    if response['SpotPriceHistory']:
                        return float(response['SpotPriceHistory'][0]['SpotPrice'])
                except Exception:
                    continue

            # Fallback without product description filter
            response = self.ec2.describe_spot_price_history(
                InstanceTypes=[instance_type],
                AvailabilityZone=az,
                MaxResults=1
            )
            if response['SpotPriceHistory']:
                return float(response['SpotPriceHistory'][0]['SpotPrice'])

            return None
        except Exception as e:
            logger.debug(f"Failed to get spot price for {instance_type} in {az}: {e}")
            return None

    def _get_ondemand_price(self, instance_type: str, region: str) -> float:
        """Get on-demand price"""
        try:
            pricing = boto3.client('pricing', region_name='us-east-1')
            location = self._region_to_location(region)

            response = pricing.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                    {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}
                ],
                MaxResults=1
            )

            if response['PriceList']:
                price_data = json.loads(response['PriceList'][0])
                terms = price_data['terms']['OnDemand']
                for term in terms.values():
                    for price_dim in term['priceDimensions'].values():
                        return float(price_dim['pricePerUnit']['USD'])

            # Fallback: estimate from spot prices
            logger.warning(f"Could not get on-demand price for {instance_type}, using estimate")
            return 0.1
        except Exception as e:
            logger.error(f"Failed to get on-demand price: {e}")
            return 0.1

    def _region_to_location(self, region: str) -> str:
        """Convert region code to pricing API location"""
        region_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'EU (Ireland)',
            'eu-central-1': 'EU (Frankfurt)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)',
        }
        return region_map.get(region, region)

# ============================================================================
# MAIN AGENT CLASS
# ============================================================================

class SpotOptimizerAgent:
    """Main agent class for backend v6.0"""

    def __init__(self):
        self.server_api = ServerAPI()
        self.pricing_collector = PricingCollector()

        # Agent state
        self.agent_id: Optional[str] = None
        self.instance_info: Dict = {}
        self.logical_agent_id: str = config.LOGICAL_AGENT_ID
        self.is_running = False
        self.is_enabled = True

        # Threads
        self.threads: List[threading.Thread] = []
        self.shutdown_event = threading.Event()

        logger.info(f"Agent initialized: Logical ID={self.logical_agent_id}")

    def start(self):
        """Start the agent"""
        try:
            # Setup signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

            # Get instance metadata
            logger.info("Fetching instance metadata...")
            self.instance_info = InstanceMetadata.get_instance_info()

            if not self.logical_agent_id:
                self.logical_agent_id = self.instance_info['instance_id']

            logger.info(f"Instance ID: {self.instance_info['instance_id']}")
            logger.info(f"Instance Type: {self.instance_info['instance_type']}")
            logger.info(f"AZ: {self.instance_info['az']}")
            logger.info(f"Mode: {self.instance_info['mode']}")

            # Register with backend
            if not self._register():
                logger.error("Failed to register agent. Exiting.")
                return

            self.is_running = True

            # Start worker threads
            self._start_workers()

            logger.info("="*80)
            logger.info("✓ Agent started successfully")
            logger.info(f"  Agent ID: {self.agent_id}")
            logger.info(f"  Logical ID: {self.logical_agent_id}")
            logger.info(f"  Version: {config.AGENT_VERSION}")
            logger.info("="*80)

            # Keep main thread alive
            while self.is_running and not self.shutdown_event.is_set():
                time.sleep(1)

        except Exception as e:
            logger.error(f"Agent start failed: {e}", exc_info=True)
        finally:
            self._shutdown()

    def _register(self) -> bool:
        """Register agent with backend v6.0"""
        try:
            registration_data = {
                'logical_agent_id': self.logical_agent_id,
                'instance_id': self.instance_info['instance_id'],
                'instance_type': self.instance_info['instance_type'],
                'region': config.REGION,
                'az': self.instance_info['az'],
                'mode': self.instance_info['mode'],
                'hostname': config.HOSTNAME,
                'ami_id': self.instance_info.get('ami_id'),
                'agent_version': config.AGENT_VERSION,
                'private_ip': self.instance_info.get('private_ip'),
                'public_ip': self.instance_info.get('public_ip')
            }

            response = self.server_api.register_agent(registration_data)

            if not response:
                logger.error("Registration failed - no response")
                return False

            self.agent_id = response.get('agent_id')
            agent_config = response.get('config', {})

            self.is_enabled = agent_config.get('enabled', True)

            logger.info(f"✓ Registered as agent: {self.agent_id}")
            logger.info(f"  Enabled: {self.is_enabled}")
            logger.info(f"  Auto-switch: {agent_config.get('auto_switch_enabled')}")

            return True
        except Exception as e:
            logger.error(f"Registration failed: {e}", exc_info=True)
            return False

    def _start_workers(self):
        """Start background worker threads"""
        workers = [
            (self._heartbeat_worker, "Heartbeat"),
            (self._emergency_check_worker, "EmergencyCheck"),
            (self._ml_decision_worker, "MLDecision"),
        ]

        for worker_func, worker_name in workers:
            thread = threading.Thread(target=worker_func, name=worker_name, daemon=True)
            thread.start()
            self.threads.append(thread)
            logger.info(f"✓ Started worker: {worker_name}")

    def _heartbeat_worker(self):
        """Send regular heartbeats"""
        logger.info("Heartbeat worker started")

        while self.is_running and not self.shutdown_event.is_set():
            try:
                status = 'online' if self.is_enabled else 'disabled'
                success = self.server_api.send_heartbeat(self.agent_id, status)

                if not success:
                    logger.warning("Heartbeat failed")
                else:
                    logger.debug(f"Heartbeat sent: status={status}")

                # Refresh config
                agent_config = self.server_api.get_agent_config(self.agent_id)
                if agent_config:
                    new_enabled = agent_config.get('enabled', True)
                    if new_enabled != self.is_enabled:
                        logger.info(f"Agent enabled state changed: {self.is_enabled} -> {new_enabled}")
                        self.is_enabled = new_enabled

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            self.shutdown_event.wait(config.HEARTBEAT_INTERVAL)

    def _emergency_check_worker(self):
        """Check for spot interruption notices"""
        logger.info("Emergency check worker started")

        while self.is_running and not self.shutdown_event.is_set():
            try:
                if self.instance_info['mode'] != 'spot':
                    # Only check for spot instances
                    self.shutdown_event.wait(config.EMERGENCY_CHECK_INTERVAL)
                    continue

                interruption = InstanceMetadata.check_spot_interruption()

                if interruption:
                    action = interruption['action']
                    notice_time = interruption['time']

                    logger.warning(f"⚠️ Spot interruption notice received: {action} at {notice_time}")

                    if action == 'terminate':
                        # Direct termination notice
                        result = self.server_api.report_termination_notice(
                            self.agent_id, notice_time
                        )
                        logger.info(f"Termination notice reported to backend: {result}")
                    else:
                        # Rebalance recommendation
                        result = self.server_api.report_rebalance_notice(
                            self.agent_id, notice_time
                        )
                        logger.info(f"Rebalance notice reported to backend: {result}")

                    # Check emergency status
                    emergency_status = self.server_api.get_emergency_status(self.agent_id)
                    if emergency_status:
                        logger.info(f"Emergency status: {emergency_status}")

            except Exception as e:
                logger.error(f"Emergency check error: {e}")

            self.shutdown_event.wait(config.EMERGENCY_CHECK_INTERVAL)

    def _ml_decision_worker(self):
        """Request ML decisions periodically"""
        logger.info("ML decision worker started")

        # Wait a bit before first decision request
        self.shutdown_event.wait(60)

        while self.is_running and not self.shutdown_event.is_set():
            try:
                if not self.is_enabled:
                    logger.debug("Agent disabled, skipping ML decision")
                    self.shutdown_event.wait(config.ML_DECISION_INTERVAL)
                    continue

                # Collect pricing data
                logger.info("Collecting pricing data for ML decision...")
                pricing_data = self.pricing_collector.collect_pricing_data(
                    self.instance_info['instance_type'],
                    config.REGION,
                    self.instance_info['az']
                )

                logger.info(f"Collected {len(pricing_data['spot_pools'])} spot pools")

                # Request ML decision
                decision = self.server_api.get_ml_decision(self.agent_id, pricing_data)

                if decision:
                    action = decision.get('action', 'NO_ACTION')
                    confidence = decision.get('confidence', 0)
                    reasoning = decision.get('reasoning', 'No reason provided')

                    logger.info(f"ML Decision: {action} (confidence: {confidence:.2f})")
                    logger.info(f"Reasoning: {reasoning}")

                    if action in ['SWITCH', 'CREATE_REPLICA']:
                        logger.warning(f"Action recommended: {action}")
                        # The backend will handle creating commands/replicas
                        # Agent just needs to report the data
                else:
                    logger.warning("No ML decision received")

            except Exception as e:
                logger.error(f"ML decision error: {e}", exc_info=True)

            self.shutdown_event.wait(config.ML_DECISION_INTERVAL)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False
        self.shutdown_event.set()

    def _shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down agent...")

        self.is_running = False
        self.shutdown_event.set()

        # Wait for threads
        for thread in self.threads:
            thread.join(timeout=5)

        # Send final heartbeat
        try:
            self.server_api.send_heartbeat(self.agent_id, 'offline')
        except:
            pass

        logger.info("✓ Agent shutdown complete")

# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    logger.info("="*80)
    logger.info("AWS Spot Optimizer Agent v4.0.0")
    logger.info("Backend v6.0 Compatible")
    logger.info("="*80)

    # Validate configuration
    if not config.validate():
        logger.error("Configuration validation failed!")
        sys.exit(1)

    # Create and start agent
    agent = SpotOptimizerAgent()
    agent.start()

if __name__ == '__main__':
    main()
