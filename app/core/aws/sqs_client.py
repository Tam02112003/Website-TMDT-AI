
import boto3
from botocore.exceptions import ClientError
import logging
import json

from core.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

class SQSClient:
    """A wrapper for boto3 SQS client."""

    def __init__(self, region_name: str = settings.AWS.REGION):
        """
        Initializes the SQS client.
        :param region_name: The AWS region.
        """
        try:
            self.client = boto3.client(
                "sqs",
                region_name=region_name,
                aws_access_key_id=settings.AWS.ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS.SECRET_ACCESS_KEY.get_secret_value(),
            )
        except ClientError as e:
            logger.error(f"Failed to create SQS client: {e}")
            raise

    def send_message(self, queue_url: str, message_body: dict) -> dict | None:
        """
        Sends a message to an SQS queue.
        :param queue_url: The URL of the SQS queue.
        :param message_body: The message body to send (as a dictionary).
        :return: The response from SQS or None if an error occurs.
        """
        try:
            response = self.client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body)
            )
            logger.info(f"Message {response.get('MessageId')} sent to queue {queue_url}.")
            return response
        except ClientError as e:
            logger.error(f"Failed to send message to SQS queue {queue_url}: {e}")
            return None

    def receive_messages(self, queue_url: str, max_number_of_messages: int = 1, wait_time_seconds: int = 5) -> list[dict] | None:
        """
        Receives messages from an SQS queue.
        :param queue_url: The URL of the SQS queue.
        :param max_number_of_messages: The maximum number of messages to receive.
        :param wait_time_seconds: The duration (in seconds) for which the call waits for a message to arrive in the queue before returning.
        :return: A list of messages or None if an error occurs.
        """
        try:
            response = self.client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_number_of_messages,
                WaitTimeSeconds=wait_time_seconds,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            messages = response.get("Messages", [])
            if messages:
                logger.info(f"Received {len(messages)} message(s) from queue {queue_url}.")
            return messages
        except ClientError as e:
            logger.error(f"Failed to receive messages from SQS queue {queue_url}: {e}")
            return None

    def delete_message(self, queue_url: str, receipt_handle: str) -> bool:
        """
        Deletes a message from an SQS queue.
        :param queue_url: The URL of the SQS queue.
        :param receipt_handle: The receipt handle of the message to delete.
        :return: True if the message was deleted successfully, False otherwise.
        """
        try:
            self.client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
            )
            logger.info(f"Message with receipt handle {receipt_handle} deleted from queue {queue_url}.")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete message from SQS queue {queue_url}: {e}")
            return False

# Singleton instance
sqs_client = SQSClient()
