#!/usr/bin/env python3
import json
import paho.mqtt.client as mqtt

BROKER = "10.166.179.5"
PORT = 1883
TOPIC_SUB = "/SparkTest/pub"
TOPIC_PUB = "/SparkTest/BrokerAnswer"


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Responder connected, subscribing to", TOPIC_SUB)
        client.subscribe(TOPIC_SUB)
    else:
        print("Responder connection failed, code =", rc)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        data = {"payload": msg.payload.decode()}

    if isinstance(data, dict):
        data["message"] = "Broker connect successfully"
    else:
        data = {
            "payload": data,
            "message": "Broker connect successfully"
        }

    payload_out = json.dumps(data)
    client.publish(TOPIC_PUB, payload_out)
    print(f"Received on {msg.topic}: {msg.payload.decode()}")
    print(f"Replied on {TOPIC_PUB}: {payload_out}")


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT)
    client.loop_forever()


if __name__ == "__main__":
    main()
