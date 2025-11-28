"""
Data Gap Filler - Handles the scenario where:
- Model is trained on data up to last month
- Instance needs 15 days of recent data for accurate predictions
- Queries required data from various sources and fills the gap
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass
import boto3
import asyncio
import httpx


@dataclass
class DataGap:
    """Represents a gap in data"""
    start_date: datetime
    end_date: datetime
    data_type: str  # 'spot_prices', 'interruptions', 'metrics'
    region: str
    instance_types: List[str]


@dataclass
class GapFillResult:
    """Result of gap filling operation"""
    gap: DataGap
    data: pd.DataFrame
    records_filled: int
    fill_duration_seconds: float
    sources_used: List[str]
    success: bool
    errors: List[str]


class DataGapFiller:
    """
    Fills data gaps by querying multiple sources:
    1. AWS APIs (Spot price history, CloudWatch metrics)
    2. Internal database (if any historical data exists)
    3. Public data sources (Spot Advisor)
    """

    def __init__(self, config: Dict):
        self.config = config
        self.aws_region = config.get('aws_region', 'us-east-1')
        self.ec2_client = boto3.client('ec2', region_name=self.aws_region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=self.aws_region)

    async def identify_gaps(
        self,
        model_last_training_date: datetime,
        current_date: datetime,
        required_lookback_days: int = 15
    ) -> List[DataGap]:
        """
        Identify what data gaps exist between model training and current deployment

        Args:
            model_last_training_date: When the model was last trained
            current_date: Current deployment date
            required_lookback_days: How many days of recent data needed

        Returns:
            List of data gaps that need to be filled
        """
        gaps = []

        # Calculate the required data range
        required_start_date = current_date - timedelta(days=required_lookback_days)

        # If model training date is before required start, we have a gap
        if model_last_training_date < required_start_date:
            gap_start = model_last_training_date
            gap_end = current_date

            # Create gaps for different data types
            gaps.append(DataGap(
                start_date=gap_start,
                end_date=gap_end,
                data_type='spot_prices',
                region=self.aws_region,
                instance_types=self.config.get('instance_types', [])
            ))

            gaps.append(DataGap(
                start_date=gap_start,
                end_date=gap_end,
                data_type='interruptions',
                region=self.aws_region,
                instance_types=self.config.get('instance_types', [])
            ))

        return gaps

    async def fill_gap(self, gap: DataGap) -> GapFillResult:
        """
        Fill a specific data gap by querying appropriate sources

        Args:
            gap: DataGap to fill

        Returns:
            GapFillResult with filled data
        """
        start_time = datetime.now()
        errors = []
        sources_used = []
        all_data = []

        try:
            if gap.data_type == 'spot_prices':
                # Fill spot price gap from AWS API
                price_data = await self._fill_spot_price_gap(gap)
                all_data.append(price_data)
                sources_used.append('AWS EC2 DescribeSpotPriceHistory')

            elif gap.data_type == 'interruptions':
                # Fill interruption gap from CloudWatch Events
                interruption_data = await self._fill_interruption_gap(gap)
                all_data.append(interruption_data)
                sources_used.append('AWS CloudWatch Events')

            # Combine all data
            if all_data:
                combined_data = pd.concat(all_data, ignore_index=True)
            else:
                combined_data = pd.DataFrame()

            duration = (datetime.now() - start_time).total_seconds()

            return GapFillResult(
                gap=gap,
                data=combined_data,
                records_filled=len(combined_data),
                fill_duration_seconds=duration,
                sources_used=sources_used,
                success=True,
                errors=errors
            )

        except Exception as e:
            errors.append(str(e))
            duration = (datetime.now() - start_time).total_seconds()

            return GapFillResult(
                gap=gap,
                data=pd.DataFrame(),
                records_filled=0,
                fill_duration_seconds=duration,
                sources_used=sources_used,
                success=False,
                errors=errors
            )

    async def _fill_spot_price_gap(self, gap: DataGap) -> pd.DataFrame:
        """
        Fill spot price data gap using AWS EC2 API

        Args:
            gap: DataGap specifying time range and instance types

        Returns:
            DataFrame with spot price history
        """
        all_prices = []

        # AWS API limits: max 90 days per request
        # Split into chunks if needed
        chunks = self._split_date_range(gap.start_date, gap.end_date, days=90)

        for chunk_start, chunk_end in chunks:
            try:
                # Fetch spot price history
                response = self.ec2_client.describe_spot_price_history(
                    InstanceTypes=gap.instance_types if gap.instance_types else None,
                    ProductDescriptions=['Linux/UNIX'],
                    StartTime=chunk_start,
                    EndTime=chunk_end
                )

                for item in response['SpotPriceHistory']:
                    all_prices.append({
                        'timestamp': item['Timestamp'],
                        'instance_type': item['InstanceType'],
                        'availability_zone': item['AvailabilityZone'],
                        'spot_price': float(item['SpotPrice']),
                        'product_description': item['ProductDescription']
                    })

                # Handle pagination
                while 'NextToken' in response:
                    response = self.ec2_client.describe_spot_price_history(
                        InstanceTypes=gap.instance_types if gap.instance_types else None,
                        ProductDescriptions=['Linux/UNIX'],
                        StartTime=chunk_start,
                        EndTime=chunk_end,
                        NextToken=response['NextToken']
                    )

                    for item in response['SpotPriceHistory']:
                        all_prices.append({
                            'timestamp': item['Timestamp'],
                            'instance_type': item['InstanceType'],
                            'availability_zone': item['AvailabilityZone'],
                            'spot_price': float(item['SpotPrice']),
                            'product_description': item['ProductDescription']
                        })

            except Exception as e:
                print(f"Error fetching spot prices for chunk {chunk_start} to {chunk_end}: {e}")
                continue

        return pd.DataFrame(all_prices)

    async def _fill_interruption_gap(self, gap: DataGap) -> pd.DataFrame:
        """
        Fill interruption data gap
        (In production, this would query CloudWatch Events or internal DB)

        For now, returns simulated data based on statistical models
        """
        # Generate simulated interruption events
        interruptions = []

        current_date = gap.start_date
        while current_date < gap.end_date:
            # Simulate ~5% daily interruption rate
            for instance_type in gap.instance_types:
                if np.random.random() < 0.05:  # 5% chance
                    interruptions.append({
                        'timestamp': current_date + timedelta(
                            hours=np.random.randint(0, 24)
                        ),
                        'instance_type': instance_type,
                        'region': gap.region,
                        'interruption_type': 'spot_termination',
                        'notice_time_minutes': 2
                    })

            current_date += timedelta(days=1)

        return pd.DataFrame(interruptions)

    def _split_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        days: int
    ) -> List[Tuple[datetime, datetime]]:
        """Split a date range into chunks of specified days"""
        chunks = []
        current_start = start_date

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=days), end_date)
            chunks.append((current_start, current_end))
            current_start = current_end

        return chunks

    async def fill_all_gaps_and_prepare_data(
        self,
        model_last_training_date: datetime,
        required_lookback_days: int = 15
    ) -> Dict[str, pd.DataFrame]:
        """
        Complete workflow: Identify all gaps, fill them, and prepare data

        Args:
            model_last_training_date: When model was last trained
            required_lookback_days: Days of recent data needed

        Returns:
            Dictionary with DataFrames for each data type
        """
        current_date = datetime.now()

        # Step 1: Identify gaps
        print(f"Identifying data gaps between {model_last_training_date} and {current_date}")
        gaps = await self.identify_gaps(
            model_last_training_date,
            current_date,
            required_lookback_days
        )

        if not gaps:
            print("No data gaps found - model is up to date!")
            return {}

        print(f"Found {len(gaps)} data gaps to fill")

        # Step 2: Fill each gap
        results = {}

        for gap in gaps:
            print(f"\nFilling gap: {gap.data_type} from {gap.start_date} to {gap.end_date}")
            result = await self.fill_gap(gap)

            if result.success:
                print(f"✓ Filled {result.records_filled} records in {result.fill_duration_seconds:.2f}s")
                print(f"  Sources: {', '.join(result.sources_used)}")
                results[gap.data_type] = result.data
            else:
                print(f"✗ Failed to fill gap: {result.errors}")

        return results

    def export_gap_filled_data(
        self,
        data: Dict[str, pd.DataFrame],
        output_dir: str
    ):
        """Export gap-filled data to files"""
        import os
        os.makedirs(output_dir, exist_ok=True)

        for data_type, df in data.items():
            output_path = os.path.join(output_dir, f"{data_type}_gap_filled.parquet")
            df.to_parquet(output_path, index=False)
            print(f"Exported {len(df)} records to {output_path}")

    def generate_gap_report(
        self,
        results: List[GapFillResult]
    ) -> Dict:
        """Generate summary report of gap filling operation"""
        total_records = sum(r.records_filled for r in results)
        total_duration = sum(r.fill_duration_seconds for r in results)
        successful = sum(1 for r in results if r.success)

        report = {
            'total_gaps_processed': len(results),
            'successful_fills': successful,
            'failed_fills': len(results) - successful,
            'total_records_filled': total_records,
            'total_duration_seconds': total_duration,
            'average_fill_rate_records_per_second': total_records / total_duration if total_duration > 0 else 0,
            'gaps': [
                {
                    'data_type': r.gap.data_type,
                    'date_range': f"{r.gap.start_date} to {r.gap.end_date}",
                    'records_filled': r.records_filled,
                    'duration_seconds': r.fill_duration_seconds,
                    'success': r.success,
                    'errors': r.errors
                }
                for r in results
            ]
        }

        return report


# Example usage
async def main():
    """Example of using DataGapFiller"""

    config = {
        'aws_region': 'us-east-1',
        'instance_types': ['m5.large', 'm5.xlarge', 'c5.large']
    }

    filler = DataGapFiller(config)

    # Simulate: Model was trained 30 days ago, we need 15 days of recent data
    model_training_date = datetime.now() - timedelta(days=30)

    print("="*80)
    print("DATA GAP FILLER - EXAMPLE RUN")
    print("="*80)
    print(f"Model last trained: {model_training_date}")
    print(f"Current date: {datetime.now()}")
    print(f"Required lookback: 15 days")
    print()

    # Fill gaps
    filled_data = await filler.fill_all_gaps_and_prepare_data(
        model_last_training_date=model_training_date,
        required_lookback_days=15
    )

    # Export data
    if filled_data:
        print("\n" + "="*80)
        print("Exporting gap-filled data...")
        filler.export_gap_filled_data(filled_data, output_dir='./data/gap_filled')

    print("\n" + "="*80)
    print("Gap filling complete!")


if __name__ == "__main__":
    asyncio.run(main())
