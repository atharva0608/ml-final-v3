"""
Spot Instance Interruption Predictor
ML Model to predict Spot instance interruption probability
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder
import joblib
import os


class SpotInterruptionPredictor:
    """
    Predicts likelihood of Spot instance interruption using XGBoost

    Features:
    - Instance type/family
    - Region and AZ
    - Time of day, day of week
    - Historical spot price
    - Time since launch
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model: Optional[xgb.XGBClassifier] = None
        self.label_encoders: Dict[str, LabelEncoder] = {}
        self.feature_names: List[str] = [
            'hour_of_day',
            'day_of_week',
            'spot_price',
            'time_since_launch_hours',
            'instance_family_encoded',
            'region_encoded',
            'az_encoded'
        ]

        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
        else:
            self._initialize_model()

    def _initialize_model(self):
        """Initialize a new XGBoost model"""
        self.model = xgb.XGBClassifier(
            max_depth=6,
            learning_rate=0.1,
            n_estimators=100,
            objective='binary:logistic',
            random_state=42,
            eval_metric='auc'
        )

        # Initialize label encoders
        self.label_encoders = {
            'instance_family': LabelEncoder(),
            'region': LabelEncoder(),
            'az': LabelEncoder()
        }

    def prepare_features(
        self,
        instance_type: str,
        region: str,
        availability_zone: str,
        spot_price: float,
        launch_time: datetime
    ) -> np.ndarray:
        """
        Prepare features for prediction

        Args:
            instance_type: e.g., 'm5.large'
            region: e.g., 'us-east-1'
            availability_zone: e.g., 'us-east-1a'
            spot_price: Current spot price
            launch_time: When the instance was launched

        Returns:
            Feature array ready for prediction
        """
        now = datetime.now()

        # Extract instance family
        instance_family = instance_type.split('.')[0]

        # Calculate time-based features
        hour_of_day = now.hour
        day_of_week = now.weekday()
        time_since_launch = (now - launch_time).total_seconds() / 3600  # hours

        # Encode categorical features
        if hasattr(self.label_encoders['instance_family'], 'classes_'):
            family_encoded = self._safe_encode(
                self.label_encoders['instance_family'], instance_family
            )
        else:
            # Fallback for untrained encoder
            family_encoded = hash(instance_family) % 100

        if hasattr(self.label_encoders['region'], 'classes_'):
            region_encoded = self._safe_encode(
                self.label_encoders['region'], region
            )
        else:
            region_encoded = hash(region) % 20

        if hasattr(self.label_encoders['az'], 'classes_'):
            az_encoded = self._safe_encode(
                self.label_encoders['az'], availability_zone
            )
        else:
            az_encoded = hash(availability_zone) % 50

        features = np.array([[
            hour_of_day,
            day_of_week,
            spot_price,
            time_since_launch,
            family_encoded,
            region_encoded,
            az_encoded
        ]])

        return features

    def _safe_encode(self, encoder: LabelEncoder, value: str) -> int:
        """Safely encode a value, handling unseen categories"""
        try:
            return encoder.transform([value])[0]
        except ValueError:
            # Unseen category - return default
            return -1

    def predict_interruption_probability(
        self,
        instance_type: str,
        region: str,
        availability_zone: str,
        spot_price: float,
        launch_time: datetime
    ) -> float:
        """
        Predict probability of interruption in the next hour

        Returns:
            float: Probability between 0.0 and 1.0
        """
        if self.model is None:
            raise ValueError("Model not initialized or loaded")

        features = self.prepare_features(
            instance_type, region, availability_zone,
            spot_price, launch_time
        )

        # Get probability for positive class (interrupted)
        probabilities = self.model.predict_proba(features)
        interruption_probability = probabilities[0][1]

        return interruption_probability

    def train(
        self,
        training_data: pd.DataFrame,
        validation_split: float = 0.2
    ) -> Dict[str, float]:
        """
        Train the model on historical data

        Args:
            training_data: DataFrame with columns:
                - instance_type
                - region
                - availability_zone
                - spot_price
                - launch_time
                - interrupted (target: 0 or 1)
            validation_split: Fraction of data for validation

        Returns:
            Dictionary with training metrics
        """
        # Extract instance family
        training_data['instance_family'] = training_data['instance_type'].str.split('.').str[0]

        # Time-based features
        training_data['hour_of_day'] = pd.to_datetime(
            training_data['observation_time']
        ).dt.hour
        training_data['day_of_week'] = pd.to_datetime(
            training_data['observation_time']
        ).dt.dayofweek

        training_data['time_since_launch_hours'] = (
            pd.to_datetime(training_data['observation_time']) -
            pd.to_datetime(training_data['launch_time'])
        ).dt.total_seconds() / 3600

        # Fit label encoders
        self.label_encoders['instance_family'].fit(training_data['instance_family'])
        self.label_encoders['region'].fit(training_data['region'])
        self.label_encoders['az'].fit(training_data['availability_zone'])

        # Encode categorical features
        training_data['instance_family_encoded'] = self.label_encoders['instance_family'].transform(
            training_data['instance_family']
        )
        training_data['region_encoded'] = self.label_encoders['region'].transform(
            training_data['region']
        )
        training_data['az_encoded'] = self.label_encoders['az'].transform(
            training_data['availability_zone']
        )

        # Prepare feature matrix
        X = training_data[self.feature_names].values
        y = training_data['interrupted'].values

        # Train/validation split
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        # Train model
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )

        # Calculate metrics
        train_accuracy = self.model.score(X_train, y_train)
        val_accuracy = self.model.score(X_val, y_val)

        return {
            'train_accuracy': train_accuracy,
            'validation_accuracy': val_accuracy,
            'num_samples': len(training_data),
            'num_features': len(self.feature_names)
        }

    def save_model(self, model_path: str):
        """Save model and encoders to disk"""
        model_dir = os.path.dirname(model_path)
        os.makedirs(model_dir, exist_ok=True)

        # Save XGBoost model
        self.model.save_model(model_path)

        # Save label encoders
        encoders_path = model_path.replace('.model', '_encoders.pkl')
        joblib.dump(self.label_encoders, encoders_path)

        print(f"Model saved to {model_path}")
        print(f"Encoders saved to {encoders_path}")

    def load_model(self, model_path: str):
        """Load model and encoders from disk"""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Load XGBoost model
        self.model = xgb.XGBClassifier()
        self.model.load_model(model_path)

        # Load label encoders
        encoders_path = model_path.replace('.model', '_encoders.pkl')
        if os.path.exists(encoders_path):
            self.label_encoders = joblib.load(encoders_path)

        print(f"Model loaded from {model_path}")

    def generate_synthetic_training_data(
        self,
        num_samples: int = 10000
    ) -> pd.DataFrame:
        """
        Generate synthetic training data for bootstrapping
        (In production, this would be replaced with real historical data)
        """
        np.random.seed(42)

        instance_types = [
            'm5.large', 'm5.xlarge', 'm5.2xlarge',
            'm5a.large', 'm5a.xlarge',
            'c5.large', 'c5.xlarge', 'c5.2xlarge',
            'r5.large', 'r5.xlarge'
        ]

        regions = ['us-east-1', 'us-west-2', 'eu-west-1']
        azs = {
            'us-east-1': ['us-east-1a', 'us-east-1b', 'us-east-1c'],
            'us-west-2': ['us-west-2a', 'us-west-2b', 'us-west-2c'],
            'eu-west-1': ['eu-west-1a', 'eu-west-1b', 'eu-west-1c']
        }

        data = []
        base_time = datetime.now() - timedelta(days=90)

        for i in range(num_samples):
            instance_type = np.random.choice(instance_types)
            region = np.random.choice(regions)
            az = np.random.choice(azs[region])

            launch_time = base_time + timedelta(
                days=np.random.randint(0, 90),
                hours=np.random.randint(0, 24)
            )
            observation_time = launch_time + timedelta(
                hours=np.random.uniform(0.5, 48)
            )

            spot_price = np.random.uniform(0.02, 0.15)

            # Simulate interruption based on heuristics
            hour = observation_time.hour
            time_since_launch = (observation_time - launch_time).total_seconds() / 3600

            # Higher interruption probability during peak hours
            base_interruption_prob = 0.05
            if 9 <= hour <= 11:
                base_interruption_prob += 0.10

            # Recently launched instances less likely to interrupt
            if time_since_launch < 1:
                base_interruption_prob *= 0.5

            # Higher prices = less likely to interrupt
            if spot_price > 0.10:
                base_interruption_prob *= 0.7

            interrupted = 1 if np.random.random() < base_interruption_prob else 0

            data.append({
                'instance_type': instance_type,
                'region': region,
                'availability_zone': az,
                'spot_price': spot_price,
                'launch_time': launch_time,
                'observation_time': observation_time,
                'interrupted': interrupted
            })

        return pd.DataFrame(data)


# Example usage
if __name__ == "__main__":
    # Initialize predictor
    predictor = SpotInterruptionPredictor()

    # Generate synthetic training data
    print("Generating synthetic training data...")
    training_data = predictor.generate_synthetic_training_data(num_samples=10000)

    # Train model
    print("Training model...")
    metrics = predictor.train(training_data)
    print(f"Training Metrics: {metrics}")

    # Make a prediction
    test_launch_time = datetime.now() - timedelta(hours=2)
    probability = predictor.predict_interruption_probability(
        instance_type='m5.large',
        region='us-east-1',
        availability_zone='us-east-1a',
        spot_price=0.045,
        launch_time=test_launch_time
    )

    print(f"\nInterruption probability: {probability:.4f}")

    # Save model
    predictor.save_model('./models/saved/spot_predictor.model')
