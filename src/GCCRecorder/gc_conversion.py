from typing import List
import struct
import sys

def _get_endianness():
    if sys.byteorder == "little":
        return "<"
    elif sys.byteorder == "big":
        return ">"
    else:
        raise ValueError(f"Not a valid endiannes : {sys.byteorder}")


class PacketData:

    def __init__(self, timestamp: float, data: List[str]):
        self.timestamp: float = timestamp
        self.player_data: List[str] = [data, data[:9], data[9:18], data[18:27], data[27:36]]


class Player:

    data_format: str = "TIMESTAMP,A,B,X,Y,Z,START,R,R_PRESSURE,L,L_PRESSURE,LEFT_STICK_X,LEFT_STICK_Y,C_STICK_X,C_STICK_Y,DPAD_LEFT,DPAD_RIGHT,DPAD_UP,DPAD_DOWN"

    def __str__(self):
        full_data = [
            self.timestamp,
            self.a,self.b,self.x,self.y,self.z,
            self.start,
            self.r,self.r_pressure,self.l,self.l_pressure,
            self.left_stick_x,self.left_stick_y,self.c_stick_x,self.c_stick_y,
            self.dpad_left,self.dpad_right,self.dpad_up,self.dpad_down
        ]
        return ",".join([str(x) for x in full_data])

    def __init__(self, port: int):
        self.port: int = port
        self.is_connected: bool = True
        self.timestamp: float

        self.left_stick_x: int
        self.left_stick_y: int
        self.c_stick_x: int
        self.c_stick_y: int

        self.dpad_left: int
        self.dpad_right: int
        self.dpad_up: int
        self.dpad_down: int

        self.a: int
        self.b: int
        self.x: int
        self.y: int

        self.start: int
        self.z: int
        self.r: int
        self.l: int

        self.r_pressure: int
        self.l_pressure: int

    def parse_packet(self, packet: PacketData):
        self.timestamp = packet.timestamp
        data = struct.unpack(f'{_get_endianness()}BBBBBBBBB', packet.player_data[self.port])
        self.check_connection(data)
        self.set_face_buttons(data)
        self.set_other_buttons(data)
        self.set_dpad(data)
        self.set_left_stick_x(data)
        self.set_left_stick_y(data)
        self.set_c_stick_x(data)
        self.set_c_stick_y(data)
        self.set_l_pressure(data)
        self.set_r_pressure(data)

    def check_connection(self, data: List[str]) -> None:
        #self.is_connected = (data[0][0] == "1")
        self.is_connected = (data[0] > 16)

    def set_left_stick_x(self, data: List[str]) -> None:
        #bval: str = data[3]
        #self.left_stick_x = int(bval, 16)
        self.left_stick_x = data[3]

    def set_left_stick_y(self, data: List[str]) -> None:
        #bval: str = data[4]
        #self.left_stick_y = int(bval, 16)
        self.left_stick_y = data[4]

    def set_c_stick_x(self, data: List[str]) -> None:
        #bval: str = data[5]
        #self.c_stick_x = int(bval, 16)
        self.c_stick_x = data[5]

    def set_c_stick_y(self, data: List[str]) -> None:
        #bval: str = data[6]
        #self.c_stick_y = int(bval, 16)
        self.c_stick_y = data[6]

    def set_dpad(self, data: List[str]) -> None:
        val: str = (int(data[1]) - 16) % 16
        rem: int

        rem = val % 2
        val = (val - rem) / 2
        self.dpad_left = rem
        rem = val % 2
        val = (val - rem) / 2
        self.dpad_right = rem
        rem = val % 2
        val = (val - rem) / 2
        self.dpad_up = rem
        rem = val % 2
        val = (val - rem) / 2
        self.dpad_down = rem

    def set_face_buttons(self, data: List[str]) -> None:
        val: str = data[1] % 16
        rem: int

        rem = val % 2
        val = (val - rem) / 2
        self.a = rem
        rem = val % 2
        val = (val - rem) / 2
        self.b = rem
        rem = val % 2
        val = (val - rem) / 2
        self.x = rem
        rem = val % 2
        val = (val - rem) / 2
        self.y = rem

    def set_other_buttons(self, data: List[str]) -> None:
        val: str = data[2] % 16
        rem: int

        rem = val % 2
        val = (val - rem) / 2
        self.start = rem
        rem = val % 2
        self.z = rem
        rem = val % 2
        self.r = rem
        rem = val % 2
        val = (val - rem) / 2
        self.l = rem

    def set_l_pressure(self, data: List[str]) -> None:
        #bval: str = data[7]
        #self.l_pressure = int(bval, 16)
        self.l_pressure = data[7]

    def set_r_pressure(self, data: List[str]) -> None:
        #bval: str = data[8]
        #self.r_pressure = int(bval, 16)
        self.r_pressure = data[8]

