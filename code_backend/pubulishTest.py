from lib import publisher
import json

BROKER = "10.166.179.5"
BROKER_PORT = 1883
USERNAME = ''
PASSWORD = ''
PUB_TOPIC = "/NoraTopic"
WHATEVER_NUM = 10

for i in range(WHATEVER_NUM):
    txt_payload = {"key_sample": "value_sample"}
    json_payload = json.dumps(txt_payload)
    publisher.push_message(BROKER, BROKER_PORT, USERNAME, PASSWORD, PUB_TOPIC, json_payload)
