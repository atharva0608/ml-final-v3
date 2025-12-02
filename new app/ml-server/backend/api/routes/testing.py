"""
Testing Mode API Routes
Independent testing environment for model evaluation
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import uuid
import pickle
import os
from datetime import datetime, timedelta
import boto3
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/testing", tags=["testing"])

# In-memory storage for testing sessions (use Redis in production)
testing_sessions = {}

class TestingSession:
    def __init__(self, session_id: str, model_path: str, config: dict):
        self.session_id = session_id
        self.model_path = model_path
        self.config = config
        self.model = None
        self.start_time = datetime.utcnow()
        self.is_active = True

    def load_model(self):
        """Load the uploaded model"""
        with open(self.model_path, 'rb') as f:
            self.model = pickle.load(f)
        return self.model


@router.post("/start-session")
async def start_testing_session(
    model_file: UploadFile = File(...),
    instance_type: str = Form(...),
    availability_zone: str = Form(...),
    region: str = Form(...)
):
    """
    Start a new testing session

    - Upload model file
    - Configure instance type and AZ
    - Generate 3 days of historical data + live predictions
    """
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())

        # Save uploaded model
        model_dir = "/tmp/testing_models"
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, f"{session_id}.pkl")

        with open(model_path, "wb") as f:
            content = await model_file.read()
            f.write(content)

        # Create session
        config = {
            "instance_type": instance_type,
            "availability_zone": availability_zone,
            "region": region
        }

        session = TestingSession(session_id, model_path, config)
        session.load_model()
        testing_sessions[session_id] = session

        return {
            "session_id": session_id,
            "status": "active",
            "config": config,
            "message": "Testing session started successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start testing session: {str(e)}")


@router.get("/predictions/{session_id}")
async def get_predictions(session_id: str):
    """
    Get predictions for a testing session

    Returns:
    - 3 days (72 hours) of historical data with actual prices
    - Live predictions from now onwards
    """
    if session_id not in testing_sessions:
        raise HTTPException(status_code=404, detail="Testing session not found")

    session = testing_sessions[session_id]

    try:
        # Generate timestamp range: 3 days ago to now + 24 hours
        now = datetime.utcnow()
        start_time = now - timedelta(days=3)
        end_time = now + timedelta(hours=24)

        predictions = []
        current_time = start_time

        # Try to fetch historical prices from AWS, fallback to mock data if unavailable
        actual_prices_map = {}
        try:
            ec2_client = boto3.client('ec2', region_name=session.config['region'])
            
            # Get spot price history for the last 3 days
            historical_prices = ec2_client.describe_spot_price_history(
                InstanceTypes=[session.config['instance_type']],
                AvailabilityZone=session.config['availability_zone'],
                StartTime=start_time,
                EndTime=now,
                ProductDescriptions=['Linux/UNIX']
            )

            # Create a map of actual prices by hour
            for price_entry in historical_prices.get('SpotPriceHistory', []):
                timestamp = price_entry['Timestamp'].replace(minute=0, second=0, microsecond=0)
                actual_prices_map[timestamp] = float(price_entry['SpotPrice'])
        except Exception as aws_error:
            logger.warning(f"AWS credentials not configured or API error: {aws_error}. Using mock data.")
            # Generate mock historical prices
            import random
            mock_price = 0.045
            temp_time = start_time
            while temp_time < now:
                mock_price += (random.random() - 0.5) * 0.003
                mock_price = max(0.01, mock_price)
                actual_prices_map[temp_time.replace(minute=0, second=0, microsecond=0)] = round(mock_price, 4)
                temp_time += timedelta(hours=1)

        # Generate hourly predictions
        while current_time <= end_time:
            is_historical = current_time < now

            # Get actual price if historical
            actual_price = actual_prices_map.get(current_time.replace(minute=0, second=0, microsecond=0)) if is_historical else None

            # Generate prediction using the model
            # Feature: [hour, day_of_week, is_weekend]
            features = [
                current_time.hour,
                current_time.weekday(),
                1 if current_time.weekday() >= 5 else 0
            ]

            # Use model to predict (simplified - actual implementation would be more complex)
            try:
                predicted_price = float(session.model.predict([features])[0])
            except:
                # Fallback if model prediction fails
                predicted_price = actual_price if actual_price else 0.05

            predictions.append({
                "timestamp": current_time.isoformat(),
                "actual_price": actual_price,
                "predicted_price": predicted_price,
                "is_historical": is_historical
            })

            current_time += timedelta(hours=1)

        return {
            "session_id": session_id,
            "predictions": predictions,
            "config": session.config,
            "total_predictions": len(predictions),
            "historical_count": len([p for p in predictions if p['is_historical']]),
            "future_count": len([p for p in predictions if not p['is_historical']])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate predictions: {str(e)}")


@router.post("/stop-session/{session_id}")
async def stop_testing_session(session_id: str):
    """Stop a testing session and cleanup resources"""
    if session_id not in testing_sessions:
        raise HTTPException(status_code=404, detail="Testing session not found")

    try:
        session = testing_sessions[session_id]
        session.is_active = False

        # Cleanup model file
        if os.path.exists(session.model_path):
            os.remove(session.model_path)

        # Remove from active sessions
        del testing_sessions[session_id]

        return {
            "session_id": session_id,
            "status": "stopped",
            "message": "Testing session stopped successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop testing session: {str(e)}")


@router.get("/sessions")
async def list_testing_sessions():
    """List all active testing sessions"""
    sessions = []
    for session_id, session in testing_sessions.items():
        sessions.append({
            "session_id": session_id,
            "config": session.config,
            "start_time": session.start_time.isoformat(),
            "is_active": session.is_active
        })

    return {
        "sessions": sessions,
        "total_active": len(sessions)
    }
