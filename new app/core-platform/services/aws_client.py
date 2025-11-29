"""
AWS Client Service

Handles AWS EC2 API operations:
- Launch/terminate instances
- Describe instances
- Query Spot prices
"""

import boto3
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class AWSClient:
    """AWS EC2 API client for instance management"""

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize AWS client

        Args:
            region: AWS region
        """
        self.region = region
        self.ec2 = boto3.client("ec2", region_name=region)
        logger.info(f"AWS client initialized for region {region}")

    def launch_instance(
        self,
        instance_type: str,
        ami_id: str,
        subnet_id: str,
        security_group_ids: List[str],
        user_data: str,
        instance_market_options: Optional[Dict] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Launch EC2 instance (Spot or On-Demand)

        Args:
            instance_type: EC2 instance type (e.g., m5.large)
            ami_id: AMI ID for the instance
            subnet_id: Subnet ID
            security_group_ids: List of security group IDs
            user_data: User data script (cloud-init)
            instance_market_options: Spot market options (None for On-Demand)
            tags: Instance tags

        Returns:
            Instance ID
        """
        launch_params = {
            "ImageId": ami_id,
            "InstanceType": instance_type,
            "MinCount": 1,
            "MaxCount": 1,
            "SubnetId": subnet_id,
            "SecurityGroupIds": security_group_ids,
            "UserData": user_data,
        }
       
        if instance_market_options:
            launch_params["InstanceMarketOptions"] = instance_market_options
       
        if tags:
            launch_params["TagSpecifications"] = [{
                "ResourceType": "instance",
                "Tags": [{"Key": k, "Value": v} for k, v in tags.items()]
            }]
       
        logger.info(f"Launching {instance_type} instance...")
        response = self.ec2.run_instances(**launch_params)
        instance_id = response["Instances"][0]["InstanceId"]
       
        logger.info(f"Launched instance: {instance_id}")
        return instance_id

    def terminate_instance(self, instance_id: str) -> bool:
        """
        Terminate EC2 instance

        Args:
            instance_id: Instance ID to terminate

        Returns:
            True if successful
        """
        logger.info(f"Terminating instance {instance_id}...")
        self.ec2.terminate_instances(InstanceIds=[instance_id])
        logger.info(f"Terminated instance {instance_id}")
        return True

    def describe_instances(self, instance_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Describe EC2 instances

        Args:
            instance_ids: Specific instance IDs (None for all)

        Returns:
            List of instance information
        """
        params = {}
        if instance_ids:
            params["InstanceIds"] = instance_ids
       
        response = self.ec2.describe_instances(**params)
       
        instances = []
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                instances.append({
                    "instance_id": instance["InstanceId"],
                    "instance_type": instance["InstanceType"],
                    "state": instance["State"]["Name"],
                    "availability_zone": instance["Placement"]["AvailabilityZone"],
                    "launch_time": instance["LaunchTime"],
                    "instance_lifecycle": instance.get("InstanceLifecycle", "on-demand"),
                })
       
        return instances
