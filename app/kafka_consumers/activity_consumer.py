import json
import boto3
import os
import sys
import time
from botocore.exceptions import ClientError

# Add the project root to the Python path to allow importing from 'core'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.settings import settings

def main():
    """
    An SQS consumer that listens to the 'user_activity_events' SQS queue
    and processes messages.
    """
    print("Loading environment configuration...")
    # Settings are loaded automatically when 'settings' is imported
    print("Environment loaded.")

    sqs_queue_url = settings.AWS.SQS_USER_ACTIVITY_QUEUE_URL
    aws_region = settings.AWS.REGION

    if not sqs_queue_url:
        print("Error: SQS_USER_ACTIVITY_QUEUE_URL is not set in environment variables.")
        return

    print(f"Connecting to SQS queue: {sqs_queue_url} in region {aws_region}...")

    try:
        sqs_client = boto3.client(
            "sqs",
            region_name=aws_region,
            aws_access_key_id=settings.AWS.ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS.SECRET_ACCESS_KEY.get_secret_value(),
        )

        print(f"Successfully connected. Listening for messages on SQS queue '{sqs_queue_url}'...")
        print("Press Ctrl+C to stop the consumer.")

        while True:
            try:
                response = sqs_client.receive_message(
                    QueueUrl=sqs_queue_url,
                    MaxNumberOfMessages=10,  # Retrieve up to 10 messages at a time
                    WaitTimeSeconds=20,      # Long polling
                )

                messages = response.get('Messages', [])

                if messages:
                    for message in messages:
                        print("\n--- New Message Received ---")
                        print(f"Message ID: {message.get('MessageId')}")
                        print("Body:")
                        try:
                            # SQS messages from SNS will have the actual message in the 'Message' attribute of the body
                            message_body = json.loads(message['Body'])
                            sns_message = json.loads(message_body['Message'])
                            print(json.dumps(sns_message, indent=2))
                        except json.JSONDecodeError:
                            print(message['Body']) # Not a JSON message, print as is
                        except KeyError:
                            print(message['Body']) # Not an SNS message, print as is

                        # Delete the message from the queue after processing
                        sqs_client.delete_message(
                            QueueUrl=sqs_queue_url,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                        print(f"Message {message.get('MessageId')} deleted from queue.")
                        print("--------------------------")
                else:
                    print("No messages in queue. Waiting...")

            except ClientError as e:
                print(f"An AWS client error occurred: {e}")
                time.sleep(5) # Wait before retrying on client error
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                time.sleep(5) # Wait before retrying on other errors

    except Exception as e:
        print(f"An error occurred during SQS client initialization: {e}")


if __name__ == "__main__":
    main()