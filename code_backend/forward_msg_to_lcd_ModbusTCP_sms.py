import threading
import time
from sqlalchemy import create_engine
import pandas as pd
import json
import atexit
from pyModbusTCP.client import ModbusClient

from lib import publisher
from lib import listen_event
from lib import logger
from lib.TwoLineLCD_ModbusTCP import LCDDisplayModbus
from lib.buzzer_modbusTCP import BuzzerModbus
from datetime import datetime

log_info, log_error, log_debug = logger.log_info, logger.log_error, logger.log_debug

# DB_URI = "mysql+mysqlconnector://jdk:3.1415926Pi@10.166.156.21:3306/jassi"  # ramsay
DB_URI = "mysql+mysqlconnector://jdk:3.1415926Pi@192.168.2.3:3306/jassi"
engine = create_engine(DB_URI, echo=False, pool_size=5, max_overflow=10, pool_timeout=30, pool_pre_ping=True)

LCD_SLAVE_ID = 1
BUZZER_SLAVE_ID = 2

DATABASE_BROKER = '192.168.2.2'
DATABASE_PORT = 1883
USERNAME = ''
PASSWORD = ''
TOPIC = "jassi/sms"

alarm_duration = {}
sent_sms_flags = {}

pre_title = "None"

class ConfigCache:
    _instance = None
    _lock = threading.Lock()
    _config = None
    _lcd_devices = None
    _device_info = {}  # 存储 j_code -> {"label": ..., "holder": ...}
    _device_changed = False  # 标记 device_info 是否变更
    _last_update = 0
    _update_interval = 10
    _default_config = {
        'lcd_display_in_green_time': 30,
        'lcd_display_in_yellow_time': 60,
        'sms_alarm_pb_time': 900,
        'sms_alarm_tracker_time': 300,
        'lcd_scrolling_alarm_interval': 1,
        'sms_destination_pb': '0456888156',
        'sms_destination_tracker': '0456888156',
        'lcd_static_title': 'Ramsay Health'
    }

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            threading.Thread(target=cls._update_loop, daemon=True).start()
        return cls._instance

    @classmethod
    def _update_loop(cls):
        while True:
            cls._update()
            time.sleep(cls._update_interval)

    @classmethod
    def _update(cls):
        with cls._lock:
            try:
                # 更新 system_config
                sql_query = "SELECT config_name, value FROM system_config;"
                df_config = pd.read_sql(sql_query, engine)
                config_dict = dict(zip(df_config['config_name'], df_config['value']))
                new_config = {}
                for key, default in cls._default_config.items():
                    value = config_dict.get(key, default)
                    if key in ['sms_destination_pb', 'sms_destination_tracker']:
                        if isinstance(value, str) and value:
                            new_config[key] = [num.strip() for num in value.split('-')]
                        else:
                            new_config[key] = [str(default)]
                    elif key == 'lcd_static_title':
                        new_config[key] = value
                    else:
                        new_config[key] = float(value) if value is not None else float(default)

                # 更新 lcd_devices
                sql_query_lcd = """
                    SELECT ip, modbus_tcp_port, mute 
                    FROM network_infrastracture_list 
                    WHERE device_type = 'annunciator';
                """
                df_lcd = pd.read_sql(sql_query_lcd, engine)
                new_lcd_devices = []
                for _, row in df_lcd.iterrows():
                    new_lcd_devices.append({
                        'ip': row['ip'],
                        'port': int(row['modbus_tcp_port']),
                        'mute': int(row['mute']) == 0
                    })

                # 更新 device_info（假设 LoRaWAN 设备的表名为 device_list，包含 devEui, label, holder）
                sql_query_device = """
                    SELECT j_code, label, holder 
                    FROM device_list 
                    WHERE j_code IS NOT NULL;
                """
                df_device = pd.read_sql(sql_query_device, engine)
                new_device_info = {
                    row['j_code']: {
                        'label': row['label'] if pd.notna(row['label']) else 'Unknown',
                        'holder': row['holder'] if pd.notna(row['holder']) else 'Unknown'
                    } for _, row in df_device.iterrows()
                }

                # 检查是否变更
                if cls._lcd_devices != new_lcd_devices:
                    cls._lcd_devices = new_lcd_devices
                    cls._device_changed = True
                    log_info("forward_msg_to_lcd", f"LCD devices changed: {cls._lcd_devices}")
                if cls._config != new_config:
                    cls._config = new_config
                    log_info("forward_msg_to_lcd", f"Updated config: {cls._config}")
                if cls._device_info != new_device_info:
                    cls._device_info = new_device_info
                    cls._device_changed = True
                    log_info("forward_msg_to_lcd", f"Updated device_info: {cls._device_info}")
                cls._last_update = time.time()
            except Exception as e:
                log_error("forward_msg_to_lcd", f"Failed to update config from DB: {e}")
                if cls._config is None:
                    cls._config = cls._default_config.copy()
                    cls._config['sms_destination_pb'] = [cls._config['sms_destination_pb']]
                    cls._config['sms_destination_tracker'] = [cls._config['sms_destination_tracker']]
                    log_info("forward_msg_to_lcd", f"Using default config due to DB error: {cls._config}")
                if cls._lcd_devices is None:
                    cls._lcd_devices = []
                    log_info("forward_msg_to_lcd", "No LCD devices available due to DB error")
                if cls._device_info is None:
                    cls._device_info = {}
                    log_info("forward_msg_to_lcd", "No device info available due to DB error")

    @classmethod
    def get_config(cls):
        with cls._lock:
            if cls._config is None:
                cls._update()
            return cls._config

    @classmethod
    def get_lcd_devices(cls):
        with cls._lock:
            if cls._lcd_devices is None:
                cls._update()
            return cls._lcd_devices

    @classmethod
    def get_device_info(cls, j_code: str):
        with cls._lock:
            if not cls._device_info:
                cls._update()
            return cls._device_info.get(j_code, {'label': 'Unknown', 'holder': 'Unknown'})

    @classmethod
    def get_label_to_jcode(cls):
        with cls._lock:
            if not cls._device_info:
                cls._update()
            return {info['label']: j_code for j_code, info in cls._device_info.items() if info['label'] != 'Unknown'}

    @classmethod
    def devices_changed(cls):
        with cls._lock:
            return cls._device_changed

    @classmethod
    def clear_devices_changed(cls):
        with cls._lock:
            cls._device_changed = False


def get_device_dictionary(alarm_dic):
    try:
        df = pd.read_sql("SELECT j_code, label FROM device_list;", engine)
        mapping = dict(zip(df["j_code"], df["label"]))
        return [mapping[j] for j in alarm_dic if j in mapping]
    except Exception as e:
        log_error("forward_msg_to_lcd", f"Failed to get device dictionary: {e}")
        return []


def get_alarm_color(duration: float) -> int:
    config = ConfigCache.get_instance().get_config()
    if duration < config['lcd_display_in_green_time']:
        return LCDDisplayModbus.DISPLAY_GREEN
    elif duration < config['lcd_display_in_yellow_time']:
        return LCDDisplayModbus.DISPLAY_YELLOW
    else:
        return LCDDisplayModbus.DISPLAY_RED


def send_alarm_message(lcd, line1: str, line2: str, duration1: float, duration2: float):
    try:
        lcd.switch_page(1)
        line1 = (line1[:16] if line1 else "").ljust(16)
        line2 = (line2[:16] if line2 else "").ljust(16)
        if line1.strip():
            # lcd.write_line(1, line1, get_alarm_color(duration1))
            lcd.write_line(1, line1, get_alarm_color(duration2))
        lcd.write_line(2, line2, get_alarm_color(duration2))
        log_info("forward_msg_to_lcd", f"Sent to LCD: {line1}, {line2}")
    except (ConnectionError, ValueError) as e:
        log_error("forward_msg_to_lcd", f"Failed to send alarm message to LCD: {e}")


def process_alarm_duration(alarm_dict):
    current_time = time.time()
    try:
        sql_query = "SELECT j_code, label, device_type FROM device_list;"
        df_device = pd.read_sql(sql_query, engine)
        device_info = df_device.set_index('j_code')[['label', 'device_type']].to_dict('index')
    except Exception as e:
        log_error("forward_msg_to_lcd", f"Failed to load device info: {e}")
        device_info = {}

    config = ConfigCache.get_instance().get_config()

    for device in list(alarm_duration.keys()):
        location = alarm_dict.get(device, ("", ""))[1]  # 找不到就给空串
        if device not in alarm_dict:
            if device in sent_sms_flags and (
                    sent_sms_flags[device]["PB_300"] or sent_sms_flags[device]["TrackerD_500"]):
                label = device_info.get(device, {}).get('label', 'Unknown')
                device_type = device_info.get(device, {}).get('device_type', '')
                payload = json.dumps({
                    "j_code": device,
                    "label": label,
                    "status": "cleared",
                    "device_type": device_type,
                    "sms_destination_pb": config['sms_destination_pb'],
                    "sms_destination_tracker": config['sms_destination_tracker']
                })
                try:
                    if str(location).strip().lower() == 'chargingstation':
                        continue
                    publisher.push_message(DATABASE_BROKER, DATABASE_PORT, USERNAME, PASSWORD, TOPIC, payload)
                    log_info("forward_msg_to_lcd", f"Sent cleared SMS for device {device} (label: {label})")
                except Exception as e:
                    log_error("forward_msg_to_lcd", f"Failed to send cleared SMS for device {device}: {e}")
            del alarm_duration[device]
            if device in sent_sms_flags:
                del sent_sms_flags[device]

    for device in alarm_dict:
        if device not in alarm_duration:
            alarm_duration[device] = current_time

    for device, start_time in alarm_duration.items():
        location = alarm_dict.get(device, ("", ""))[1]
        elapsed = current_time - start_time
        label = device_info.get(device, {}).get('label', 'Unknown')
        device_type = device_info.get(device, {}).get('device_type', '')

        if elapsed >= config['lcd_display_in_yellow_time']:
            log_info("forward_msg_to_lcd",
                     f"Device {device} has been in alarm for {elapsed:.1f} seconds - [Command type: {config['lcd_display_in_yellow_time']}+ sec].")
        elif elapsed >= config['lcd_display_in_green_time']:
            log_info("forward_msg_to_lcd",
                     f"Device {device} has been in alarm for {elapsed:.1f} seconds - [Command type: {config['lcd_display_in_green_time']}+ sec].")
        else:
            log_info("forward_msg_to_lcd", f"Device {device} is in alarm for {elapsed:.1f} seconds.")

        if device not in sent_sms_flags:
            sent_sms_flags[device] = {"PB_300": False, "TrackerD_500": False}

        if device_type == "PB" and elapsed > config['sms_alarm_pb_time'] and not sent_sms_flags[device]["PB_300"]:
            payload = json.dumps({
                "j_code": device,
                "label": label,
                "device_type": device_type,
                "sms_destination_pb": config['sms_destination_pb'],
                "sms_destination_tracker": config['sms_destination_tracker']
            })
            try:
                if str(location).strip().lower() == 'chargingstation':
                    continue
                publisher.push_message(DATABASE_BROKER, DATABASE_PORT, USERNAME, PASSWORD, TOPIC, payload)
                log_info("forward_msg_to_lcd",
                         f"Sent SMS for PB device {device} (label: {label}) with duration {elapsed:.1f} seconds.")
                sent_sms_flags[device]["PB_300"] = True
            except Exception as e:
                log_error("forward_msg_to_lcd", f"Failed to send SMS for PB device {device}: {e}")

        if device_type == "TrackerD" and elapsed > config['sms_alarm_tracker_time'] and not sent_sms_flags[device]["TrackerD_500"]:
            payload = json.dumps({
                "j_code": device,
                "label": label,
                "device_type": device_type,
                "sms_destination_pb": config['sms_destination_pb'],
                "sms_destination_tracker": config['sms_destination_tracker']
            })
            try:
                if str(location).strip().lower() == 'chargingstation':
                    continue
                publisher.push_message(DATABASE_BROKER, DATABASE_PORT, USERNAME, PASSWORD, TOPIC, payload)
                log_info("forward_msg_to_lcd",
                         f"Sent SMS for TrackerD device {device} (label: {label}) with duration {elapsed:.1f} seconds.")
                sent_sms_flags[device]["TrackerD_500"] = True
            except Exception as e:
                log_error("forward_msg_to_lcd", f"Failed to send SMS for TrackerD device {device}: {e}")


def send_messages():
    global pre_title
    cache = ConfigCache.get_instance()
    lcd_info = cache.get_lcd_devices()

    lcd_clients = []
    for info in lcd_info:
        lcd_client = ModbusClient(host=info["ip"], port=info["port"], timeout=3)
        if not lcd_client.open():
            log_error("forward_msg_to_lcd", f"Failed to connect LCD to {info['ip']}:{info['port']}")
            continue
        lcd = LCDDisplayModbus(lcd_client, slave_id=LCD_SLAVE_ID)
        buzzer = None
        # if info["mute"]:
        #     buzzer_client = ModbusClient(host=info["ip"], port=info["port"], timeout=1)
        #     if not buzzer_client.open():
        #         log_error("forward_msg_to_lcd", f"Failed to connect buzzer to {info['ip']}:{info['port']}")
        #     else:
        #         buzzer = BuzzerModbus(buzzer_client, slave_id=BUZZER_SLAVE_ID)
        buzzer_client = ModbusClient(host=info["ip"], port=info["port"], timeout=3)
        if not buzzer_client.open():
            log_error("forward_msg_to_lcd", f"Failed to connect buzzer to {info['ip']}:{info['port']}")
        else:
            buzzer = BuzzerModbus(buzzer_client, slave_id=BUZZER_SLAVE_ID)
        lcd_clients.append({
            "ip": info["ip"],
            "lcd": lcd,
            "buzzer": buzzer,
            "buzzer_on": False,
            "lock": threading.Lock(),
            "active": True,
            "fail_count": 0
        })
        log_info("forward_msg_to_lcd", f"Initialized connection for {info['ip']}:{info['port']}")

    def _close_all_clients():
        for dev in lcd_clients:
            try:
                dev["lcd"].close()
            except:
                pass
            try:
                if dev["buzzer"]:
                    dev["buzzer"].close()
            except:
                pass

    atexit.register(_close_all_clients)

    # State Machine Variables
    buzzer_on = False
    alarm_index = 0
    last_labels = []
    last_display_time = time.time()
    last_time_update = 0
    location_to_area = {}

    # label_to_jcode = ConfigCache.get_instance().get_label_to_jcode()
    try:
        # sql_query = "SELECT j_code, label FROM device_list;"
        # df_device = pd.read_sql(sql_query, engine)
        # label_to_jcode = dict(zip(df_device['label'], df_device['j_code']))

        sql_query_beacon = "SELECT X, Y, Z, area FROM beacon_list;"
        df_beacon = pd.read_sql(sql_query_beacon, engine)
        # Normalize coordinates to string format "(X, Y, Z)" with 2 decimal places
        location_to_area = {f"({float(row['X']):.2f}, {float(row['Y']):.2f}, {float(row['Z']):.2f})": row['area']
                            for _, row in df_beacon.iterrows()}
        # location_to_area = {
        #     (row['X'], row['Y'], row['Z']): row['area']
        #     for _, row in df_beacon.iterrows()
        # }
    except Exception as e:
        log_error("forward_msg_to_lcd", f"Failed to load device dictionary for reverse lookup: {e}")

    recover_interval = 60
    last_recover = 0.0

    while True:
        try:
            label_to_jcode = ConfigCache.get_instance().get_label_to_jcode()
            title = cache.get_config()['lcd_static_title']
            # everytime we need to check the _lcd_devices (witch is saved in the memory, no more connection to DB)
            current_cfg = ConfigCache.get_instance().get_lcd_devices()

            current_time = time.time()

            # —— 0) 定期探活所有 inactive 设备 —— #
            if current_time - last_recover >= recover_interval:
                for dev in lcd_clients:
                    if not dev['active']:
                        try:
                            # Try reopening the underlying connection first (if using a persistent connection)
                            dev['lcd'].client.open()
                            dev['lcd'].switch_page(0)
                            dev['active'] = True
                            dev['fail_count'] = 0
                            log_info("forward_msg_to_lcd", f"{dev['ip']} 恢复在线")
                        except Exception:
                            log_debug("\n---------forward_msg_to_lcd", f"{dev['ip']} still offline---------\n")
                            # still offline
                            pass
                last_recover = current_time

            # Add more LCD devices in the future, we may need the rebuild functino
            # if cache.devices_changed():
            #     rebuild_clients()
            #     cache.clear_devices_changed()

            alarm_dic = listen_event.alarm_dictionary
            current_alarm_count = len(alarm_dic)
            log_info("forward_msg_to_lcd", f"(Alarm count: {current_alarm_count})")

            # 不关注value的格式，此时已经在listen_event里放入location
            process_alarm_duration(alarm_dic)
            alarm_labels = get_device_dictionary(alarm_dic)
            log_info("forward_msg_to_lcd", f"alarm_labels: {alarm_labels}")

            mute_map = {d['ip']: d['mute'] for d in current_cfg}  # {192.168.2.21: 0->True, ...}

            if current_alarm_count == 0:
                # 无报警，显示时间页面
                if buzzer_on:
                    # print("\n===========================无报警，关闭buzzer===========================\n")
                    for dev in lcd_clients:
                        try:
                            if not dev["active"]:
                                log_debug("forward_msg_to_lcd", f"can't write to the {dev['ip']} with 3 times out")
                                continue

                            if dev['buzzer'] and mute_map.get(dev['ip'], False):
                                with dev["lock"]:
                                    # print(f"start buzzer off: {datetime.now()}")
                                    dev['buzzer'].set_off()
                                    # print(f"end buzzer off: {datetime.now()}")
                                    log_info("forward_msg_to_lcd", f"Turned off buzzer for {dev['ip']}")

                                    dev['fail_count'] = 0
                        except ConnectionError as e:
                            log_error("forward_msg_to_lcd", f"Failed to turn off buzzer: {e}")

                            dev['fail_count'] += 1
                            log_error("forward_msg_to_lcd", f"{dev['ip']} fail to turn off ({dev['fail_count']} times): {e}")
                            if dev['fail_count'] >= 3:
                                dev['active'] = False
                                # dev['lcd'].client.close()
                                log_info("forward_msg_to_lcd", f"{dev['ip']} offline, continue")
                    buzzer_on = False

                # force buzzer off when current_alarm_count == 0 and 10s interval
                for dev in lcd_clients:
                    try:
                        if not dev["active"]:
                            log_debug("forward_msg_to_lcd", f"can't write to the {dev['ip']} with 3 times out")
                            continue

                        if dev['buzzer'] and mute_map.get(dev['ip'], False) and current_time - last_time_update >= 10:
                            with dev["lock"]:
                                # print(f"start buzzer off: {datetime.now()}")
                                dev['buzzer'].set_off()
                                log_info("forward_msg_to_lcd", f"Forced {dev['ip']}'s buzzer off")
                    except Exception as e:
                        log_error("forward_msg_to_lcd", f"Failed to turn off {dev['ip']}'s buzzer: {e}")
                # update time in 10s interval
                if current_time - last_time_update >= 10:
                    for dev in lcd_clients:
                        if not dev["active"]:
                            log_debug("forward_msg_to_lcd", f"can't write to the {dev['ip']} with 3 times out")
                            continue

                        with dev["lock"]:
                            try:
                                # print("====Try to write the switch_page====")
                                dev["lcd"].switch_page(0)
                                # print("====end switch_page====")
                                # print("====Try to write time_page====")
                                # if title != pre_title:
                                #     pre_title = title
                                #     dev["lcd"].set_title(title)
                                dev["lcd"].set_title(title)
                                log_info("forward_msg_to_lcd", f"Sent current Title to LCD at {dev['ip']}")
                                dev["lcd"].set_current_time()
                                log_info("forward_msg_to_lcd", f"Sent current time to LCD at {dev['ip']}")

                                dev['fail_count'] = 0
                            except Exception as e:
                                log_error("forward_msg_to_lcd", f"Time update failed for {dev['ip']}: {e}", exc_info=True)

                                dev['fail_count'] += 1
                                log_error("forward_msg_to_lcd", f"{dev['ip']} fail to turn off ({dev['fail_count']} times): {e}")
                                if dev['fail_count'] >= 3:
                                    dev['active'] = False
                                    # dev['lcd'].client.close()
                                    log_info("forward_msg_to_lcd", f"{dev['ip']} offline, continue")
                    last_time_update = current_time

            # 改变报警的显示逻辑，一页一个设备，添加location
            else:
                # 有报警，显示报警页面
                if not buzzer_on:
                    # print("\n===========================有报警，开启buzzer===========================\n")
                    for dev in lcd_clients:
                        try:
                            if not dev['active']:
                                continue

                            if dev['buzzer'] and mute_map.get(dev['ip'], False):
                                with dev["lock"]:
                                    log_debug("forward_msg_to_lcd", f"Turning on buzzer for {dev['ip']}")
                                    dev['buzzer'].set_on()
                                    log_info("forward_msg_to_lcd", f"Turned on buzzer for {dev['ip']}")

                                    dev['fail_count'] = 0
                        except ConnectionError as e:
                            log_error("forward_msg_to_lcd", f"Failed to turn on buzzer: {e}")

                            dev['fail_count'] += 1
                            log_error("forward_msg_to_lcd", f"{dev['ip']} fail to turn on ({dev['fail_count']} times): {e}")
                            if dev['fail_count'] >= 3:
                                dev['active'] = False
                                # dev['lcd'].client.close()
                                log_info("forward_msg_to_lcd", f"{dev['ip']} offline, continue")
                    buzzer_on = True

                labels_changed = alarm_labels != last_labels
                config = ConfigCache.get_instance().get_config()
                display_time = config['lcd_scrolling_alarm_interval']

                if labels_changed or (current_time - last_display_time >= display_time):
                    num_labels = len(alarm_labels)
                    line1, line2 = "", ""
                    duration1, duration2 = 0, 0

                    # print("nums_labels: ", num_labels)
                    if num_labels == 0:
                        # clear the page
                        for dev in lcd_clients:
                            if not dev['active']:
                                continue

                            with dev["lock"]:
                                try:
                                    dev['lcd'].switch_page(1)
                                    dev['lcd'].write_line(1, " " * 16, LCDDisplayModbus.DISPLAY_RED)
                                    dev['lcd'].write_line(2, " " * 16, LCDDisplayModbus.DISPLAY_RED)
                                    dev['lcd'].switch_page(0)
                                    log_info("forward_msg_to_lcd", f"Cleared alarm page content for {dev['ip']}")

                                    dev['fail_count'] = 0
                                except (ConnectionError, ValueError) as e:
                                    log_error("forward_msg_to_lcd", f"Failed to clear alarm page content for {dev['ip']}: {e}")

                                    dev['fail_count'] += 1
                                    log_error("forward_msg_to_lcd", f"{dev['ip']} fail to turn off ({dev['fail_count']} times): {e}")
                                    if dev['fail_count'] >= 3:
                                        dev['active'] = False
                                        # dev['lcd'].client.close()
                                        log_info("forward_msg_to_lcd", f"{dev['ip']} offline, continue")

                    # 在这一部分进行修改，添加location，一页显示一个device
                    else:
                        if alarm_index >= num_labels:
                            alarm_index = 0
                        j_code = label_to_jcode.get(alarm_labels[alarm_index])
                        log_info("forward_msg_to_lcd", f"j_code is {j_code}")

                        if j_code:
                            device_info = cache.get_device_info(j_code)
                            holder = device_info.get('holder', 'Unknown')
                            event_name = alarm_dic[j_code][0]
                            location = alarm_dic[j_code][1]  # str or None(PB)
                            # location还需要和area对应，将location的坐标mapping到area
                            if location != '' and location is not None:
                                x, y, z = map(float, location.strip("()").split(", "))
                                formatted_location = f"({x:.2f}, {y:.2f}, {z:.2f})"
                                area = location_to_area.get(formatted_location, location)
                            else:
                                area = "locating.."
                            log_info("forward_msg_to_lcd", f"e: {event_name}, l: {location}, a: {area}")

                            if "PB_" in event_name:
                                device_type = "PB"
                            else:
                                device_type = "Tracker"

                            if device_type == "PB":
                                line1 = f"{alarm_index + 1}. {alarm_labels[alarm_index]}"
                                line2 = f" "
                            elif device_type == "Tracker":
                                line1 = f"{alarm_index + 1}. {holder}"
                                line2 = f"{area}"

                        if j_code:
                            duration2 = current_time - alarm_duration.get(j_code, current_time)
                        for dev in lcd_clients:
                            if not dev['active']:
                                continue
                            with dev["lock"]:
                                try:
                                    c1 = get_alarm_color(duration2)
                                    c2 = get_alarm_color(duration2)
                                    log_debug("forward_msg_to_lcd",
                                              f"[display] dev={dev['ip']} dur1={duration1:.1f} → color1={c1}, "
                                              f"dur2={duration2:.1f} → color2={c2}")
                                    send_alarm_message(dev["lcd"], line1, line2, 0, duration2)
                                    dev['fail_count'] = 0
                                except Exception as e:
                                    dev['fail_count'] += 1
                                    log_error("forward_msg_to_lcd",
                                              f"{dev['ip']} fail to write color ({dev['fail_count']} times): {e}")
                                    if dev['fail_count'] >= 3:
                                        dev['active'] = False
                                        log_info("forward_msg_to_lcd", f"{dev['ip']} offline, continue")
                        alarm_index = (alarm_index + 1) % num_labels

                    # elif num_labels == 1:
                    #     line1 = f"1. {alarm_labels[0]}"
                    #     line2 = " " * 16
                    #     j_code = label_to_jcode.get(alarm_labels[0])
                    #     if j_code:
                    #         duration1 = current_time - alarm_duration.get(j_code, current_time)
                    # elif num_labels == 2:
                    #     line1 = f"1. {alarm_labels[0]}"
                    #     line2 = f"2. {alarm_labels[1]}"
                    #     j_code1 = label_to_jcode.get(alarm_labels[0])
                    #     j_code2 = label_to_jcode.get(alarm_labels[1])
                    #     if j_code1:
                    #         duration1 = current_time - alarm_duration.get(j_code1, current_time)
                    #     if j_code2:
                    #         duration2 = current_time - alarm_duration.get(j_code2, current_time)
                    # else:
                    #     if alarm_index >= num_labels:
                    #         alarm_index = 0
                    #     next_index = (alarm_index + 1) % num_labels
                    #     line1 = f"{alarm_index + 1}. {alarm_labels[alarm_index]}"
                    #     line2 = f"{next_index + 1}. {alarm_labels[next_index]}"
                    #     j_code1 = label_to_jcode.get(alarm_labels[alarm_index])
                    #     j_code2 = label_to_jcode.get(alarm_labels[next_index])
                    #     if j_code1:
                    #         duration1 = current_time - alarm_duration.get(j_code1, current_time)
                    #     if j_code2:
                    #         duration2 = current_time - alarm_duration.get(j_code2, current_time)
                    #     alarm_index = (alarm_index + 1) % num_labels
                    #
                    # if line1 or line2:
                    #     for dev in lcd_clients:
                    #         if not dev['active']:
                    #             continue
                    #
                    #         with dev["lock"]:
                    #             try:
                    #                 c1 = get_alarm_color(duration1)
                    #                 c2 = get_alarm_color(duration2)
                    #                 log_debug("forward_msg_to_lcd",
                    #                           f"[display] dev={dev['ip']} dur1={duration1:.1f} → color1={c1}, "
                    #                           f"dur2={duration2:.1f} → color2={c2}")
                    #                 send_alarm_message(dev["lcd"], line1, line2, duration1, duration2)
                    #
                    #                 dev['fail_count'] = 0
                    #             except Exception as e:
                    #                 dev['fail_count'] += 1
                    #                 log_error("forward_msg_to_lcd", f"{dev['ip']} fail to write color ({dev['fail_count']} times): {e}")
                    #                 if dev['fail_count'] >= 3:
                    #                     dev['active'] = False
                    #                     # dev['lcd'].client.close()
                    #                     log_info("forward_msg_to_lcd", f"{dev['ip']} offline, continue")

                    last_labels = alarm_labels.copy()
                    last_display_time = current_time
        except Exception as e:
            log_error("forward_msg_to_lcd", f"Unexpected error in main loop: {e}")

        time.sleep(0.1)


if __name__ == "__main__":
    try:
        if not callable(listen_event.start_mqtt_listener):
            log_error("forward_msg_to_lcd",
                      f"start_mqtt_listener is not callable, got {type(listen_event.start_mqtt_listener)}")
            raise TypeError(f"start_mqtt_listener is not callable, got {type(listen_event.start_mqtt_listener)}")
        ConfigCache.get_instance()
        mqtt_thread = threading.Thread(target=listen_event.start_mqtt_listener, daemon=True)
        mqtt_thread.start()
        send_messages()
    except Exception as e:
        log_error("forward_msg_to_lcd", f"Program failed: {e}")