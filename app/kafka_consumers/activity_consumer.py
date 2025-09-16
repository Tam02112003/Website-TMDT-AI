import json
import os
import sys
from kafka import KafkaConsumer

# Add the project root to the Python path to allow importing from 'core'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import the environment loader
from core.settings import load_environment

def main():
    """
    A Kafka consumer that connects to Confluent Cloud, listens to the
    'user_activity_events' topic, and prints the messages.
    """
    print("Loading environment configuration...")
    # Load environment variables from ../env/.env.dev
    load_environment()
    print("Environment loaded.")

    # Get Kafka settings from environment variables
    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    kafka_security_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL")
    kafka_sasl_mechanism = os.getenv("KAFKA_SASL_MECHANISM")
    kafka_sasl_username = os.getenv("KAFKA_SASL_USERNAME")
    kafka_sasl_password = os.getenv("KAFKA_SASL_PASSWORD")
    
    topic_name = 'user_activity_events'

    if not all([kafka_bootstrap_servers, kafka_sasl_username, kafka_sasl_password]):
        print("Error: Kafka environment variables are not fully set.")
        print("Please check your .env.dev file for KAFKA_BOOTSTRAP_SERVERS, KAFKA_SASL_USERNAME, and KAFKA_SASL_PASSWORD.")
        return

    print(f"Connecting to Kafka broker at {kafka_bootstrap_servers}...")

    try:
        consumer = KafkaConsumer(
            topic_name,
            bootstrap_servers=kafka_bootstrap_servers,
            security_protocol=kafka_security_protocol,
            sasl_mechanism=kafka_sasl_mechanism,
            sasl_plain_username=kafka_sasl_username,
            sasl_plain_password=kafka_sasl_password,
            auto_offset_reset='earliest',
            group_id='my-activity-consumer-group-1', # Use a unique group id
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        print(f"Successfully connected. Listening for messages on topic '{topic_name}'...")
        print("Press Ctrl+C to stop the consumer.")

        for message in consumer:
            print("\n--- New Message Received ---")
            print(f"Topic: {message.topic}")
            print(f"Partition: {message.partition}")
            print(f"Offset: {message.offset}")
            print("Data:")
            print(json.dumps(message.value, indent=2))
            print("--------------------------")

    except Exception as e:
        print(f"An error occurred while connecting or consuming: {e}")

if __name__ == "__main__":
    main()
