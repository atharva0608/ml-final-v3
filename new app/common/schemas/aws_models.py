"""
AWS Models for CloudOptim Agentless Architecture

Schemas for AWS EventBridge events, EC2 operations, and pricing data.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SpotEvent(BaseModel):
    """
    AWS EC2 Spot Instance Interruption Event

    Flow: AWS EventBridge → SQS → Core Platform poller
    Provides 2-minute warning before Spot interruption.
    """
    # Event identification
    event_id: str = Field(..., description="Unique event ID from EventBridge")
    cluster_id: str = Field(..., description="Cluster ID (derived from instance tags)")
    instance_id: str = Field(..., description="EC2 instance ID being interrupted")

    # Event details
    event_type: str = Field(..., description="Event type (interruption_warning, terminated)")
    event_time: datetime = Field(..., description="Time when AWS generated this event")
    received_at: datetime = Field(default_factory=datetime.utcnow, description="Time when Core Platform received event")

    # Instance details
    instance_type: str = Field(..., description="EC2 instance type")
    availability_zone: str = Field(..., description="Availability zone")
    region: str = Field(..., description="AWS region")

    # Interruption details
    interruption_time: Optional[datetime] = Field(None, description="Scheduled interruption time (2 min from event_time)")
    action: str = Field("terminate", description="Action AWS will take (terminate, stop, hibernate)")

    # Raw event
    detail: Dict[str, Any] = Field(..., description="Raw AWS EventBridge event detail")

    # Response tracking
    action_taken: Optional[str] = Field(None, description="Action taken by Core Platform (drained, replaced)")
    replacement_instance_id: Optional[str] = Field(None, description="New instance ID if replaced")
    drain_duration_seconds: Optional[int] = Field(None, description="Time taken to drain node (seconds)")
    processed_at: Optional[datetime] = Field(None, description="Time when processing completed")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class EC2InstanceLaunchRequest(BaseModel):
    """
    Request to launch EC2 instance via AWS API

    Flow: Core Platform → AWS EC2 API
    Used for Spot optimization and replacements.
    """
    # Instance configuration
    instance_type: str = Field(..., description="EC2 instance type (e.g., m5.large)")
    availability_zone: str = Field(..., description="Availability zone")
    region: str = Field(..., description="AWS region")

    # Market type
    instance_market: str = Field(..., description="Instance market (spot, on-demand)")

    # Spot configuration (if market = spot)
    max_spot_price: Optional[float] = Field(None, description="Maximum Spot price (USD/hour)")
    spot_interruption_behavior: str = Field("terminate", description="Interruption behavior (terminate, stop, hibernate)")

    # Network configuration
    subnet_id: str = Field(..., description="VPC subnet ID")
    security_group_ids: List[str] = Field(..., description="Security group IDs")

    # IAM
    iam_instance_profile: Optional[str] = Field(None, description="IAM instance profile ARN")

    # User data
    user_data: Optional[str] = Field(None, description="Base64-encoded user data script")

    # Tags
    tags: Dict[str, str] = Field(..., description="Instance tags")

    # AMI
    image_id: str = Field(..., description="AMI ID")

    # Storage
    root_volume_size_gb: int = Field(100, description="Root EBS volume size in GB")
    root_volume_type: str = Field("gp3", description="Root EBS volume type")

    # Metadata
    cluster_id: str = Field(..., description="Cluster ID (for tagging)")
    purpose: str = Field(..., description="Purpose (replacement, scaling, optimization)")


class EC2InstanceTerminateRequest(BaseModel):
    """
    Request to terminate EC2 instance via AWS API

    Flow: Core Platform → AWS EC2 API
    Used for optimization and cleanup.
    """
    # Instance identification
    instance_id: str = Field(..., description="EC2 instance ID to terminate")
    region: str = Field(..., description="AWS region")

    # Termination details
    reason: str = Field(..., description="Reason (optimization, interruption, manual, cleanup)")

    # Safety checks
    force: bool = Field(False, description="Force termination even if protected")
    skip_drain: bool = Field(False, description="Skip Kubernetes node drain")

    # Metadata
    cluster_id: str = Field(..., description="Cluster ID")
    triggered_by: str = Field(..., description="What triggered this termination")


class SpotPriceQuery(BaseModel):
    """
    Request to query AWS Spot price history

    Flow: ML Server → AWS EC2 API
    Used for gap filling and price analysis.
    """
    # Instance types
    instance_types: List[str] = Field(..., description="Instance types to query")

    # Regions
    regions: List[str] = Field(..., description="AWS regions to query")

    # Time range
    start_time: datetime = Field(..., description="Start time for price history")
    end_time: datetime = Field(..., description="End time for price history")

    # Filters
    product_descriptions: List[str] = Field(
        default_factory=lambda: ["Linux/UNIX"],
        description="Product descriptions (OS types)"
    )

    # Options
    max_results: int = Field(10000, description="Maximum results per API call")


class SpotPriceData(BaseModel):
    """
    AWS Spot price data point

    Stored in ML Server database for model inference.
    """
    # Identification
    instance_type: str = Field(..., description="EC2 instance type")
    availability_zone: str = Field(..., description="Availability zone")
    region: str = Field(..., description="AWS region")

    # Pricing
    spot_price: float = Field(..., description="Spot price (USD/hour)")
    timestamp: datetime = Field(..., description="Price timestamp")

    # Product details
    product_description: str = Field("Linux/UNIX", description="Product description (OS)")

    # Metadata
    collected_at: datetime = Field(default_factory=datetime.utcnow, description="When we collected this data")


class OnDemandPriceData(BaseModel):
    """
    AWS On-Demand price data

    Stored in ML Server database for baseline cost calculations.
    """
    # Identification
    instance_type: str = Field(..., description="EC2 instance type")
    region: str = Field(..., description="AWS region")

    # Pricing
    on_demand_price: float = Field(..., description="On-Demand price (USD/hour)")

    # Product details
    operating_system: str = Field("Linux", description="Operating system")
    tenancy: str = Field("Shared", description="Tenancy (Shared, Dedicated, Host)")
    pre_installed_sw: str = Field("NA", description="Pre-installed software")

    # Metadata
    effective_date: datetime = Field(..., description="When this price became effective")
    collected_at: datetime = Field(default_factory=datetime.utcnow, description="When we collected this data")


class SpotAdvisorData(BaseModel):
    """
    AWS Spot Advisor public data

    Source: https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json
    Cached in ML Server Redis for risk scoring.
    """
    # Identification
    instance_type: str = Field(..., description="EC2 instance type")
    region: str = Field(..., description="AWS region (e.g., us-east-1)")

    # Interruption rate
    interruption_rate: str = Field(..., description="Interruption rate category (<5%, 5-10%, 10-15%, 15-20%, >20%)")

    # Numeric risk score (derived)
    risk_score: float = Field(..., description="Risk score (0.0 to 1.0, derived from interruption_rate)")

    # Savings percentage
    savings_percentage: int = Field(..., description="Savings vs On-Demand (0-100)")

    # Metadata
    last_updated: datetime = Field(..., description="When AWS last updated Spot Advisor data")
    cached_at: datetime = Field(default_factory=datetime.utcnow, description="When we cached this data")


class EBSVolumeData(BaseModel):
    """
    AWS EBS volume data

    Used for Zombie Volume Cleanup feature.
    """
    # Identification
    volume_id: str = Field(..., description="EBS volume ID")
    region: str = Field(..., description="AWS region")

    # Volume details
    volume_type: str = Field(..., description="Volume type (gp3, gp2, io1, etc.)")
    size_gb: int = Field(..., description="Volume size in GB")
    iops: Optional[int] = Field(None, description="Provisioned IOPS")

    # Status
    state: str = Field(..., description="Volume state (available, in-use, deleting)")
    attached_to: Optional[str] = Field(None, description="Instance ID if attached")

    # Cost
    monthly_cost: float = Field(..., description="Estimated monthly cost (USD)")

    # PVC tracking
    pvc_name: Optional[str] = Field(None, description="Kubernetes PVC name from tags")
    pvc_namespace: Optional[str] = Field(None, description="Kubernetes PVC namespace from tags")
    cluster_id: Optional[str] = Field(None, description="Cluster ID from tags")

    # Cleanup tracking
    orphaned: bool = Field(False, description="True if no matching PVC in Kubernetes")
    orphaned_since: Optional[datetime] = Field(None, description="When it became orphaned")
    grace_period_days: int = Field(7, description="Days before auto-deletion")

    # Timestamps
    created_at: datetime = Field(..., description="Volume creation time")
    collected_at: datetime = Field(default_factory=datetime.utcnow, description="When we collected this data")


class EC2InstanceData(BaseModel):
    """
    AWS EC2 instance data

    Used for Ghost Probe Scanner feature (zombie instance detection).
    """
    # Identification
    instance_id: str = Field(..., description="EC2 instance ID")
    region: str = Field(..., description="AWS region")

    # Instance details
    instance_type: str = Field(..., description="EC2 instance type")
    availability_zone: str = Field(..., description="Availability zone")
    instance_state: str = Field(..., description="State (running, stopped, terminated)")

    # Market type
    instance_lifecycle: str = Field("on-demand", description="Lifecycle (spot, on-demand)")

    # Network
    private_ip: Optional[str] = Field(None, description="Private IP address")
    public_ip: Optional[str] = Field(None, description="Public IP address")

    # Tags
    tags: Dict[str, str] = Field(default_factory=dict, description="Instance tags")

    # Kubernetes association
    cluster_id: Optional[str] = Field(None, description="Cluster ID from tags")
    node_name: Optional[str] = Field(None, description="K8s node name from tags")
    in_kubernetes: bool = Field(False, description="True if this instance is a K8s node")

    # Ghost detection
    is_ghost: bool = Field(False, description="True if running but not in Kubernetes")
    ghost_since: Optional[datetime] = Field(None, description="When it became a ghost")
    grace_period_hours: int = Field(24, description="Hours before auto-termination")

    # Cost
    hourly_cost: float = Field(..., description="Hourly cost (USD)")

    # Timestamps
    launch_time: datetime = Field(..., description="Instance launch time")
    collected_at: datetime = Field(default_factory=datetime.utcnow, description="When we collected this data")


class EventBridgeRuleConfig(BaseModel):
    """
    AWS EventBridge rule configuration

    Used for customer onboarding.
    """
    # Rule identification
    rule_name: str = Field(..., description="EventBridge rule name")
    cluster_id: str = Field(..., description="Cluster ID")
    customer_id: str = Field(..., description="Customer ID")

    # Rule details
    event_pattern: Dict[str, Any] = Field(..., description="EventBridge event pattern JSON")
    description: str = Field(..., description="Rule description")

    # Target
    target_arn: str = Field(..., description="SQS queue ARN (target)")
    target_id: str = Field(..., description="Target ID")

    # Status
    state: str = Field("ENABLED", description="Rule state (ENABLED, DISABLED)")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SQSQueueConfig(BaseModel):
    """
    AWS SQS queue configuration

    Used for customer onboarding and EventBridge integration.
    """
    # Queue identification
    queue_name: str = Field(..., description="SQS queue name")
    queue_url: str = Field(..., description="SQS queue URL")
    queue_arn: str = Field(..., description="SQS queue ARN")
    cluster_id: str = Field(..., description="Cluster ID")
    customer_id: str = Field(..., description="Customer ID")

    # Queue configuration
    visibility_timeout: int = Field(60, description="Visibility timeout (seconds)")
    message_retention_period: int = Field(345600, description="Message retention (seconds, 4 days)")
    receive_wait_time: int = Field(20, description="Long polling wait time (seconds)")

    # Polling configuration
    poll_interval: int = Field(5, description="How often Core Platform polls (seconds)")
    max_messages: int = Field(10, description="Max messages per poll")

    # Status
    active: bool = Field(True, description="True if actively polled")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
