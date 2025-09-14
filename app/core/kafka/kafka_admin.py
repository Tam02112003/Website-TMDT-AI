import asyncio
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from core.settings import settings

# List of topics that the application requires
REQUIRED_TOPICS = [
    'product_events',
    'comments',
    'news',
    'discounts',
    'order_events',
    'payment_events',
    'auth_events'
]

def get_admin_client_config():
    """Builds the configuration dictionary for the KafkaAdminClient."""
    config = {
        'bootstrap_servers': settings.KAFKA.BOOTSTRAP_SERVERS
    }
    if all([settings.KAFKA.SECURITY_PROTOCOL,
            settings.KAFKA.SASL_MECHANISM, 
            settings.KAFKA.SASL_USERNAME, 
            settings.KAFKA.SASL_PASSWORD]):
        config.update({
            'security_protocol': settings.KAFKA.SECURITY_PROTOCOL,
            'sasl_mechanism': settings.KAFKA.SASL_MECHANISM,
            'sasl_plain_username': settings.KAFKA.SASL_USERNAME,
            'sasl_plain_password': settings.KAFKA.SASL_PASSWORD.get_secret_value()
        })
    return config

async def create_topics_if_needed():
    """
    Checks for required Kafka topics and creates them if they don't exist.
    This is an async function to be called from an async context (like FastAPI startup).
    """
    print("Checking for required Kafka topics...")
    admin_client = None
    try:
        config = get_admin_client_config()
        admin_client = KafkaAdminClient(**config)

        existing_topics = await asyncio.to_thread(admin_client.list_topics)
        
        topics_to_create = []
        for topic_name in REQUIRED_TOPICS:
            if topic_name not in existing_topics:
                print(f"Topic '{topic_name}' not found. Scheduling for creation.")
                # Confluent Cloud requires replication_factor >= 3
                topics_to_create.append(
                    NewTopic(name=topic_name, num_partitions=6, replication_factor=3)
                )
        
        if topics_to_create:
            try:
                await asyncio.to_thread(admin_client.create_topics, new_topics=topics_to_create, validate_only=False)
                print(f"Successfully created topics: {[t.name for t in topics_to_create]}")
            except TopicAlreadyExistsError:
                print("Some topics were already created by another process. This is safe.")
            except Exception as e:
                print(f"Could not create Kafka topics: {e}")
        else:
            print("All required Kafka topics already exist.")

    except Exception as e:
        print(f"Could not connect to Kafka AdminClient: {e}")
    finally:
        if admin_client:
            admin_client.close()
