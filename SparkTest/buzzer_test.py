import logging
import atexit
import time
from pyModbusTCP.client import ModbusClient
from logging.handlers import RotatingFileHandler

from lib.buzzer_modbusTCP import BuzzerModbus

# use JIG02 LAN / IR302 and relay config
HOST_IR302_TRANS = "10.166.179.25"
PORT_IR302_TRANS = 8233
SLAVE_RELAY = 2


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
        filename="alarmHandler.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)


def sendAlarm():
    """
    1. get payload from AI prediction
    2. send mqtt payload: {# out of range}, /BLEpublish
    3. use buzzer_modbusTCP to control buzzer ring
    """
    setup_logging()

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
        except:
            pass

    atexit.register(_close_all_clients)

    while True:
        # buzzer.set_on()
        # time.sleep(5)
        buzzer.set_off()
        time.sleep(5)


if __name__ == "__main__":
    sendAlarm()
