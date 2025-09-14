from kafka import KafkaProducer
from core.settings import settings
from core.app_config import logger # Import logger

class KafkaProducerWrapper:
    _producer: KafkaProducer | None = None

    def _get_producer(self):
        if self._producer is None:
            logger.info("Initializing Kafka producer...") # Use logger.info
            # Build Kafka configuration
            kafka_config = {
                'bootstrap_servers': settings.KAFKA.BOOTSTRAP_SERVERS
            }

            # Add SASL SSL configuration if available - for Confluent Cloud
            if all([settings.KAFKA.SECURITY_PROTOCOL, 
                    settings.KAFKA.SASL_MECHANISM, 
                    settings.KAFKA.SASL_USERNAME, 
                    settings.KAFKA.SASL_PASSWORD]):
                kafka_config.update({
                    'security_protocol': settings.KAFKA.SECURITY_PROTOCOL,
                    'sasl_mechanism': settings.KAFKA.SASL_MECHANISM,
                    'sasl_plain_username': settings.KAFKA.SASL_USERNAME,
                    'sasl_plain_password': settings.KAFKA.SASL_PASSWORD.get_secret_value()
                })
            
            try:
                self._producer = KafkaProducer(**kafka_config)
                logger.info("Successfully connected to Kafka producer.") # Use logger.info
            except Exception as e:
                logger.error(f"Failed to create Kafka producer: {e}", exc_info=True) # Use logger.error
                # self._producer remains None, subsequent calls will retry
        return self._producer

    def __getattr__(self, name):
        # Delegate calls like .send(), .flush() to the actual producer instance
        producer_instance = self._get_producer()
        if producer_instance:
            return getattr(producer_instance, name)
        else:
            # If producer creation failed, we should not hide the error.
            # Raising an exception here makes the failure explicit.
            raise RuntimeError("Kafka producer is not initialized or connection failed.")

producer = KafkaProducerWrapper()

def close_kafka_producer():
    # Access the internal producer to close it
    if producer._producer:
        logger.info("Closing Kafka producer...") # Use logger.info
        producer.flush()
        producer.close()
        logger.info("Kafka producer closed.") # Use logger.info
