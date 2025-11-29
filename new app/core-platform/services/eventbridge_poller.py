"""
EventBridge/SQS Poller Service

Polls customer SQS queues for Spot interruption warnings (2-minute notice)
Runs as background task in Core Platform
"""

import boto3
import json
import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class EventBridgePoller:
    """
    SQS Poller for Spot Interruption Warnings
   
    Polls customer SQS queues every 5 seconds for EC2 Spot Instance Interruption Warnings
    """

    def __init__(self, poll_interval_seconds: int = 5, max_messages: int = 10):
        """
        Initialize SQS poller

        Args:
            poll_interval_seconds: Polling interval (default: 5 seconds)
            max_messages: Maximum messages per poll (default: 10)
        """
        self.poll_interval = poll_interval_seconds
        self.max_messages = max_messages
        self.sqs_clients: Dict[str, Any] = {}  # region -> boto3 SQS client
        self.running = False
        logger.info(f"EventBridge poller initialized (interval: {poll_interval_seconds}s)")

    async def start(self, queue_configs: List[Dict[str, Any]]):
        """
        Start polling SQS queues

        Args:
            queue_configs: List of queue configurations
                [{"queue_url": "...", "region": "...", "cluster_id": "..."}]
        """
        self.running = True
        logger.info(f"Starting SQS poller for {len(queue_configs)} queues")
       
        # Create SQS clients for each region
        for config in queue_configs:
            region = config.get("region", "us-east-1")
            if region not in self.sqs_clients:
                self.sqs_clients[region] = boto3.client("sqs", region_name=region)
       
        # Start polling loop
        while self.running:
            await self._poll_all_queues(queue_configs)
            await asyncio.sleep(self.poll_interval)

    async def _poll_all_queues(self, queue_configs: List[Dict[str, Any]]):
        """Poll all configured SQS queues"""
        for config in queue_configs:
            try:
                messages = await self._poll_queue(config)
                if messages:
                    logger.info(f"Received {len(messages)} Spot warning(s) from queue {config['queue_url']}")
                    for message in messages:
                        await self._process_spot_warning(message, config)
            except Exception as e:
                logger.error(f"Error polling queue {config['queue_url']}: {e}")

    async def _poll_queue(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Poll a single SQS queue

        Args:
            config: Queue configuration

        Returns:
            List of messages
        """
        queue_url = config["queue_url"]
        region = config.get("region", "us-east-1")
        sqs = self.sqs_clients[region]
       
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=self.max_messages,
            WaitTimeSeconds=20,  # Long polling
            AttributeNames=["All"],
            MessageAttributeNames=["All"]
        )
       
        messages = response.get("Messages", [])
       
        # Delete messages from queue after receiving
        for message in messages:
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message["ReceiptHandle"]
            )
       
        return messages

    async def _process_spot_warning(self, message: Dict[str, Any], config: Dict[str, Any]):
        """
        Process Spot interruption warning

        Args:
            message: SQS message
            config: Queue configuration
        """
        try:
            # Parse EventBridge event from SQS message
            event_body = json.loads(message["Body"])
           
            instance_id = event_body["detail"]["instance-id"]
            event_time = event_body["time"]
            cluster_id = config["cluster_id"]
           
            logger.warning(f"⚠️  Spot Interruption Warning: {instance_id} in cluster {cluster_id}")
            logger.info(f"Event time: {event_time}")
           
            # TODO: Call spot_handler to drain node and launch replacement
            # from services.spot_handler import SpotHandler
            # await spot_handler.handle_interruption(cluster_id, instance_id, event_time)
           
        except Exception as e:
            logger.error(f"Failed to process Spot warning: {e}")

    def stop(self):
        """Stop polling"""
        self.running = False
        logger.info("Stopped SQS poller")
