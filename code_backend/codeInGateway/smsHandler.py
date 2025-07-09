# Enter your python code.
import json
import traceback
from common.Logger import logger
from mobiuspi_lib.cellular import Cellular

# init Cellular
try:
    cel = Cellular()
    logger.info("Cellular instance initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Cellular: {str(e)}")
    raise

# SMS_CENTER = "+61418706700"  # telstra
SMS_CENTER = "+61411990001"  # optus


def main(topic, payload):
    """
    Receive SMS payload and send SMS to appropriate phone numbers based on device type.
    Topic: /BLEpublish
    """

    logger.info(f"Received message on topic {topic}: {payload}")

    data_SMS = {
                "sms_mode": 1,
                "phone_number": '0402386294',
                "sms_content": "Spark Test",
                "sms_center": SMS_CENTER
            }
    logger.info("SMS data prepared")

    # Send SMS
    result = cel.send_sms(data=data_SMS)
    if result:
        logger.info("SMS sent successfully")
    else:
        logger.error("Failed to send SMS")

