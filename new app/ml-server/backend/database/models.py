"""
SQLAlchemy ORM Models for ML Server Database

Database Schema:
- ml_models: Uploaded ML models metadata
- decision_engines: Decision engine metadata
- spot_prices: Historical Spot pricing data
- on_demand_prices: On-Demand pricing data
- spot_advisor_data: AWS Spot Advisor interruption rates
- data_gaps: Data gap analysis and fill tracking
- model_refresh_history: Model refresh execution logs
- predictions_log: Prediction history
- decision_execution_log: Decision execution history
"""

from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, DateTime, Date,
    Text, DECIMAL, ARRAY, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class MLModel(Base):
    """ML Models table - stores uploaded model metadata"""
    __tablename__ = "ml_models"

    model_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(255), nullable=False)
    model_version = Column(String(50), nullable=False)
    model_type = Column(String(50), nullable=False)  # spot_predictor, resource_forecaster
    trained_until_date = Column(Date, nullable=False)  # Last date model was trained on
    upload_date = Column(DateTime, nullable=False, server_default=func.now())
    uploaded_by = Column(String(255))
    active = Column(Boolean, nullable=False, default=False)
    model_file_path = Column(Text, nullable=False)
    model_metadata = Column(JSONB)  # Feature names, hyperparameters
    performance_metrics = Column(JSONB)  # Accuracy, precision, recall

    __table_args__ = (
        UniqueConstraint('model_name', 'model_version', name='uq_model_name_version'),
    )


class DecisionEngine(Base):
    """Decision Engines table - stores decision engine metadata"""
    __tablename__ = "decision_engines"

    engine_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engine_name = Column(String(255), nullable=False)
    engine_version = Column(String(50), nullable=False)
    engine_type = Column(String(50), nullable=False)  # spot_optimizer, bin_packing, etc.
    upload_date = Column(DateTime, nullable=False, server_default=func.now())
    active = Column(Boolean, nullable=False, default=False)
    engine_file_path = Column(Text, nullable=False)
    config = Column(JSONB)  # Engine configuration
    input_schema = Column(JSONB)  # Expected input format
    output_schema = Column(JSONB)  # Output format

    __table_args__ = (
        UniqueConstraint('engine_name', 'engine_version', name='uq_engine_name_version'),
    )


class SpotPrice(Base):
    """Spot Prices table - historical Spot pricing data"""
    __tablename__ = "spot_prices"

    price_id = Column(BigInteger, primary_key=True, autoincrement=True)
    instance_type = Column(String(50), nullable=False)
    availability_zone = Column(String(50), nullable=False)
    region = Column(String(50), nullable=False)
    spot_price = Column(DECIMAL(10, 4), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    product_description = Column(String(100))  # Linux/UNIX, Windows
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('instance_type', 'availability_zone', 'timestamp',
                        name='uq_spot_price_instance_az_timestamp'),
        Index('idx_spot_prices_lookup', 'instance_type', 'region', 'timestamp'),
        Index('idx_spot_prices_timestamp', 'timestamp'),
    )


class OnDemandPrice(Base):
    """On-Demand Prices table"""
    __tablename__ = "on_demand_prices"

    price_id = Column(BigInteger, primary_key=True, autoincrement=True)
    instance_type = Column(String(50), nullable=False)
    region = Column(String(50), nullable=False)
    hourly_price = Column(DECIMAL(10, 4), nullable=False)
    operating_system = Column(String(50))  # Linux, Windows
    effective_date = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('instance_type', 'region', 'operating_system', 'effective_date',
                        name='uq_od_price_instance_region_os_date'),
        Index('idx_on_demand_prices_lookup', 'instance_type', 'region'),
    )


class SpotAdvisorData(Base):
    """Spot Advisor Data table - AWS public interruption rates"""
    __tablename__ = "spot_advisor_data"

    advisor_id = Column(BigInteger, primary_key=True, autoincrement=True)
    instance_type = Column(String(50), nullable=False)
    region = Column(String(50), nullable=False)
    interruption_rate = Column(String(50), nullable=False)  # <5%, 5-10%, >20%
    savings_over_od = Column(Integer)  # Percentage savings over On-Demand
    last_updated = Column(DateTime, nullable=False)
    raw_data = Column(JSONB)  # Full AWS Spot Advisor JSON

    __table_args__ = (
        UniqueConstraint('instance_type', 'region', name='uq_spot_advisor_instance_region'),
        Index('idx_spot_advisor_lookup', 'instance_type', 'region'),
    )


class DataGap(Base):
    """Data Gaps table - tracks gap analysis and filling progress"""
    __tablename__ = "data_gaps"

    gap_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey('ml_models.model_id'))
    gap_start_date = Column(Date, nullable=False)
    gap_end_date = Column(Date, nullable=False)
    gap_days = Column(Integer, nullable=False)
    data_type = Column(String(50), nullable=False)  # spot_prices, on_demand_prices
    regions = Column(ARRAY(Text))
    instance_types = Column(ARRAY(Text))
    status = Column(String(50), nullable=False)  # pending, filling, completed, failed
    records_filled = Column(Integer, default=0)
    records_expected = Column(Integer)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)


class ModelRefreshHistory(Base):
    """Model Refresh History table"""
    __tablename__ = "model_refresh_history"

    refresh_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey('ml_models.model_id'))
    refresh_type = Column(String(50), nullable=False)  # manual, scheduled, auto
    data_fetched_from = Column(Date)
    data_fetched_to = Column(Date)
    records_fetched = Column(Integer)
    status = Column(String(50), nullable=False)  # in_progress, completed, failed
    triggered_by = Column(String(255))
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
    error_message = Column(Text)


class PredictionLog(Base):
    """Predictions Log table - for monitoring and analysis"""
    __tablename__ = "predictions_log"

    prediction_id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey('ml_models.model_id'))
    prediction_type = Column(String(50), nullable=False)  # spot_interruption, cost_forecast
    input_data = Column(JSONB, nullable=False)
    prediction_output = Column(JSONB, nullable=False)
    confidence_score = Column(DECIMAL(5, 4))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index('idx_predictions_log_model', 'model_id', 'created_at'),
        Index('idx_predictions_log_timestamp', 'created_at'),
    )


class DecisionExecutionLog(Base):
    """Decision Execution Log table"""
    __tablename__ = "decision_execution_log"

    execution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engine_id = Column(UUID(as_uuid=True), ForeignKey('decision_engines.engine_id'))
    decision_type = Column(String(50), nullable=False)  # spot_optimize, bin_pack, rightsize
    cluster_id = Column(String(255))
    input_state = Column(JSONB, nullable=False)
    recommendations = Column(JSONB, nullable=False)
    confidence_score = Column(DECIMAL(5, 4))
    estimated_savings = Column(DECIMAL(10, 2))
    executed_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index('idx_decision_log_engine', 'engine_id', 'executed_at'),
        Index('idx_decision_log_cluster', 'cluster_id', 'executed_at'),
    )
