import time
from ubluepy import Service, Characteristic, UUID, Peripheral, constants
from machine import Pin, I2C
import imu
from time import sleep_ms

# 初始化 I2C
bus = I2C(1, scl=Pin(15), sda=Pin(14))
imu = imu.IMU(bus)

# 全局状态机，跟踪当前发送的传感器和轴
current_sensor = 0  # 0: accel, 1: gyro, 2: magnet
current_axis = 0    # 0: x, 1: y, 2: z

# 获取当前轴的数据
def get_imu():
    global current_sensor, current_axis
    try:
        if current_sensor == 0:
            data = imu.accel()
            prefix = 'a'  # accel
        elif current_sensor == 1:
            data = imu.gyro()
            prefix = 'g'  # gyro
        elif current_sensor == 2:
            data = imu.magnet()
            prefix = 'm'  # magnet
        else:
            return "error"

        # 获取当前轴值，乘以 1000 转为整数
        value = int(data[current_axis] * 1000)
        # 格式化为标志位+值，例如 "ax-324"
        data_str = f"{prefix}{['x', 'y', 'z'][current_axis]}{value:+05d}"
        
        # 更新状态
        if current_axis == 2:  # z 轴发送完
            current_axis = 0    # 重置到 x 轴
            current_sensor = (current_sensor + 1) % 3  # 切换到下一传感器
        else:
            current_axis += 1  # 切换到下一轴
        return data_str
    except Exception as e:
        print(f"IMU error: {e}")
        return "error"

def event_handler(id, handle, data):
    global periph
    global custom_read_char
    global notif_enabled
    
    # 1) GAP 连接事件
    if id == constants.EVT_GAP_CONNECTED:
        pass
    
    # 2) GAP 断开事件
    elif id == constants.EVT_GAP_DISCONNECTED:
        periph.advertise(device_name="Z5511644")
    
    # 3) GATT 写事件
    elif id == constants.EVT_GATTS_WRITE:
        if handle == 16:  # 写特征
            print(data)
            if notif_enabled and data == b'1':
                imu_data = get_imu()
                print(f"IMU data: {imu_data}")
                b_msg = imu_data.encode()
                try:
                    custom_read_char.write(b_msg)
                except OSError as e:
                    print(f"Write error: {e}")
        elif handle == 19:  # CCCD
            if int(data[0]) == 1:
                notif_enabled = True
                print("Notifications enabled")
            else:
                notif_enabled = False
                print("Notifications disabled")

notif_enabled = False

# 定义 UUID 和服务
custom_svc_uuid = UUID("4A981234-1CC4-E7C1-C757-F1267DD021E8")
custom_wrt_char_uuid = UUID("4A981235-1CC4-E7C1-C757-F1267DD021E8")
custom_read_char_uuid = UUID("4A981236-1CC4-E7C1-C757-F1267DD021E8")

custom_svc = Service(custom_svc_uuid)
custom_wrt_char = Characteristic(custom_wrt_char_uuid, props=Characteristic.PROP_WRITE)
custom_read_char = Characteristic(custom_read_char_uuid, props=Characteristic.PROP_READ | Characteristic.PROP_NOTIFY, attrs=Characteristic.ATTR_CCCD)

custom_svc.addCharacteristic(custom_wrt_char)
custom_svc.addCharacteristic(custom_read_char)

periph = Peripheral()
periph.addService(custom_svc)

periph.setConnectionHandler(event_handler)
periph.advertise(device_name="Z5511644")

# 主循环
while True:
    if notif_enabled:
        imu_data = get_imu()
        b_msg = imu_data.encode()
        try:
            custom_read_char.write(b_msg)
        except OSError as e:
            print(f"Write error: {e}")
    sleep_ms(50)  # 每 50ms 发送一次