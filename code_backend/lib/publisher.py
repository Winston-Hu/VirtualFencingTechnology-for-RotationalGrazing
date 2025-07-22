"""
publisher.push_message(DATABASE_BROKER, DATABASE_PORT, USERNAME, PASSWORD, TOPIC, payload)
"""
import time
import traceback
import threading
import paho.mqtt.client as mqtt
import os
import logging
from logging.handlers import RotatingFileHandler

_clients = {}
_clients_lock = threading.Lock()
MQTT_KEEPALIVE = 60

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'publisherlog.log')

liblog = logging.getLogger('publisherlog')
liblog.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5*1024*1024,
    backupCount=2,
    encoding='utf-8'
)
file_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(file_fmt)
liblog.addHandler(file_handler)

def _get_client(broker, port, username=None, password=None):
    """
    Reuse or create mqtt.Client according to broker/port/username/password
    """
    key = (broker, port, username, password)
    with _clients_lock:
        if key not in _clients:
            client = mqtt.Client()
            if username is not None:
                client.username_pw_set(username, password)
            client.on_connect = lambda c, u, f, rc: liblog.info(f"MQTT({broker}:{port}) connected, rc={rc}")
            client.on_disconnect = lambda c, u, rc: liblog.warning(f"MQTT({broker}:{port}) disconnected, rc={rc}")
            client.connect(broker, port, keepalive=MQTT_KEEPALIVE)  # Use synchronous connect
            client.loop_start()
            _clients[key] = client
        return _clients[key]

def push_message(broker, port, username, password, topic, payload, qos=0, retain=False):
    """
    According to the incoming connection parameters, first get the corresponding Client, then publish.
    If an error occurs, try to reconnect and resend up to 3 times with delays.
    """
    client = _get_client(broker, port, username, password)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result, mid = client.publish(topic, payload, qos, retain)
            if result == mqtt.MQTT_ERR_SUCCESS:
                liblog.info(f"Successfully published to {topic}: {payload}")
                return (result, mid)
            else:
                liblog.error(f"Publish to {topic} failed, result code: {result}")
                raise Exception(f"Publish failed with code {result}")
        except Exception as e:
            liblog.error(f"[{broker}:{port}] Publish error (attempt {attempt + 1}/{max_retries}): {e}")
            traceback.print_exc()
            if attempt < max_retries - 1:
                liblog.info(f"Attempting to reconnect and retry...")
                try:
                    client.reconnect()
                    time.sleep(1)  # Wait before retry
                except Exception as e2:
                    liblog.error(f"Reconnect failed: {e2}")
            else:
                liblog.error(f"Max retries reached, giving up on {topic}")
                return (mqtt.MQTT_ERR_NO_CONN, None)