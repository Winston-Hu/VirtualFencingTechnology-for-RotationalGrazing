import logging
import atexit
import time
from pyModbusTCP.client import ModbusClient
from logging.handlers import RotatingFileHandler

from lib.buzzer_modbusTCP import BuzzerModbus


# use JIG02 LAN / IR302 and relay config
HOST_IR302_TRANS = "192.168.2.25"
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
        filename="gps_data.log",
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

    # state machine
    buzzer_on = False  # default -> not ring
    last_display_time = time.time()
    last_time_update = 0

    while True:
        try:
            current_time = time.time()

            # get_alarm_dictionary() expected payload:{"cow1": (200, 120), "cow2": (230, 90), ...} or {}
            alarm_dic = get_alarm_dictionary()  # get the alarm cows info here
            current_alarm_count = len(alarm_dic)  # count how many cows in alarm
            logging.info(f"(Alarm count: {current_alarm_count})")

            # ------------------------------------------------------------------------------------------------------





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
                            log_error("forward_msg_to_lcd",
                                      f"{dev['ip']} fail to turn off ({dev['fail_count']} times): {e}")
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
                                log_error("forward_msg_to_lcd", f"Time update failed for {dev['ip']}: {e}",
                                          exc_info=True)

                                dev['fail_count'] += 1
                                log_error("forward_msg_to_lcd",
                                          f"{dev['ip']} fail to turn off ({dev['fail_count']} times): {e}")
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
                            log_error("forward_msg_to_lcd",
                                      f"{dev['ip']} fail to turn on ({dev['fail_count']} times): {e}")
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
                                    log_error("forward_msg_to_lcd",
                                              f"Failed to clear alarm page content for {dev['ip']}: {e}")

                                    dev['fail_count'] += 1
                                    log_error("forward_msg_to_lcd",
                                              f"{dev['ip']} fail to turn off ({dev['fail_count']} times): {e}")
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

                    last_labels = alarm_labels.copy()
                    last_display_time = current_time
        except Exception as e:
            log_error("forward_msg_to_lcd", f"Unexpected error in main loop: {e}")

        time.sleep(0.1)


if __name__ == "__main__":
    sendAlarm()
