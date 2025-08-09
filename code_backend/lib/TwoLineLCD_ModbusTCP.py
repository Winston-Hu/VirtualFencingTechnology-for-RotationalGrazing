from datetime import datetime

class LCDDisplayModbus:
    DISPLAY_RED = 1
    DISPLAY_GREEN = 2
    DISPLAY_YELLOW = 3

    def __init__(self, client, slave_id=1):
        self.client = client
        self.slave_id = slave_id
        self.client.unit_id = slave_id

    def close(self):
        if self.client.is_open:
            self.client.close()

    def switch_page(self, page):
        if page not in [0, 1]:
            raise ValueError("Page must be 0 or 1")
        if not self.client.is_open:
            if not self.client.open():
                raise ConnectionError("Failed to reconnect for switch page")
        # if not self.client.write_single_register(5, page):
        #     self.client.close()
        #     raise ConnectionError("Failed to switch page")
        try:
            ok = self.client.write_single_register(5, page)
            if not ok:
                # 读取库内部记录的错误/异常信息
                err_txt = self.client.last_error_as_txt  # 如 "connection timed out"
                exc_txt = self.client.last_except_as_txt  # 如 "ILLEGAL DATA ADDRESS"
                detail = self.client.last_except_as_full_txt  # 更长的 Modbus 解释
                raise ConnectionError(
                    f"Modbus write_single_register(addr=5, value={page}) failed: "
                    f"last_error={err_txt}, last_except={exc_txt}, detail={detail}"
                )
        except Exception as e:
            # 捕获 write_single_register 自己抛出的异常（例如参数越界）
            raise ConnectionError(
                f"Exception while switching page to {page}: {e}"
            ) from e

    def set_current_time(self):
        if not self.client.is_open:
            if not self.client.open():
                raise ConnectionError("Failed to reconnect for set time")
        now = datetime.now()
        values = [now.year, now.month, now.day, now.hour, now.minute]
        if not self.client.write_multiple_registers(0, values):
            self.client.close()
            raise ConnectionError("Failed to write current time")

    def write_line(self, line_num, text, color):
        if line_num not in [1, 2]:
            raise ValueError("line_num must be 1 or 2")
        if not (1 <= len(text) <= 16):
            raise ValueError("Text must be 1 to 16 characters long")

        text = text.ljust(16)
        registers = []
        for i in range(0, 16, 2):
            high = ord(text[i])
            low = ord(text[i + 1])
            value = (high << 8) + low
            registers.append(value)

        start_register = 6 if line_num == 1 else 14
        color_register = 48 if line_num == 1 else 49

        if not self.client.is_open:
            if not self.client.open():
                raise ConnectionError("Failed to reconnect for write line")
        if not self.client.write_multiple_registers(start_register, registers):
            self.client.close()
            raise ConnectionError(f"Failed to write content for line {line_num}")
        if not self.client.write_single_register(color_register, color):
            self.client.close()
            raise ConnectionError(f"Failed to write color for line {line_num}")

    def set_title(self, title):
        text = title.ljust(16)
        registers = []
        for i in range(0, 16, 2):
            high = ord(text[i])
            low = ord(text[i+1])
            value = (high << 8) + low
            registers.append(value)
        start_register = 24

        if not self.client.is_open:
            if not self.client.open():
                raise ConnectionError("Failed to reconnect for set title")
        if not self.client.write_multiple_registers(start_register, registers):
            self.client.close()
            raise ConnectionError(f"Failed to write content for title")
        # always assuming color register at 51, and color to be yellow
        if not self.client.write_single_register(50, 2):
            self.client.close()
            raise ConnectionError(f"Failed to write color for title")

