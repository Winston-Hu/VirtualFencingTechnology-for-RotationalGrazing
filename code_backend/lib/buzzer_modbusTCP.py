from datetime import datetime


class BuzzerModbus:
    def __init__(self, client, slave_id=2):
        self.client = client
        self.slave_id = slave_id
        self.client.unit_id = slave_id

    def close(self):
        if self.client.is_open:
            self.client.close()

    def set_on(self):
        if not self.client.is_open:
            if not self.client.open():
                raise ConnectionError("Failed to reconnect for buzzer ON")
        print(f"---try to turn on the buzzer--- {datetime.now()}")
        if not self.client.write_single_register(4, 1):
            self.client.close()
            print(f"---fail to turn on the buzzer--- {datetime.now()}")
            raise ConnectionError("Failed to turn ON buzzer")

    def set_off(self):
        if not self.client.is_open:
            if not self.client.open():
                raise ConnectionError("Failed to reconnect for buzzer OFF")
        print(f"try to turn off the buzzer {datetime.now()}")
        if not self.client.write_single_register(4, 0):
            self.client.close()
            print(f"---fail to turn off the buzzer--- {datetime.now()}")
            raise ConnectionError("Failed to turn OFF buzzer")