import os
import logging
import threading
import json
from logging.handlers import RotatingFileHandler

import paho.mqtt.client as mqtt
import time

# Broker Info
BROKER = '10.166.179.5'
PORT = 1883
USERNAME = ''
PASSWORD = ''
TOPIC = "/modelPublish"

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'listenEventlog.log')

listenEventlog = logging.getLogger('listenEventlog')
listenEventlog.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5*1024*1024,
    backupCount=2,
    encoding='utf-8'
)
file_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(file_fmt)
listenEventlog.addHandler(file_handler)

# Global Singleton Variables and Locks
_client = None
_client_lock = threading.Lock()

# Global Dictionary and Locks
alarm_dictionary = {}
_dict_lock = threading.Lock()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        listenEventlog.info("MQTT Connection successful, start subscription %s", TOPIC)
        client.subscribe(TOPIC, qos=1)
    else:
        listenEventlog.error("MQTT Connection failed, return code %s", rc)


def on_disconnect(client, userdata, rc):
    listenEventlog.warning("MQTT Disconnected, return code %s", rc)
    if rc != 0:  # not disconnect manually
        listenEventlog.info("Unexpected disconnection, attempting to reconnect...")
        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            try:
                client.reconnect()
                listenEventlog.info("MQTT Reconnection successful")
                break
            except Exception as e:
                retry_count += 1
                listenEventlog.error("Reconnection failed (%d/%d): %s", retry_count, max_retries, e, exc_info=True)
                time.sleep(5)
                if retry_count == max_retries:
                    listenEventlog.error("Max reconnection attempts reached, stopping retries")


def on_message(client, userdata, msg):
    global alarm_dictionary
    try:
        raw = msg.payload.decode()
        listenEventlog.debug("Receive payload: %s", raw)
        payload = json.loads(raw)  # {"cow1": [1,1,1], "cow2": [1,2,1], ...}

        if payload:
            with _dict_lock:
                for cow_id, grid_fenceInfo in payload.items():
                    if not isinstance(grid_fenceInfo, list) or len(grid_fenceInfo) < 3:
                        listenEventlog.error("Invalid grid_fenceInfo for cow %s: %s", cow_id, grid_fenceInfo)
                        continue

                    grid = grid_fenceInfo[:2]
                    isOutside = grid_fenceInfo[-1]  # isOutside = 1 -> outside

                    if isOutside == 1:
                        alarm_dictionary[cow_id] = grid  # {'cow1': [1,1]}
                        listenEventlog.debug(f"add {cow_id} in alarm_dictionary")
                    elif isOutside == 0:
                        if cow_id in alarm_dictionary:
                            del alarm_dictionary[cow_id]  # alarm_dictionary -> {}
                            listenEventlog.debug(f"del {cow_id} in alarm_dictionary")

    except Exception as e:
        listenEventlog.error("on_message dealing failed: %s", e, exc_info=True)


def start_mqtt_listener(broker_url=BROKER, broker_port=PORT):
    global _client
    with _client_lock:
        if _client is not None:
            listenEventlog.debug("There is already an MQTT client instance, skip reinitialization")
            return _client

        listenEventlog.info("Initialize MQTT client, connect %s:%s", broker_url, broker_port)
        # dynamic client_id
        client = mqtt.Client(client_id=f"listen_event_{os.getpid()}", clean_session=True)
        if USERNAME and PASSWORD:
            client.username_pw_set(USERNAME, PASSWORD)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message

        try:
            client.connect(broker_url, broker_port, keepalive=60)
        except Exception as e:
            listenEventlog.error("MQTT Connection abnormality: %s", e, exc_info=True)
            raise

        client.loop_start()
        _client = client
        listenEventlog.info("MQTT Listening started (singleton mode)")
        return _client


def stop_mqtt_listener():
    global _client
    with _client_lock:
        if _client is None:
            listenEventlog.info("No running MQTT client")
            return
        try:
            _client.loop_stop()
            _client.disconnect()
            listenEventlog.info("MQTT Client stopped")
        except Exception as e:
            listenEventlog.error("Failed to stop MQTT client: %s", e, exc_info=True)
        finally:
            _client = None


if __name__ == "__main__":
    try:
        start_mqtt_listener()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listenEventlog.info("Received interrupt signal, stopping listener...")
        stop_mqtt_listener()
    except Exception as e:
        listenEventlog.error("Program exception: %s", e, exc_info=True)
        stop_mqtt_listener()