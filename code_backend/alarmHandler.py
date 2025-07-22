import logging
import atexit
import time
import json
from pathlib import Path
from pyModbusTCP.client import ModbusClient
from logging.handlers import RotatingFileHandler

from lib.buzzer_modbusTCP import BuzzerModbus
from lib.listen_event import alarm_dictionary, start_mqtt_listener, _dict_lock
from lib import publisher


# use JIG02 LAN / IR302 and relay config
HOST_IR302_TRANS = "10.166.179.25"
PORT_IR302_TRANS = 8233
SLAVE_RELAY = 2
POOLING_INTERVAL = 10

# MQTT config
BROKER = "10.166.179.5"
BROKER_PORT = 1883
USERNAME = ''
PASSWORD = ''
SMS_TOPIC = "/smsControl"

last_alarm_dic = {}


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / "alarmHandler.log"


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    )
    logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)


def alarm_send_sms(cow_id, grid, isOutside):
    json_data = {
        "cow_id":   str(cow_id),
        "grid":     str(grid),
        "isOutside": isOutside  # "On" or "Back"
    }
    json_payload = json.dumps(json_data, default=str)
    result = publisher.push_message(BROKER, BROKER_PORT, USERNAME, PASSWORD, SMS_TOPIC, json_payload)
    if result[0] == 0:
        logging.info(f"Sent SMS to {cow_id}: {isOutside}")
    else:
        logging.error(f"Failed to send SMS to {cow_id}: {isOutside}, Error code: {result[0]}")
    logging.info(f"Sent SMS to {cow_id}: {isOutside}")


def sendAlarm():
    """
    1. get payload from AI prediction
    2. send mqtt payload: {# out of range}, /BLEpublish
    3. use buzzer_modbusTCP to control buzzer ring
    """
    global last_alarm_dic
    setup_logging()
    try:
        start_mqtt_listener()
        logging.info("Successfully listen to event -> alarm_dictionary")
    except Exception as e:
        logging.error("Error happen when listen event")

    buzzer = None
    buzzer_client = ModbusClient(host=HOST_IR302_TRANS, port=PORT_IR302_TRANS, timeout=3)
    if not buzzer_client.open():
        logging.error(f"Failed to connect buzzer to {HOST_IR302_TRANS}:{PORT_IR302_TRANS}")
    else:
        buzzer = BuzzerModbus(buzzer_client, slave_id=SLAVE_RELAY)

    def _close_all_clients():
        try:
            if buzzer:
                buzzer.close()
        except Exception as close_all_clients_error:
            logging.error(f"close_all_clients_error: {close_all_clients_error}")
            pass

    atexit.register(_close_all_clients)

    # state machine
    buzzer_on = False  # default -> not ring
    last_time_update = 0

    while True:
        try:
            current_time = time.time()

            # get_alarm_dictionary() expected payload:{'cow1': [1,1]} or {}
            with _dict_lock:
                alarm_dic = alarm_dictionary.copy()  # get the alarm cows info here, need MQTT listen
            current_alarm_count = len(alarm_dic)  # count how many cows in alarm
            logging.info(f"(Alarm count: {current_alarm_count})")

            # alarm_dic -> {}
            if current_alarm_count == 0:
                # buzzer control
                # force buzzer off
                logging.info(current_time - last_time_update)
                if current_time - last_time_update >= POOLING_INTERVAL:
                    last_time_update = current_time
                    try:
                        buzzer.set_off()
                        logging.info("Forced buzzer off")
                    except Exception as e:
                        logging.error(f"Failed to turn off buzzer force: {e}")

                # turn off buzzer if buzzer on
                if buzzer_on:
                    try:
                        buzzer.set_off()
                        logging.info("Turn off the buzzer")
                        buzzer_on = False
                    except ConnectionError as e:
                        logging.error(f"Failed to turn off buzzer: {e}")

                # sms control
                try:
                    # sms payload, need to cancel the last alarm one
                    if last_alarm_dic:
                        for cow_id, grid in last_alarm_dic.items():
                            alarm_send_sms(cow_id, grid, "Back")
                        logging.info("Sent SMS clear for all previously alarmed cows")
                    last_alarm_dic = {}  # Clear last_alarm_dic after sending
                except Exception as e:
                    logging.error(f"Sms clear sent error: {e}")

            # alarm_dic -> {'cow1': [1, 1]}
            elif current_alarm_count != 0:

                # buzzer control
                if not buzzer_on:
                    try:
                        buzzer.set_on()
                        logging.info(f"Turn on the buzzer")
                    except Exception as e:
                        logging.error(f"Failed to turn on the buzzer: {e}")
                buzzer_on = True

                try:
                    for cow_id, grid in alarm_dic.items():
                        # sms control
                        if cow_id not in last_alarm_dic:
                            alarm_send_sms(cow_id, grid, "On")

                    # Find cleared alarms (cows in last_alarm_dic but not in current alarm_dic)
                    for cow_id, grid in last_alarm_dic.items():
                        if cow_id not in alarm_dic:
                            alarm_send_sms(cow_id, grid, "Back")

                    last_alarm_dic = alarm_dic.copy()
                except Exception as e:
                    logging.error(f"SMS handling error: {e}")

        except Exception as e:
            logging.error(f"Failed in while loop: {e}")

        time.sleep(1)


if __name__ == "__main__":
    sendAlarm()
