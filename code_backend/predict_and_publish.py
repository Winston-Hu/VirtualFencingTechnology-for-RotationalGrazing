import json
import pandas as pd
import joblib
import paho.mqtt.client as mqtt
from collections import defaultdict, deque, Counter

# === MQTT Configuration ===
MQTT_BROKER = '10.166.179.5'
MQTT_PORT = 1883
PUBLISH_TOPIC = "/modelPublish"
SUBSCRIBE_TOPIC = "/BLEPublish"

# === Load model and mappings ===
model = joblib.load('model/weight/knn_model.pkl')
grid_encoder = joblib.load('model/weight/grid_label_encoder.pkl')
label_map = joblib.load('model/weight/grid_to_label_mapping.pkl')
col_mean_map = joblib.load('model/weight/global_column_means.pkl')
grid_mean_map = joblib.load('model/weight/grid_mean_map.pkl')

# === Constants ===
SPECIAL_FILL_VALUE = -106
GRID_HISTORY_LEN = 5

# === RSSI column names (with receiver info) ===
rssi_cols = ['RSSI_0_0', 'RSSI_0_8', 'RSSI_8_0', 'RSSI_8_8', 'RSSI_16_0', 'RSSI_16_8']

# === Sliding window: recent predicted grids for each device ===
cow_grid_history = defaultdict(lambda: deque(maxlen=GRID_HISTORY_LEN))  # key: cow_id, value: list of previous predicted grids


# === Missing value imputation using recent grid or column mean ===
def fill_missing_with_grid_or_column_mean(rssi_series, cow_id, col_mean_map, grid_mean_map):
    filled = rssi_series.copy()
    history = cow_grid_history[cow_id]
    fallback_grid = Counter(history).most_common(1)[0][0] if history else None

    for col in filled.index:
        if pd.isna(filled[col]):
            if fallback_grid and fallback_grid in grid_mean_map.index and col in grid_mean_map.columns:
                filled[col] = grid_mean_map.at[fallback_grid, col]
            else:
                filled[col] = col_mean_map.get(col, SPECIAL_FILL_VALUE)
    return filled


# === Prediction and MQTT publishing ===
def predict_and_publish(input_data: dict):
    """
    input_data: dict, such as {"cow1": [RSSI_0_0, RSSI_0_8, ..., RSSI_16_8]}
    """
    payload = {}

    for cow_id, rssi_vector in input_data.items():
        if len(rssi_vector) != len(rssi_cols):
            print(f"❌ Skipping {cow_id} due to incorrect vector length")
            continue

        rssi_series = pd.Series(rssi_vector, index=rssi_cols, dtype=float)

        # === Handle missing values ===
        if rssi_series.isna().any():
            print(f"⚠️ Missing values detected in {cow_id}, filling with history Grid or column mean...")
            rssi_series = fill_missing_with_grid_or_column_mean(rssi_series, cow_id, col_mean_map, grid_mean_map)

        X_input = rssi_series.values.reshape(1, -1)

        try:
            pred_grid_encoded = model.predict(X_input)[0]
            pred_grid = grid_encoder.inverse_transform([pred_grid_encoded])[0]
            is_out = 1 if label_map.get(pred_grid) == 'out' else 0

            # === Update sliding window history ===
            cow_grid_history[cow_id].append(pred_grid)

            grid_x, grid_y = map(int, pred_grid.split('_'))
            payload[cow_id] = [grid_x, grid_y, is_out]
        except Exception as e:
            print(f"⚠️ Prediction error for {cow_id}: {e}")

    # === Publish message via MQTT ===
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    message = json.dumps(payload)
    client.publish(PUBLISH_TOPIC, message)
    print("✅ Published to topic:", PUBLISH_TOPIC)
    print("📦 Payload:", json.dumps(payload))
    client.disconnect()


# === MQTT Connection and Subscription ===
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT Broker")
        client.subscribe(SUBSCRIBE_TOPIC)
        print(f"📡 Subscribed to topic: {SUBSCRIBE_TOPIC}")
    else:
        print(f"❌ Connection failed with code {rc}")


# === Handle incoming messages ===
def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
        input_data = json.loads(payload_str)
        # {"cow1": [RSSI_0_0, RSSI_0_8, ..., RSSI_16_8]}
        print("📥 Received message:")
        print(json.dumps(input_data, indent=2))

        predict_and_publish(input_data)

    except Exception as e:
        print(f"⚠️ Error handling message: {e}")


# === Start MQTT Listener ===
def start_mqtt_listener():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    print("🚀 MQTT Listener started...")
    client.loop_forever()


# === Entry point ===
if __name__ == "__main__":
    start_mqtt_listener()
