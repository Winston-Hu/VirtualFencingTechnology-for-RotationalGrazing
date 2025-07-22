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
    Payload:
        {"cow_id": "cow1", "grid": "[-3, 12]", "isOutside": "On"}
        {"cow_id": "cow1", "grid": "[-3, 12]", "isOutside": "Back"}
    """

    logger.info(f"Received message on topic {topic}: {payload}")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.error("JSON decode failed: %s – raw data: %s", exc, payload)
        return

    cow_id = data.get("cow_id", "Unknown Cow")
    isOutside = data.get("isOutside", "Unknown isOutside")
    if isOutside == "On":
        isOutside = "Outside the fence"
    content = f"the {cow_id} now is {isOutside}"
    phone_number_list = ['0402386294', '0403290319', '0401602408', '0466615511', '0450063062']
    # phone_number_list = ['0402386294']
    for phone_number in phone_number_list:
        data_SMS = {
                    "sms_mode": 1,
                    "phone_number": phone_number,
                    "sms_content": content,
                    "sms_center": SMS_CENTER
                }
        logger.info("SMS data prepared")

        # Send SMS
        result = cel.send_sms(data=data_SMS)
        if not result:
            logger.info("SMS sent successfully")
        else:
            logger.error("Failed to send SMS")

