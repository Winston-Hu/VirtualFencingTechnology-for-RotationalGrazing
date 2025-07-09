#!/usr/bin/env python3
import json
import time
import paho.mqtt.client as mqtt

BROKER = "10.166.179.5"
PORT = 1883

TOPIC_PUB = "/SparkTest/pub"
TOPIC_SUB = "/SparkTest/BrokerAnswer"
PAYLOAD_DATA = {"payload": "z5511644"}


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to broker")
        client.subscribe(TOPIC_SUB)
        client.publish(TOPIC_PUB, json.dumps(PAYLOAD_DATA))
        print(f"Published to {TOPIC_PUB}: {PAYLOAD_DATA} after connecting immediately")
    else:
        print("Connection failed, code =", rc)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        data = msg.payload.decode()
    print(f"Received on {msg.topic}: {data}")


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT)
    client.loop_start()

    try:
        while True:
            client.publish(
                TOPIC_PUB,
                json.dumps(PAYLOAD_DATA)
            )
            print(f"Published to {TOPIC_PUB}: {PAYLOAD_DATA}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("Interrupted by user, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
