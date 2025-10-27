
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import logging
import re
from starlette.concurrency import run_in_threadpool

from core.settings import settings

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_topic_name_from_arn(arn: str) -> str | None:
    """Extracts the topic name from an SNS Topic ARN."""
    if not arn or not isinstance(arn, str):
        return None
    # A more robust regex to handle different partition (aws, aws-cn, etc.)
    match = re.match(r'arn:aws.*:sns:[^:]+:[^:]+:(.+)', arn)
    if match:
        return match.group(1)
    return None

def _setup_sns_topics_sync():
    """
    Synchronous function to set up SNS topics. Designed to be run in a threadpool.
    """
    logging.info("Starting SNS topic setup...")

    try:
        sns_client = boto3.client(
            "sns",
            region_name=settings.AWS.REGION,
            aws_access_key_id=settings.AWS.ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS.SECRET_ACCESS_KEY.get_secret_value(),
        )
        logging.info(f"Successfully created boto3 SNS client for region: {settings.AWS.REGION}")

    except NoCredentialsError:
        logging.error("AWS credentials not found. Please configure them in your .env.dev file.")
        return
    except ClientError as e:
        logging.error(f"Failed to create AWS SNS client: {e}")
        return

    topic_arn_settings = [
        settings.AWS.SNS_USER_ACTIVITY_TOPIC_ARN,
        settings.AWS.SNS_ORDER_EVENTS_TOPIC_ARN,
        settings.AWS.SNS_AUTH_EVENTS_TOPIC_ARN,
        settings.AWS.SNS_DISCOUNT_EVENTS_TOPIC_ARN,
        settings.AWS.SNS_NEWS_EVENTS_TOPIC_ARN,
        settings.AWS.SNS_PRODUCT_EVENTS_TOPIC_ARN,
    ]

    successful_topics = []
    failed_topics = []

    for arn in topic_arn_settings:
        topic_name = extract_topic_name_from_arn(arn)
        if not topic_name:
            logging.warning(f"Could not extract topic name from invalid ARN: '{arn}'. Skipping.")
            failed_topics.append(str(arn))
            continue

        try:
            logging.info(f"Checking/creating SNS topic: '{topic_name}'...")
            response = sns_client.create_topic(Name=topic_name)
            created_arn = response.get("TopicArn")
            if created_arn:
                logging.info(f"Successfully ensured topic '{topic_name}' exists with ARN: {created_arn}")
                successful_topics.append(topic_name)
            else:
                logging.error(f"Failed to create topic '{topic_name}'. No ARN in response.")
                failed_topics.append(topic_name)
        except ClientError as e:
            logging.error(f"Error creating topic '{topic_name}': {e}")
            failed_topics.append(topic_name)
        except Exception as e:
            logging.error(f"An unexpected error occurred for topic '{topic_name}': {e}")
            failed_topics.append(topic_name)

    logging.info("\n--- SNS Topic Setup Summary ---")
    if successful_topics:
        logging.info(f"Successfully created/verified {len(successful_topics)} topics: {', '.join(successful_topics)}")
    if failed_topics:
        logging.error(f"Failed to create/verify {len(failed_topics)} topics/ARNs: {', '.join(failed_topics)}")
    logging.info("---------------------------------")

def _setup_sqs_queues_sync():
    """
    Synchronous function to set up SQS queues. Designed to be run in a threadpool.
    """
    logging.info("Starting SQS queue setup...")

    try:
        sqs_client = boto3.client(
            "sqs",
            region_name=settings.AWS.REGION,
            aws_access_key_id=settings.AWS.ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS.SECRET_ACCESS_KEY.get_secret_value(),
        )
        logging.info(f"Successfully created boto3 SQS client for region: {settings.AWS.REGION}")

    except NoCredentialsError:
        logging.error("AWS credentials not found. Please configure them in your .env.dev file.")
        return
    except ClientError as e:
        logging.error(f"Failed to create AWS SQS client: {e}")
        return

    queue_url = settings.AWS.SQS_USER_ACTIVITY_QUEUE_URL
    if not queue_url:
        logging.warning("SQS_USER_ACTIVITY_QUEUE_URL is not set. Skipping SQS queue setup.")
        return

    # Extract queue name from URL
    queue_name = queue_url.split('/')[-1]

    try:
        logging.info(f"Checking/creating SQS queue: '{queue_name}'...")
        # create_queue is idempotent, so it will create if not exists, or return existing if it does
        response = sqs_client.create_queue(
            QueueName=queue_name,
            Attributes={
                'DelaySeconds': '0',
                'MessageRetentionPeriod': '345600' # 4 days
            }
        )
        created_queue_url = response['QueueUrl']
        logging.info(f"Successfully ensured SQS queue '{queue_name}' exists with URL: {created_queue_url}")
    except ClientError as e:
        logging.error(f"Error creating SQS queue '{queue_name}': {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred for SQS queue '{queue_name}': {e}")

    logging.info("---------------------------------")

async def setup_aws_resources():
    """Asynchronous wrapper to run the synchronous setup function in a threadpool."""
    logging.info("Running AWS resource setup in a background thread.")
    await run_in_threadpool(_setup_sns_topics_sync)
    await run_in_threadpool(_setup_sqs_queues_sync)

