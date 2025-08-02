"""
  a_x,a_y,a_z,g_x,g_y,g_z,m_x,m_y,m_z,class_name
"""

import asyncio
import csv
import os
import time
from datetime import datetime

from bleak import BleakClient, BleakError


DEVICE_ADDRESS      = "E5796C3F-1C80-8E92-A222-0EEF42F6ED28"
CUSTOM_SVC_UUID     = "4A981234-1CC4-E7C1-C757-F1267DD021E8"
CUSTOM_WRT_CHAR_UUID = "4A981235-1CC4-E7C1-C757-F1267DD021E8"
CUSTOM_RD_CHAR_UUID  = "4A981236-1CC4-E7C1-C757-F1267DD021E8"

SAMPLES_PER_CLASS   = 100
TRIGGER_INTERVAL_S  = 0.5
TIMEOUT_S = 4.0

BASE_DIR = os.path.dirname(__file__)
CSV_FILE = os.path.join(BASE_DIR, "dataset/imu_data.csv")
CSV_HEADER = [
    "a_x", "a_y", "a_z",
    "g_x", "g_y", "g_z",
    "m_x", "m_y", "m_z",
    "class_name",
]


def init_csv() -> None:
    need_header = (not os.path.exists(CSV_FILE)) or os.path.getsize(CSV_FILE) == 0
    if need_header:
        with open(CSV_FILE, "w", newline="") as f:
            csv.writer(f).writerow(CSV_HEADER)
        print(f"已创建 CSV 并写入表头: {CSV_FILE}")
    else:
        print(f"将追加写入已有文件: {CSV_FILE}")


def append_row(row) -> None:
    with open(CSV_FILE, "a", newline="") as f:
        csv.writer(f).writerow(row)


def parse_notification(raw: str):
    """
    sensor ∈ {'a','g','m'}, axis ∈ {'x','y','z'}
    """
    if len(raw) < 4:
        return None
    sensor, axis, value_txt = raw[0], raw[1], raw[2:]
    try:
        value = int(value_txt)
    except ValueError:
        return None
    return sensor, axis, value


async def sample_once(class_name: str):
    imu_buf  = [None] * 9
    saved    = 0
    last_update_time = time.time()

    def notification_cb(_: int, data: bytearray):
        nonlocal imu_buf, saved, last_update_time
        text = data.decode(errors="ignore").strip()
        parsed = parse_notification(text)
        if parsed is None:
            return

        sensor, axis, value = parsed
        idx_base = {"a": 0, "g": 3, "m": 6}.get(sensor)
        idx_axis = {"x": 0, "y": 1, "z": 2}.get(axis)
        if idx_base is None or idx_axis is None:
            return

        imu_buf[idx_base + idx_axis] = value
        last_update_time = time.time()

        if None not in imu_buf:
            append_row(imu_buf + [class_name])
            saved += 1
            print(f"已写入第 {saved:03d} 行: {imu_buf}")
            imu_buf = [None] * 9
            last_update_time = time.time()

    print(f"尝试连接 {DEVICE_ADDRESS} …")
    try:
        async with BleakClient(DEVICE_ADDRESS) as client:
            if not client.is_connected:
                raise BleakError("连接失败")

            print("已连接！开始采集 … (Ctrl+C 结束)")
            await client.start_notify(CUSTOM_RD_CHAR_UUID, notification_cb)

            try:
                while True:
                    await client.write_gatt_char(CUSTOM_WRT_CHAR_UUID, b"1")
                    await asyncio.sleep(TRIGGER_INTERVAL_S)

                    # 检查是否超时
                    if time.time() - last_update_time > TIMEOUT_S:
                        print(f"\n警告：超过 {TIMEOUT_S} 秒未收到完整样本，丢弃不完整数据并重置。")
                        imu_buf = [None] * 9
                        last_update_time = time.time()

                    if SAMPLES_PER_CLASS and saved >= SAMPLES_PER_CLASS:
                        print(f"达到预设数量 {SAMPLES_PER_CLASS}，自动结束采集。")
                        break
            except KeyboardInterrupt:
                print("手动终止采集。")

            await client.stop_notify(CUSTOM_RD_CHAR_UUID)
            print(f"本次共采集到 {saved} 行。")
    except Exception as e:
        print(f"采集过程中发生错误: {e}")


def main():
    class_name = input("Enter class name (e.g., 'stable'): ").strip()
    if not class_name:
        print("未输入 class name，退出。")
        return

    init_csv()
    asyncio.run(sample_once(class_name))


if __name__ == "__main__":
    print(f"IMU 采集脚本启动  {datetime.now():%Y-%m-%d %H:%M:%S}")
    main()
