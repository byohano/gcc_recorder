# This file is part of the GCC Recorder program.
# Copyright (c) 2024 Ohayon Benjamin.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
gc_conversion.py: Carry and convert Gamecube controller byte data.

Methods:
    get_endianness: Get endianness of underlying hardware.

Classes:
    PacketData: Player inputs extracted from USB packets.
    CaptureData: Converts byte data to a human-readable format.
"""

import struct
import sys
from typing import List


def _get_endianness():
    """
    Get endianness of underlying OS.

    This is necessary to orient byte data unpacking operations.

    Returns:
        "<" if hardware is little-endian.
        ">" if hardware is big-endian.
    Raises:
        ValueError if "sys.byteorder" has an unexpected value.
    """
    if sys.byteorder == "little":
        return "<"
    elif sys.byteorder == "big":
        return ">"
    else:
        raise ValueError(f"Not a valid endianness : {sys.byteorder}")


class PacketData:
    """
    Player inputs extracted from USB packets.

    Attributes:
        timestamp: Data timestamp
        player_data: Inputs captured on all ports. 0 = Full data, 1-4 = Data of port 1-4.
    Methods:
        __init__: Constructor, simply set attributes.
    """

    def __init__(self, timestamp: float, data: List[str]):
        """
        Constructor, simply set attributes.

        Parameters:
            timestamp: Data timestamp
            data: Salient packet data, describing player inputs on all ports.
        """
        self.timestamp: float = timestamp
        self.player_data: List[str] = [data, data[:9], data[9:18], data[18:27], data[27:36]]


class CaptureData:
    """
    Converts byte data to a human-readable format.

    Target format is CSV, with a column for timestamp and each possible input. It goes as follows :
    - Buttons (A, B, START, etc...) and DPad : 0 = Neutral, 1 = Pressed
    - Sticks : 0 = Left for X-axis, Down for Y-axis, 255 = Right for X-axis, Up for Y-axis, 128 = Perfect center
    - Digital trigger presses are like buttons : 0 = Neutral, 1 = Pressed
    - Analog trigger presses : 0 = Neutral, 255 = Maximum value (typically impossible without modding the controller)

    Class attributes:
        data_format: Header for output file, describing target CSV format.
    Attributes:
        port: Number of port corresponding to captured data.
        is_connected: Flag indicating whether a controller is connected on the listened port.
        timestamp: Data timestamp.
        a: Formatted value of A button press.
        b: Formatted value of B button press.
        x: Formatted value of X button press.
        y: Formatted value of Y button press.
        z: Formatted value of Z button press.
        start: Formatted value of START button press.
        r: Formatted value of R trigger digital press.
        l: Formatted value of L trigger digital press.
        r_pressure: Formatted value of R trigger analog press.
        l_pressure: Formatted value of L trigger analog press.
        left_stick_x: Formatted value of left stick's horizontal inclination.
        left_stick_y: Formatted value of left stick's vertical inclination.
        c_stick_x: Formatted value of C-Stick's horizontal inclination.
        c_stick_y: Formatted value of C-Stick's vertical inclination.
        dpad_left: Formatted value of DPad left press.
        dpad_right: Formatted value of DPad right press.
        dpad_up: Formatted value of DPad up press.
        dpad_down: Formatted value of DPad down press.
    Methods:
        __str__: Override to easily summarize attributes into target format.
        __init__: Constructor, define all attributes.
        parse_packet: Parse a PacketData object to set all attributes according to its data.
        check_connection: Set attribute flag according to connectivity status of listened port.
        set_left_stick_x: Parse X-axis data for left stick orientation.
        set_left_stick_y: Parse Y-axis data for left stick orientation.
        set_c_stick_x: Parse X-axis data for C-stick orientation.
        set_c_stick_y: Parse Y-axis data for C-stick orientation.
        set_dpad: Parse DPad data.
        set_face_buttons: Parse face buttons data (A, B, X, Y).
        set_other_buttons: Parse other buttons data (Start, Z, R, L).
        set_l_pressure: Parse analog input on L trigger.
        set_r_pressure: Parse analog input on R trigger.
    """
    data_format: str = "TIMESTAMP,A,B,X,Y,Z,START,R,R_PRESSURE,L,L_PRESSURE,LEFT_STICK_X,LEFT_STICK_Y,C_STICK_X,C_STICK_Y,DPAD_LEFT,DPAD_RIGHT,DPAD_UP,DPAD_DOWN"

    def __str__(self):
        """
        Override to easily summarize attributes into target format.

        Returns:
            CSV string of player inputs ordered in target format
        """
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
        """
        Constructor, define all attributes.

        Arguments:
            port: Number of original port through which other inputs were captured.
        """
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
        """
        Parse a PacketData object to set all attributes according to its data.

        Arguments:
            packet: PacketData object to parse.
        """
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
        """
        Set attribute flag according to connectivity status of listened port.

        Found in 1st byte of a port data section :
        - 04 (hex) / 04 (dec) : No controller detected
        - 14 (hex) / 20 (dec) : Controller detected

        Arguments:
            data: Full input data from a port as bytes.
        """
        self.is_connected = (data[0] > 16)

    def set_left_stick_x(self, data: List[str]) -> None:
        """
        Parse X-axis data for left stick orientation.

        Found with raw value of the 4th byte of a port data section.

        Arguments:
            data: Full input data from a port as bytes.
        """
        self.left_stick_x = data[3]

    def set_left_stick_y(self, data: List[str]) -> None:
        """
        Parse Y-axis data for left stick orientation.

        Found with raw value of the 5th byte of a port data section.

        Arguments:
            data: Full input data from a port as bytes.
        """
        self.left_stick_y = data[4]

    def set_c_stick_x(self, data: List[str]) -> None:
        """
        Parse X-axis data for C-stick orientation.

        Found with raw value of the 6th byte of a port data section.

        Arguments:
            data: Full input data from a port as bytes.
        """
        self.c_stick_x = data[5]

    def set_c_stick_y(self, data: List[str]) -> None:
        """
        Set attribute flag according to connectivity status of listened port.

        Found with raw value of the 7th byte of a port data section.

        Arguments:
            data: Full input data from a port as bytes.
        """
        self.c_stick_y = data[6]

    def set_dpad(self, data: List[str]) -> None:
        """
        Parse DPad data.

        Found with raw value of the left digit of the 2nd byte of a port data section.
        Its value is the sum of each individual input's code value :
        - DPad left = 1
        - DPad right = 2
        - DPad down = 4
        - DPad up = 8

        Arguments:
            data: Full input data from a port as bytes.
        """
        val: int = data[1] // 16  # Floor division operator

        self.dpad_left = val % 2
        val //= 2
        self.dpad_right = val % 2
        val //= 2
        self.dpad_down = val % 2
        val //= 2
        self.dpad_up = val % 2

    def set_face_buttons(self, data: List[str]) -> None:
        """
        Parse face buttons data (A, B, X, Y).

        Found with raw value of the right digit of the 2nd byte of a port data section.
        Its value is the sum of each individual input's code value :
        - A = 1
        - B = 2
        - X = 4
        - Y = 8

        Arguments:
            data: Full input data from a port as bytes.
        """
        val: int = data[1] % 16

        self.a = val % 2
        val //= 2
        self.b = val % 2
        val //= 2
        self.x = val % 2
        val //= 2
        self.y = val % 2

    def set_other_buttons(self, data: List[str]) -> None:
        """
        Parse other buttons data (Start, Z, R, L).

        Found with raw value of the 3rd byte of a port data section.
        Its value is the sum of each individual input's code value :
        - Start = 1
        - Z = 2
        - R = 4
        - L = 8

        Arguments:
            data: Full input data from a port as bytes.
        """
        val: int = data[2] % 16

        self.start = val % 2
        val //= 2
        self.z = val % 2
        val //= 2
        self.r = val % 2
        val //= 2
        self.l = val % 2

    def set_l_pressure(self, data: List[str]) -> None:
        """
        Parse analog input on L trigger.

        Found with raw value of the 8th byte of a port data section.

        Arguments:
            data: Full input data from a port as bytes.
        """
        self.l_pressure = data[7]

    def set_r_pressure(self, data: List[str]) -> None:
        """
        Parse analog input on R trigger.

        Found with raw value of the 9th byte of a port data section.

        Arguments:
            data: Full input data from a port as bytes.
        """
        self.r_pressure = data[8]

