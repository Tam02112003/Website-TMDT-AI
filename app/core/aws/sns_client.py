import boto3
from botocore.exceptions import ClientError
import logging

from core.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

class SNSClient:
    """A wrapper for boto3 SNS client."""

    def __init__(self, region_name: str = settings.AWS.REGION):
        """
        Initializes the SNS client.
        :param region_name: The AWS region.
        """
        try:
            self.client = boto3.client(
                "sns",
                region_name=region_name,
                aws_access_key_id=settings.AWS.ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS.SECRET_ACCESS_KEY.get_secret_value(),
            )
        except ClientError as e:
            logger.error(f"Failed to create SNS client: {e}")
            raise

    def publish_message(self, topic_arn: str, message: str, subject: str = "New Message") -> dict | None:
        """
        Publishes a message to an SNS topic.
        :param topic_arn: The ARN of the SNS topic.
        :param message: The message to publish.
        :param subject: The subject of the message.
        :return: The response from SNS or None if an error occurs.
        """
        try:
            response = self.client.publish(
                TopicArn=topic_arn,
                Message=message,
                Subject=subject,
            )
            logger.info(f"Message {response.get('MessageId')} published to topic {topic_arn}.")
            return response
        except ClientError as e:
            logger.error(f"Failed to publish message to SNS topic {topic_arn}: {e}")
            return None

# Singleton instance
sns_client = SNSClient()

