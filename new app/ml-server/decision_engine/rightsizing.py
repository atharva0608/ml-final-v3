"""
CloudOptim ML Server - Hybrid Rightsizing Engine
=================================================

Purpose: Match instance sizes to actual workload requirements
Author: Architecture Team
Date: 2025-12-01

Hybrid Approach - Day Zero Compatible:

**Phase 1: Deterministic (Month 0-3)**
- Lookup tables map (CPU, Memory) → Instance types
- Compare actual vs requested resources
- Rules: Downsize if <50% usage, upsize if >80% usage
- No ML or historical data needed
- Confidence: 0.75-0.85

**Phase 2: ML Enhanced (Month 3+)**
- Time series forecasting for usage spikes
- Features: historical CPU/memory, day/hour patterns, workload type
- Output: Predicted p95 usage + 20% buffer
- Confidence: 0.85-0.95

**Merge Logic:**
- Month 0-3: Use deterministic only
- Month 3+: Merge deterministic + ML predictions
- Safety Rule: If ML predicts larger, use ML (prevent outages)
- If predictions diverge >30%, flag for manual review

Database Integration:
- Query usage_history table for time series data
- Store recommendations in rightsizing_recommendations table
- Track accuracy for continuous improvement

Example:
    engine = RightsizingEngine(db=db_session)
    result = engine.decide(
        cluster_state={
            "nodes": [...],
            "metrics": {"node1": {"cpu_usage_pct": 25, "memory_usage_pct": 30}}
        },
        requirements={"workload_type": "web"},
        constraints={"min_cpu_cores": 2}
    )
"""

from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import logging
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from .base_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)


class RightsizingEngine(BaseDecisionEngine):
    """
    Hybrid Instance Rightsizing Engine

    Combines deterministic lookup tables (Day Zero) with ML predictions (Month 3+)
    for optimal instance sizing recommendations.
    """

    # ========================================
    # DETERMINISTIC COMPONENT: LOOKUP TABLES
    # ========================================

    # Comprehensive instance type database with pricing tiers
    # Format: (cpu_cores, memory_gb) -> [(instance_type, category, monthly_cost)]
    INSTANCE_LOOKUP = {
        # Micro instances (1-2 CPU)
        (1, 1): [("t3.micro", "burstable", 7.30), ("t3a.micro", "burstable", 6.50)],
        (1, 2): [("t3.small", "burstable", 14.60), ("t3a.small", "burstable", 13.00)],
        (2, 2): [("t3.small", "burstable", 14.60), ("t4g.small", "arm", 12.00)],
        (2, 4): [
            ("t3.medium", "burstable", 29.20),
            ("t3a.medium", "burstable", 26.00),
            ("t4g.medium", "arm", 24.00),
            ("m6i.large", "general", 69.00)
        ],

        # Small instances (2-4 CPU, 4-16 GB)
        (2, 8): [
            ("m6i.large", "general", 69.00),
            ("r6i.large", "memory", 100.80),
            ("m5.large", "general", 69.00)
        ],
        (4, 8): [
            ("m6i.xlarge", "general", 138.00),
            ("c6i.xlarge", "compute", 122.00),
            ("m5.xlarge", "general", 138.00)
        ],
        (4, 16): [
            ("m6i.xlarge", "general", 138.00),
            ("r6i.xlarge", "memory", 201.60),
            ("m5.xlarge", "general", 138.00)
        ],

        # Medium instances (8 CPU, 16-64 GB)
        (8, 16): [
            ("m6i.2xlarge", "general", 276.00),
            ("c6i.2xlarge", "compute", 244.00),
            ("m5.2xlarge", "general", 276.00)
        ],
        (8, 32): [
            ("m6i.2xlarge", "general", 276.00),
            ("r6i.2xlarge", "memory", 403.20),
            ("m5.2xlarge", "general", 276.00)
        ],
        (8, 64): [
            ("r6i.2xlarge", "memory", 403.20),
            ("x2gd.2xlarge", "memory", 600.00)
        ],

        # Large instances (16 CPU, 32-128 GB)
        (16, 32): [
            ("m6i.4xlarge", "general", 552.00),
            ("c6i.4xlarge", "compute", 488.00),
            ("m5.4xlarge", "general", 552.00)
        ],
        (16, 64): [
            ("m6i.4xlarge", "general", 552.00),
            ("r6i.4xlarge", "memory", 806.40),
            ("m5.4xlarge", "general", 552.00)
        ],
        (16, 128): [
            ("r6i.4xlarge", "memory", 806.40),
            ("x2gd.4xlarge", "memory", 1200.00)
        ],

        # XL instances (32 CPU, 64-256 GB)
        (32, 64): [
            ("m6i.8xlarge", "general", 1104.00),
            ("c6i.8xlarge", "compute", 976.00),
            ("m5.8xlarge", "general", 1104.00)
        ],
        (32, 128): [
            ("m6i.8xlarge", "general", 1104.00),
            ("r6i.8xlarge", "memory", 1612.80),
            ("m5.8xlarge", "general", 1104.00)
        ],
        (32, 256): [
            ("r6i.8xlarge", "memory", 1612.80),
            ("x2gd.8xlarge", "memory", 2400.00)
        ],

        # XXL instances (64+ CPU)
        (64, 128): [
            ("m6i.16xlarge", "general", 2208.00),
            ("c6i.16xlarge", "compute", 1952.00)
        ],
        (64, 256): [
            ("m6i.16xlarge", "general", 2208.00),
            ("r6i.16xlarge", "memory", 3225.60)
        ],
        (64, 512): [
            ("r6i.16xlarge", "memory", 3225.60),
            ("x2gd.16xlarge", "memory", 4800.00)
        ],
    }

    # Workload-specific recommendations
    WORKLOAD_PREFERENCES = {
        "web": ["t3", "t3a", "m6i", "m5"],  # Burstable or general purpose
        "database": ["r6i", "r5", "m6i"],    # Memory-optimized
        "ml": ["p3", "g4dn", "c6i"],         # GPU or compute-optimized
        "batch": ["c6i", "c5", "m6i"],       # Compute-optimized
        "cache": ["r6i", "r5", "x2gd"],      # Memory-optimized
    }

    # Usage thresholds for rightsizing decisions
    DOWNSIZE_THRESHOLD = 0.50  # Downsize if usage < 50%
    UPSIZE_THRESHOLD = 0.80    # Upsize if usage > 80%
    SAFETY_BUFFER = 0.20       # 20% buffer for spikes

    # ML maturity thresholds (in days of data)
    ML_MINIMUM_DAYS = 90       # Need 3 months of data for ML
    ML_CONFIDENCE_BOOST = 0.10 # ML adds +0.10 to confidence

    def __init__(self, db: Optional[AsyncSession] = None):
        """Initialize Rightsizing Engine with optional database session"""
        super().__init__()
        self.db = db

    async def decide(
        self,
        cluster_state: Dict[str, Any],
        requirements: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate hybrid rightsizing recommendations

        Flow:
        1. Validate input
        2. Analyze each node using deterministic rules
        3. If ML data available (3+ months), enhance with ML predictions
        4. Merge deterministic + ML recommendations
        5. Calculate savings and build execution plan

        Args:
            cluster_state: Current cluster state with nodes and metrics
            requirements: Workload type, optimization goals
            constraints: Min/max CPU/memory, instance type restrictions

        Returns:
            {
                'recommendations': List[Dict],
                'confidence_score': float,
                'estimated_savings': Decimal,
                'execution_plan': List[Dict],
                'metadata': Dict
            }
        """
        self.validate_input(cluster_state)
        logger.info("Generating hybrid rightsizing recommendations")

        nodes = cluster_state.get("nodes", [])
        metrics = cluster_state.get("metrics", {})
        workload_type = requirements.get("workload_type", "general")

        # Check if we have enough data for ML predictions
        ml_available = await self._check_ml_maturity()
        logger.info(f"ML predictions available: {ml_available}")

        # Analyze each node
        recommendations = []
        for node in nodes:
            node_name = node.get("name", "")
            actual_usage = metrics.get(node_name, {})

            # Step 1: Deterministic analysis
            deterministic_rec = await self._analyze_node_deterministic(
                node, actual_usage, workload_type, constraints
            )

            # Step 2: ML enhancement (if available)
            if ml_available and deterministic_rec:
                ml_rec = await self._analyze_node_ml(
                    node, actual_usage, workload_type
                )

                # Step 3: Merge recommendations
                final_rec = await self._merge_recommendations(
                    deterministic_rec, ml_rec
                )
            else:
                final_rec = deterministic_rec

            if final_rec:
                recommendations.append(final_rec)

        # Calculate total savings
        total_savings = sum(r.get("monthly_savings", 0) for r in recommendations)
        estimated_savings = Decimal(str(total_savings))

        # Build execution plan
        execution_plan = self._build_execution_plan(recommendations)

        # Calculate confidence score
        base_confidence = 0.80
        if ml_available:
            base_confidence += self.ML_CONFIDENCE_BOOST

        confidence_score = min(0.95, base_confidence)

        return self.create_response(
            recommendations=recommendations,
            confidence_score=confidence_score,
            estimated_savings=estimated_savings,
            execution_plan=execution_plan,
            metadata={
                "nodes_analyzed": len(nodes),
                "ml_enhanced": ml_available,
                "recommendations_count": len(recommendations)
            }
        )

    # ========================================
    # DETERMINISTIC ANALYSIS
    # ========================================

    async def _analyze_node_deterministic(
        self,
        node: Dict[str, Any],
        actual_usage: Dict[str, Any],
        workload_type: str,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Deterministic node sizing analysis using lookup tables

        Rules:
        1. If CPU usage < 50% AND memory < 50% → Downsize
        2. If CPU usage > 80% OR memory > 80% → Upsize
        3. Otherwise → Keep current size

        Args:
            node: Node configuration (current_instance_type, cpu_cores, memory_gb)
            actual_usage: Observed metrics (cpu_usage_pct, memory_usage_pct)
            workload_type: web, database, ml, batch, cache
            constraints: Optional min/max constraints

        Returns:
            Recommendation dict or None if no change needed
        """
        current_instance = node.get("instance_type", "")
        current_cpu = node.get("cpu_cores", 0)
        current_memory = node.get("memory_gb", 0)

        # Get actual usage (default to safe values if missing)
        cpu_usage_pct = actual_usage.get("cpu_usage_pct", 75.0) / 100.0
        memory_usage_pct = actual_usage.get("memory_usage_pct", 75.0) / 100.0

        logger.debug(
            f"Analyzing node {node.get('name')}: "
            f"CPU={cpu_usage_pct*100:.1f}%, Memory={memory_usage_pct*100:.1f}%"
        )

        # Determine sizing action
        action = None
        if cpu_usage_pct < self.DOWNSIZE_THRESHOLD and memory_usage_pct < self.DOWNSIZE_THRESHOLD:
            action = "downsize"
            target_cpu = math.ceil(current_cpu * cpu_usage_pct / self.DOWNSIZE_THRESHOLD)
            target_memory = math.ceil(current_memory * memory_usage_pct / self.DOWNSIZE_THRESHOLD)
        elif cpu_usage_pct > self.UPSIZE_THRESHOLD or memory_usage_pct > self.UPSIZE_THRESHOLD:
            action = "upsize"
            target_cpu = math.ceil(current_cpu * (1 + self.SAFETY_BUFFER))
            target_memory = math.ceil(current_memory * (1 + self.SAFETY_BUFFER))
        else:
            # No change needed
            logger.debug(f"Node {node.get('name')} is properly sized")
            return None

        # Apply constraints
        if constraints:
            target_cpu = max(target_cpu, constraints.get("min_cpu_cores", 1))
            target_memory = max(target_memory, constraints.get("min_memory_gb", 1))
            target_cpu = min(target_cpu, constraints.get("max_cpu_cores", 64))
            target_memory = min(target_memory, constraints.get("max_memory_gb", 512))

        # Find recommended instance type
        recommended_instance = self._find_best_instance(
            target_cpu, target_memory, workload_type, constraints
        )

        if not recommended_instance:
            logger.warning(f"No suitable instance found for CPU={target_cpu}, Memory={target_memory}")
            return None

        instance_type, category, monthly_cost = recommended_instance

        # Calculate current cost (estimate)
        current_cost = self._estimate_instance_cost(current_instance)
        monthly_savings = current_cost - monthly_cost if action == "downsize" else 0

        return {
            "node_name": node.get("name", ""),
            "current_instance_type": current_instance,
            "current_cpu": current_cpu,
            "current_memory": current_memory,
            "current_monthly_cost": current_cost,
            "recommended_instance_type": instance_type,
            "recommended_cpu": target_cpu,
            "recommended_memory": target_memory,
            "recommended_monthly_cost": monthly_cost,
            "action": action,
            "reason": f"CPU usage {cpu_usage_pct*100:.1f}%, Memory usage {memory_usage_pct*100:.1f}%",
            "monthly_savings": monthly_savings,
            "category": category,
            "method": "deterministic",
            "confidence": 0.80
        }

    def _find_best_instance(
        self,
        cpu_cores: int,
        memory_gb: int,
        workload_type: str,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Optional[Tuple[str, str, float]]:
        """
        Find best instance type from lookup table

        Strategy:
        1. Find exact match in lookup table
        2. If no match, find next larger size
        3. Filter by workload preferences
        4. Apply constraints
        5. Choose lowest cost option

        Returns:
            (instance_type, category, monthly_cost) or None
        """
        # Try exact match first
        key = (cpu_cores, memory_gb)
        if key in self.INSTANCE_LOOKUP:
            candidates = self.INSTANCE_LOOKUP[key]
        else:
            # Find next larger size
            candidates = []
            for (cpu, mem), instances in self.INSTANCE_LOOKUP.items():
                if cpu >= cpu_cores and mem >= memory_gb:
                    candidates.extend(instances)

            if not candidates:
                return None

        # Filter by workload preferences
        preferred_families = self.WORKLOAD_PREFERENCES.get(workload_type, [])
        if preferred_families:
            preferred_candidates = [
                c for c in candidates
                if any(c[0].startswith(family) for family in preferred_families)
            ]
            if preferred_candidates:
                candidates = preferred_candidates

        # Apply constraints
        if constraints:
            allowed_types = constraints.get("allowed_instance_types", [])
            if allowed_types:
                candidates = [c for c in candidates if c[0] in allowed_types]

            blocked_types = constraints.get("blocked_instance_types", [])
            if blocked_types:
                candidates = [c for c in candidates if c[0] not in blocked_types]

        if not candidates:
            return None

        # Choose lowest cost
        candidates.sort(key=lambda x: x[2])
        return candidates[0]

    def _estimate_instance_cost(self, instance_type: str) -> float:
        """Estimate monthly cost for instance type"""
        # Search lookup table for matching instance
        for instances in self.INSTANCE_LOOKUP.values():
            for itype, category, cost in instances:
                if itype == instance_type:
                    return cost

        # Fallback: estimate based on size suffix
        if "micro" in instance_type:
            return 7.0
        elif "small" in instance_type:
            return 14.0
        elif "medium" in instance_type:
            return 29.0
        elif "large" in instance_type and "xlarge" not in instance_type:
            return 70.0
        elif "xlarge" in instance_type:
            multiplier = 1
            if "2xlarge" in instance_type:
                multiplier = 2
            elif "4xlarge" in instance_type:
                multiplier = 4
            elif "8xlarge" in instance_type:
                multiplier = 8
            elif "16xlarge" in instance_type:
                multiplier = 16
            return 140.0 * multiplier

        return 100.0  # Default estimate

    # ========================================
    # ML ANALYSIS
    # ========================================

    async def _check_ml_maturity(self) -> bool:
        """
        Check if we have enough historical data for ML predictions

        Requirement: 3+ months (90 days) of usage data

        Returns:
            True if ML can be used, False otherwise
        """
        if not self.db:
            return False

        try:
            # Check if usage_history table exists and has sufficient data
            # This is a placeholder - actual implementation depends on schema
            cutoff_date = datetime.utcnow() - timedelta(days=self.ML_MINIMUM_DAYS)

            # Query to check data availability
            # result = await self.db.execute(
            #     select(func.count()).select_from(UsageHistory)
            #     .where(UsageHistory.timestamp >= cutoff_date)
            # )
            # count = result.scalar()

            # For now, return False until usage_history table is created
            return False

        except Exception as e:
            logger.warning(f"Error checking ML maturity: {e}")
            return False

    async def _analyze_node_ml(
        self,
        node: Dict[str, Any],
        actual_usage: Dict[str, Any],
        workload_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        ML-based node sizing analysis using time series forecasting

        Features:
        - Historical CPU/memory usage (p50, p95, p99)
        - Temporal patterns (day_of_week, hour_of_day)
        - Workload type patterns
        - Seasonal patterns (detected from feedback loop)

        Prediction:
        - Forecast p95 usage for next 30 days
        - Add 20% safety buffer
        - Recommend instance size

        Args:
            node: Node configuration
            actual_usage: Current metrics
            workload_type: Workload category

        Returns:
            ML recommendation dict or None
        """
        if not self.db:
            return None

        try:
            node_name = node.get("name", "")

            # Fetch historical usage data
            # historical_data = await self._fetch_usage_history(node_name)
            # if not historical_data:
            #     return None

            # Extract features
            # features = self._extract_ml_features(historical_data, workload_type)

            # Predict future usage (p95 + 20% buffer)
            # predicted_cpu = self._predict_usage(features, metric='cpu')
            # predicted_memory = self._predict_usage(features, metric='memory')

            # For now, return None until ML models are trained
            return None

        except Exception as e:
            logger.warning(f"Error in ML analysis: {e}")
            return None

    async def _merge_recommendations(
        self,
        deterministic_rec: Dict[str, Any],
        ml_rec: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge deterministic and ML recommendations

        Merge Strategy:
        1. If ML predicts larger instance → Use ML (safety first)
        2. If predictions agree → Use ML confidence
        3. If predictions diverge >30% → Flag for manual review
        4. Otherwise → Use deterministic with ML confidence boost

        Args:
            deterministic_rec: Recommendation from lookup tables
            ml_rec: Recommendation from ML model (or None)

        Returns:
            Final merged recommendation
        """
        # If no ML recommendation, return deterministic
        if not ml_rec:
            return deterministic_rec

        det_cpu = deterministic_rec["recommended_cpu"]
        det_memory = deterministic_rec["recommended_memory"]
        ml_cpu = ml_rec["recommended_cpu"]
        ml_memory = ml_rec["recommended_memory"]

        # Safety rule: If ML predicts larger, use ML
        if ml_cpu > det_cpu or ml_memory > det_memory:
            logger.info(
                f"ML predicts larger size (ML: {ml_cpu}c/{ml_memory}GB, "
                f"Det: {det_cpu}c/{det_memory}GB) - Using ML recommendation"
            )
            ml_rec["method"] = "ml_override"
            ml_rec["confidence"] = 0.90
            return ml_rec

        # Check for divergence (>30% difference)
        cpu_divergence = abs(ml_cpu - det_cpu) / det_cpu if det_cpu > 0 else 0
        memory_divergence = abs(ml_memory - det_memory) / det_memory if det_memory > 0 else 0

        if cpu_divergence > 0.30 or memory_divergence > 0.30:
            logger.warning(
                f"Predictions diverge significantly "
                f"(CPU: {cpu_divergence*100:.1f}%, Memory: {memory_divergence*100:.1f}%) "
                f"- Flagging for manual review"
            )
            deterministic_rec["requires_review"] = True
            deterministic_rec["review_reason"] = "ML and deterministic predictions diverge >30%"
            deterministic_rec["ml_alternative"] = ml_rec
            return deterministic_rec

        # Predictions agree - use deterministic with ML confidence boost
        deterministic_rec["method"] = "hybrid"
        deterministic_rec["confidence"] = min(0.95, deterministic_rec["confidence"] + self.ML_CONFIDENCE_BOOST)
        deterministic_rec["ml_validated"] = True

        return deterministic_rec

    # ========================================
    # EXECUTION PLANNING
    # ========================================

    def _build_execution_plan(self, recommendations: List[Dict]) -> List[Dict]:
        """
        Build phased execution plan for rightsizing

        Safety Strategy:
        1. Start with lowest-risk changes (downsizes with high confidence)
        2. Group changes by node pool
        3. Execute in waves (25% per wave, validate between waves)
        4. Rollback plan for each step

        Args:
            recommendations: List of rightsizing recommendations

        Returns:
            List of execution steps with rollback procedures
        """
        if not recommendations:
            return []

        # Sort by risk: downsizes first, then upsizes
        downsizes = [r for r in recommendations if r["action"] == "downsize"]
        upsizes = [r for r in recommendations if r["action"] == "upsize"]

        downsizes.sort(key=lambda r: r["confidence"], reverse=True)
        upsizes.sort(key=lambda r: r["confidence"], reverse=True)

        plan = []
        step_num = 1

        # Phase 1: Pre-flight checks
        plan.append({
            "step": step_num,
            "phase": "pre_flight",
            "action": "validate_cluster_health",
            "description": "Verify cluster health and resource availability",
            "estimated_duration_minutes": 5,
            "rollback_procedure": "None - read-only operation"
        })
        step_num += 1

        plan.append({
            "step": step_num,
            "phase": "pre_flight",
            "action": "backup_cluster_state",
            "description": "Backup current cluster state and node configurations",
            "estimated_duration_minutes": 10,
            "rollback_procedure": "None - backup operation"
        })
        step_num += 1

        # Phase 2: Execute downsizes (safer, saves money immediately)
        if downsizes:
            plan.append({
                "step": step_num,
                "phase": "downsize",
                "action": "execute_downsizes",
                "description": f"Downsize {len(downsizes)} over-provisioned nodes",
                "nodes": [r["node_name"] for r in downsizes],
                "estimated_duration_minutes": len(downsizes) * 15,
                "rollback_procedure": "Restore original instance types from backup"
            })
            step_num += 1

            plan.append({
                "step": step_num,
                "phase": "downsize",
                "action": "validate_downsizes",
                "description": "Monitor workload performance for 15 minutes",
                "estimated_duration_minutes": 15,
                "rollback_procedure": "Automatic rollback if performance degradation detected"
            })
            step_num += 1

        # Phase 3: Execute upsizes (higher risk, need more capacity)
        if upsizes:
            plan.append({
                "step": step_num,
                "phase": "upsize",
                "action": "execute_upsizes",
                "description": f"Upsize {len(upsizes)} under-provisioned nodes",
                "nodes": [r["node_name"] for r in upsizes],
                "estimated_duration_minutes": len(upsizes) * 15,
                "rollback_procedure": "Restore original instance types from backup"
            })
            step_num += 1

            plan.append({
                "step": step_num,
                "phase": "upsize",
                "action": "validate_upsizes",
                "description": "Monitor workload performance for 30 minutes",
                "estimated_duration_minutes": 30,
                "rollback_procedure": "Automatic rollback if performance degradation detected"
            })
            step_num += 1

        # Phase 4: Post-execution validation
        plan.append({
            "step": step_num,
            "phase": "post_execution",
            "action": "validate_final_state",
            "description": "Verify all nodes healthy and workloads stable",
            "estimated_duration_minutes": 15,
            "rollback_procedure": "Full cluster restore from backup if critical issues"
        })
        step_num += 1

        plan.append({
            "step": step_num,
            "phase": "post_execution",
            "action": "update_monitoring",
            "description": "Update monitoring alerts and dashboards",
            "estimated_duration_minutes": 10,
            "rollback_procedure": "Restore previous monitoring configuration"
        })

        return plan
