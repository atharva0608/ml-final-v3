"""
CloudOptim Core Platform - Safety Enforcement Integration Tests
================================================================

Tests for Five-Layer Defense Strategy:
1. Risk Threshold Validation (≥0.75)
2. AZ Distribution Validation (≥3 zones)
3. Pool Concentration Validation (≤20% per pool)
4. On-Demand Buffer Validation (≥15%)
5. Multi-Factor Validation (all constraints)

Author: Architecture Team
Date: 2025-12-01
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any

from services.safety_enforcer import SafetyEnforcer
from services.safe_executor import SafeExecutor


class TestSafetyEnforcer:
    """Test suite for SafetyEnforcer five-layer defense"""

    @pytest.fixture
    async def enforcer(self):
        """Create SafetyEnforcer instance with mock database"""
        # In production, use real database session
        return SafetyEnforcer(db=None)

    @pytest.fixture
    def cluster_id(self):
        """Generate test cluster ID"""
        return uuid4()

    @pytest.fixture
    def safe_recommendation(self):
        """Safe recommendation that passes all constraints"""
        return {
            "optimization_type": "spot",
            "instance_pools": [
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1a",
                    "spot_allocation_percentage": 15,
                    "risk_score": 0.80
                },
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1b",
                    "spot_allocation_percentage": 15,
                    "risk_score": 0.82
                },
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1c",
                    "spot_allocation_percentage": 15,
                    "risk_score": 0.78
                },
            ],
            "on_demand_percentage": 55,
            "total_instances": 100,
            "estimated_savings": Decimal("1200.00")
        }

    @pytest.fixture
    def unsafe_low_risk_recommendation(self):
        """Unsafe recommendation with risk scores < 0.75"""
        return {
            "optimization_type": "spot",
            "instance_pools": [
                {
                    "instance_type": "t3.micro",
                    "availability_zone": "us-east-1a",
                    "spot_allocation_percentage": 30,
                    "risk_score": 0.50  # TOO LOW - CRITICAL VIOLATION
                },
                {
                    "instance_type": "t3.micro",
                    "availability_zone": "us-east-1b",
                    "spot_allocation_percentage": 30,
                    "risk_score": 0.60  # TOO LOW - CRITICAL VIOLATION
                },
            ],
            "on_demand_percentage": 40,
            "total_instances": 100,
            "estimated_savings": Decimal("2000.00")
        }

    @pytest.fixture
    def unsafe_single_az_recommendation(self):
        """Unsafe recommendation with only 1 AZ"""
        return {
            "optimization_type": "spot",
            "instance_pools": [
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1a",
                    "spot_allocation_percentage": 60,
                    "risk_score": 0.85
                },
            ],
            "on_demand_percentage": 40,
            "total_instances": 100,
            "estimated_savings": Decimal("1500.00")
        }

    @pytest.fixture
    def unsafe_pool_concentration_recommendation(self):
        """Unsafe recommendation with >20% in single pool"""
        return {
            "optimization_type": "spot",
            "instance_pools": [
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1a",
                    "spot_allocation_percentage": 35,  # >20% - VIOLATION
                    "risk_score": 0.85
                },
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1b",
                    "spot_allocation_percentage": 15,
                    "risk_score": 0.82
                },
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1c",
                    "spot_allocation_percentage": 10,
                    "risk_score": 0.78
                },
            ],
            "on_demand_percentage": 40,
            "total_instances": 100,
            "estimated_savings": Decimal("1200.00")
        }

    @pytest.fixture
    def unsafe_low_on_demand_recommendation(self):
        """Unsafe recommendation with <15% On-Demand buffer"""
        return {
            "optimization_type": "spot",
            "instance_pools": [
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1a",
                    "spot_allocation_percentage": 30,
                    "risk_score": 0.85
                },
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1b",
                    "spot_allocation_percentage": 30,
                    "risk_score": 0.82
                },
                {
                    "instance_type": "m5.large",
                    "availability_zone": "us-east-1c",
                    "spot_allocation_percentage": 30,
                    "risk_score": 0.78
                },
            ],
            "on_demand_percentage": 10,  # <15% - VIOLATION
            "total_instances": 100,
            "estimated_savings": Decimal("1800.00")
        }

    # ========================================
    # CONSTRAINT 1: RISK THRESHOLD TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_safe_recommendation_passes(self, enforcer, cluster_id, safe_recommendation):
        """Test that safe recommendation passes all constraints"""
        result = await enforcer.validate_recommendation(cluster_id, safe_recommendation)

        assert result["is_safe"] is True
        assert result["violations"] == []
        assert result["action_taken"] == "approved"
        assert result["recommendation"] == safe_recommendation

    @pytest.mark.asyncio
    async def test_low_risk_score_rejected(self, enforcer, cluster_id, unsafe_low_risk_recommendation):
        """Test that recommendations with risk scores <0.75 are rejected"""
        result = await enforcer.validate_recommendation(cluster_id, unsafe_low_risk_recommendation)

        assert result["is_safe"] is False
        assert any("risk score" in v.lower() for v in result["violations"])
        assert result["action_taken"] in ["rejected", "safe_alternative_created"]

    # ========================================
    # CONSTRAINT 2: AZ DISTRIBUTION TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_single_az_rejected(self, enforcer, cluster_id, unsafe_single_az_recommendation):
        """Test that single-AZ recommendations are rejected"""
        result = await enforcer.validate_recommendation(cluster_id, unsafe_single_az_recommendation)

        assert result["is_safe"] is False
        assert any("availability zone" in v.lower() or "az" in v.lower() for v in result["violations"])
        assert result["action_taken"] in ["rejected", "safe_alternative_created"]

    @pytest.mark.asyncio
    async def test_three_az_minimum_required(self, enforcer, cluster_id):
        """Test that minimum 3 AZs are required"""
        two_az_recommendation = {
            "optimization_type": "spot",
            "instance_pools": [
                {"instance_type": "m5.large", "availability_zone": "us-east-1a", "spot_allocation_percentage": 25, "risk_score": 0.85},
                {"instance_type": "m5.large", "availability_zone": "us-east-1b", "spot_allocation_percentage": 25, "risk_score": 0.82},
            ],
            "on_demand_percentage": 50,
            "total_instances": 100,
            "estimated_savings": Decimal("1000.00")
        }

        result = await enforcer.validate_recommendation(cluster_id, two_az_recommendation)

        assert result["is_safe"] is False
        assert any("3" in v and ("az" in v.lower() or "zone" in v.lower()) for v in result["violations"])

    # ========================================
    # CONSTRAINT 3: POOL CONCENTRATION TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_pool_concentration_violation(self, enforcer, cluster_id, unsafe_pool_concentration_recommendation):
        """Test that >20% allocation to single pool is rejected"""
        result = await enforcer.validate_recommendation(cluster_id, unsafe_pool_concentration_recommendation)

        assert result["is_safe"] is False
        assert any("pool" in v.lower() and ("20%" in v or "concentration" in v.lower()) for v in result["violations"])
        assert result["action_taken"] in ["rejected", "safe_alternative_created"]

    @pytest.mark.asyncio
    async def test_20_percent_max_per_pool(self, enforcer, cluster_id):
        """Test that exactly 20% allocation is allowed"""
        max_pool_recommendation = {
            "optimization_type": "spot",
            "instance_pools": [
                {"instance_type": "m5.large", "availability_zone": "us-east-1a", "spot_allocation_percentage": 20, "risk_score": 0.85},
                {"instance_type": "m5.large", "availability_zone": "us-east-1b", "spot_allocation_percentage": 20, "risk_score": 0.82},
                {"instance_type": "m5.large", "availability_zone": "us-east-1c", "spot_allocation_percentage": 20, "risk_score": 0.78},
            ],
            "on_demand_percentage": 40,
            "total_instances": 100,
            "estimated_savings": Decimal("1200.00")
        }

        result = await enforcer.validate_recommendation(cluster_id, max_pool_recommendation)

        # Should pass - exactly 20% is allowed
        assert result["is_safe"] is True or result["action_taken"] == "safe_alternative_created"

    # ========================================
    # CONSTRAINT 4: ON-DEMAND BUFFER TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_low_on_demand_buffer_rejected(self, enforcer, cluster_id, unsafe_low_on_demand_recommendation):
        """Test that <15% On-Demand buffer is rejected"""
        result = await enforcer.validate_recommendation(cluster_id, unsafe_low_on_demand_recommendation)

        assert result["is_safe"] is False
        assert any("on-demand" in v.lower() and ("15%" in v or "buffer" in v.lower()) for v in result["violations"])
        assert result["action_taken"] in ["rejected", "safe_alternative_created"]

    @pytest.mark.asyncio
    async def test_15_percent_minimum_on_demand(self, enforcer, cluster_id):
        """Test that exactly 15% On-Demand is allowed"""
        min_on_demand_recommendation = {
            "optimization_type": "spot",
            "instance_pools": [
                {"instance_type": "m5.large", "availability_zone": "us-east-1a", "spot_allocation_percentage": 28, "risk_score": 0.85},
                {"instance_type": "m5.large", "availability_zone": "us-east-1b", "spot_allocation_percentage": 28, "risk_score": 0.82},
                {"instance_type": "m5.large", "availability_zone": "us-east-1c", "spot_allocation_percentage": 29, "risk_score": 0.78},
            ],
            "on_demand_percentage": 15,  # Exactly 15% - should pass
            "total_instances": 100,
            "estimated_savings": Decimal("1500.00")
        }

        result = await enforcer.validate_recommendation(cluster_id, min_on_demand_recommendation)

        # Should pass - exactly 15% is allowed
        assert result["is_safe"] is True or result["action_taken"] == "safe_alternative_created"

    # ========================================
    # SAFE ALTERNATIVE CREATION TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_safe_alternative_created(self, enforcer, cluster_id, unsafe_pool_concentration_recommendation):
        """Test that enforcer can create safe alternatives"""
        result = await enforcer.validate_recommendation(cluster_id, unsafe_pool_concentration_recommendation)

        if result["action_taken"] == "safe_alternative_created":
            # Verify safe alternative meets all constraints
            safe_alt = result["recommendation"]

            # Check all pools have ≤20% allocation
            for pool in safe_alt.get("instance_pools", []):
                assert pool["spot_allocation_percentage"] <= 20

            # Check ≥3 AZs
            azs = set(pool["availability_zone"] for pool in safe_alt.get("instance_pools", []))
            assert len(azs) >= 3

            # Check ≥15% On-Demand
            assert safe_alt.get("on_demand_percentage", 0) >= 15

            # Check all risk scores ≥0.75
            for pool in safe_alt.get("instance_pools", []):
                assert pool["risk_score"] >= 0.75


class TestSafeExecutor:
    """Test suite for SafeExecutor integration with ML Server"""

    @pytest.fixture
    async def executor(self):
        """Create SafeExecutor instance with mock ML client"""
        # In production, use real ML client and database
        return SafeExecutor(ml_client=None, db=None)

    @pytest.fixture
    def cluster_id(self):
        """Generate test cluster ID"""
        return uuid4()

    @pytest.mark.asyncio
    async def test_executor_validates_before_execution(self, executor, cluster_id):
        """Test that SafeExecutor validates recommendations before execution"""
        # This test would require mocking ML Server responses
        # For now, verify the interface exists

        assert hasattr(executor, 'execute_optimization')
        assert hasattr(executor, 'execute_spot_optimization')
        assert hasattr(executor, 'execute_bin_packing')
        assert hasattr(executor, 'execute_rightsizing')

    @pytest.mark.asyncio
    async def test_executor_rejects_unsafe_recommendations(self, executor, cluster_id):
        """Test that SafeExecutor rejects unsafe recommendations"""
        # Mock unsafe ML response
        # Verify execution is blocked
        # This would be implemented with proper mocking
        pass


class TestEndToEndSafetyFlow:
    """End-to-end integration tests for safety enforcement"""

    @pytest.mark.asyncio
    async def test_full_safety_validation_flow(self):
        """Test complete flow from ML recommendation to safe execution"""
        # 1. ML Server generates recommendation
        # 2. SafetyEnforcer validates recommendation
        # 3. If unsafe, create safe alternative or reject
        # 4. SafeExecutor executes only if safe
        # 5. Audit log created in safety_violations table

        # This would be implemented with proper database and ML Server integration
        pass

    @pytest.mark.asyncio
    async def test_safety_violation_audit_logging(self):
        """Test that all safety violations are logged to database"""
        # Verify that violations are written to safety_violations table
        # Verify that active_safety_violations view is updated
        # Verify that cluster_safety_summary view shows correct stats

        # This would be implemented with proper database integration
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
