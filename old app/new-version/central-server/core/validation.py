"""
Validation schemas for API request data using Marshmallow.
Provides input validation for complex request payloads.
"""

from marshmallow import Schema, fields, validates, ValidationError


class AgentRegistrationSchema(Schema):
    """
    Validation schema for agent registration requests.

    Required fields:
    - logical_agent_id: Unique logical ID for agent (persists across reinstalls)
    - instance_id: AWS EC2 instance ID
    - instance_type: EC2 instance type (e.g., t3.medium)
    - region: AWS region (e.g., us-east-1)
    - az: Availability zone (e.g., us-east-1a)
    - mode: Current mode ('spot' or 'ondemand')

    Optional fields:
    - hostname: Instance hostname
    - ami_id: AMI ID used
    - agent_version: Agent software version
    - private_ip: Private IP address
    - public_ip: Public IP address
    """
    logical_agent_id = fields.Str(required=True)
    instance_id = fields.Str(required=True)
    instance_type = fields.Str(required=True)
    region = fields.Str(required=True)
    az = fields.Str(required=True)
    mode = fields.Str(required=True)

    # Optional fields
    hostname = fields.Str(required=False, allow_none=True)
    ami_id = fields.Str(required=False, allow_none=True)
    agent_version = fields.Str(required=False, allow_none=True)
    private_ip = fields.Str(required=False, allow_none=True)
    public_ip = fields.Str(required=False, allow_none=True)

    @validates('mode')
    def validate_mode(self, value):
        """Validate that mode is either 'spot' or 'ondemand'."""
        if value not in ['spot', 'ondemand']:
            raise ValidationError("Mode must be 'spot' or 'ondemand'")


class HeartbeatSchema(Schema):
    """
    Validation schema for agent heartbeat requests.

    Optional fields allow partial updates.
    """
    status = fields.Str(required=False)
    current_mode = fields.Str(required=False)
    current_pool_id = fields.Str(required=False)
    spot_price = fields.Float(required=False)
    ondemand_price = fields.Float(required=False)


class ForceSwitchSchema(Schema):
    """
    Validation schema for manual instance switch requests.

    Required fields:
    - target_pool: Target pool ID to switch to
    - target_type: Type of target ('spot' or 'ondemand')

    Optional fields:
    - auto_terminate: Whether to auto-terminate old instance
    """
    target_pool = fields.Str(required=False, allow_none=True)
    target_type = fields.Str(required=True)
    auto_terminate = fields.Bool(required=False, default=True)

    @validates('target_type')
    def validate_target_type(self, value):
        """Validate target type."""
        if value not in ['spot', 'ondemand']:
            raise ValidationError("target_type must be 'spot' or 'ondemand'")


class SwitchReportSchema(Schema):
    """Validation schema for switch report from agents."""
    old_instance_id = fields.Str(required=True)
    new_instance_id = fields.Str(required=True)
    old_price = fields.Float(required=True)
    new_price = fields.Float(required=True)
    ondemand_price = fields.Float(required=True)
    trigger = fields.Str(required=True)
    downtime_seconds = fields.Int(required=False, default=0)

    @validates('trigger')
    def validate_trigger(self, value):
        """Validate trigger type."""
        if value not in ['manual', 'automatic', 'emergency']:
            raise ValidationError("trigger must be 'manual', 'automatic', or 'emergency'")


class PricingReportSchema(Schema):
    """Validation schema for pricing reports from agents."""
    instance_type = fields.Str(required=True)
    region = fields.Str(required=True)
    pools = fields.List(fields.Dict(), required=True)
    ondemand_price = fields.Float(required=True)
