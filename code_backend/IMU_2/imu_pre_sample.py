import time
import imu
from machine import I2C, Pin

# === 初始化 IMU ===
bus = I2C(1, scl=Pin(15), sda=Pin(14))
sensor = imu.IMU(bus)

# === 手势配置 ===
gesture_names = ["drink", "sleep", "forward", "left", "right", "fall"]
gesture_count = len(gesture_names)
samples_per_gesture = 25
sample_rate_hz = 20
sample_interval = 1 / sample_rate_hz
time_steps = 20  # 1 秒采样

# === 输出 CSV 表头（6通道 × 20步 + label）===
header = [f"{sensor}_{i}" for i in range(time_steps) for sensor in ['ax', 'ay', 'az', 'gx', 'gy', 'gz']]
print(",".join(header + ["label"]))

# === 循环采集手势 ===
while True:
    try:
        # 打印手势编号对照表
        print("\n请选择要采集的手势编号：")
        for idx, name in enumerate(gesture_names):
            print(f"{idx}: {name}")

        # 用户输入手势编号
        gesture_id = int(input("请输入准备做的手势编号（或输入 -1 退出）：").strip())
        if gesture_id == -1:
            print("采集结束。")
            break
        if gesture_id < 0 or gesture_id >= gesture_count:
            print("无效编号，请重新输入。")
            continue

        gesture_name = gesture_names[gesture_id]
        print(f"\n 开始采集手势 '{gesture_name}'（编号 {gesture_id}），共 {samples_per_gesture} 次")

        for sample_num in range(samples_per_gesture):
            input()

            sample = []
            for _ in range(time_steps):
                ax, ay, az = sensor.accel()
                gx, gy, gz = sensor.gyro()
                sample.extend([ax, ay, az, gx, gy, gz])
                time.sleep(sample_interval)

            flat = [f"{v:.4f}" for v in sample]
            csv_line = ",".join(flat + [str(gesture_id)])
            print(csv_line)

        print(f"\n 手势 '{gesture_name}' 采集完成！")

    except Exception as e:
        print("出错了：", e)
