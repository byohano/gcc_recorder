import mmap
import io
import struct
import time
from threading import Thread, Event, Lock
import queue
from itertools import chain
from pathlib import Path
import logging
import tempfile
import shutil
import os

from gc_conversion import *

SLEEP_TIME = 0.01

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler("core.log")
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] %(message)s')
file_handler.setFormatter(file_formatter)
file_handler.name = "file"
stream_handler = logging.StreamHandler()
stream_formatter = logging.Formatter('%(levelname)s - %(message)s')
stream_handler.setFormatter(stream_formatter)
stream_handler.name = "stream"
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

def set_log_verbosity(verbose_log):
    for hdl in logger.handlers:
        if hdl.name == "file":
            if verbose_log == 2:
                hdl.setLevel(logging.DEBUG)
            elif verbose_log == 1:
                hdl.setLevel(logging.INFO)
            else:
                hdl.setLevel(logging.WARNING)
        elif hdl.name == "stream":
            hdl.setLevel(logging.WARNING)


class App:

    def __init__(self, device_number, bus_number, player_port, output_file, duration):
        self.q_stream, self.q_stream_lock = [], Lock()
        self.q_packet, self.q_packet_lock = [], Lock()
        self.q_input, self.q_input_lock = [], Lock()
        self.end_capture = Event()
        self.end_stream = Event()
        self.end_packet = Event()
        self.abort_signal = Event()
        self.device_number = 7
        self.bus_number = 3
        self.usbmon_file = f"/dev/usbmon{self.bus_number}"
        self.output_file = output_file
        self.duration = duration
        self.player_port = player_port

    def _read_data(self, arr):
        return int("".join(reversed(arr)), 16)

    def _handle_exception(self, exc):
        logger.error(exc)
        self.abort_signal.set()
        raise exc

    def record_data(self):
        player = Player(self.player_port)
        items = []
        epoch = None
        logger.info(f"Recording inputs from port n°{self.player_port}")
        logger.info(f"Opening output file : {self.output_file}")
        with open(self.output_file, "w") as fic:
            fic.write(Player.data_format + os.linesep)
            try:
                while True:
                    if self.abort_signal.is_set():
                        logger.info("abort record")
                        return
                    elif self.q_input:
                        with self.q_input_lock:
                            items, self.q_input = self.q_input, []
                        for elmt in items:
                            logger.info("recording data")
                            if not epoch:
                                epoch = elmt.timestamp
                            elmt.timestamp -= epoch
                            elmt.timestamp = round(elmt.timestamp, 6)
                            logger.info(f"record timestamp {elmt.timestamp}")
                            player.parse_packet(elmt)
                            if not player.is_connected:
                                logger.warning(f"Player n°{player.port} isn't connected, empty data will be written.")
                            fic.write(str(player) + os.linesep)
                        logger.info("pause recording")
                        time.sleep(SLEEP_TIME)
                    elif self.end_packet.is_set():
                        logger.info("no more data, stop record")
                        break
                    else:
                        logger.info("waiting for data")
                        time.sleep(SLEEP_TIME)
            except Exception as exc:
                logger.error("Runtime exception, aborting")
                self._handle_exception(exc)
        logger.error(f"q_packet size : {len(self.q_packet)}")

    def filter_data(self):
        items = []
        time_start = None
        input_truck = []
        try:
            while True:
                if self.abort_signal.is_set():
                    logger.info("abort analysis")
                    return
                elif self.q_packet:
                    logger.info("filter attempt")
                    with self.q_packet_lock:
                        items, self.q_packet = self.q_packet, []
                    for elmt in items:
                        logger.debug(f"{elmt} at {time.time()}")
                        device_number = int(elmt[11])
                        logger.debug(f"device number, {device_number}")
                        if device_number != self.device_number:
                            logger.info("wrong device, discarding")
                            continue
                        urb_type = int(elmt[8])
                        logger.debug(f"urb type, {urb_type}")
                        if urb_type != 43:
                            logger.info("not a data packet, discarding")
                            continue
                        data_length = self._read_data(elmt[36:40])
                        sec, usec = self._read_data(elmt[16:24]), self._read_data(elmt[24:28])
                        packet_time = float(f"{sec}.{str(usec).zfill(6)}")
                        logger.debug(f"packet time, {packet_time}")
                        input_truck.append(PacketData(packet_time, elmt[-(data_length-1):]))
                        logger.info("filter passed")
                        if not time_start:
                            time_start = packet_time
                        elif packet_time - time_start > self.duration:
                            if self.end_capture.is_set():
                                break
                            logger.info("last packet processed, signal end of capture")
                            self.end_capture.set()
                        with self.q_input_lock:
                            self.q_input += input_truck
                        logger.info("input truck sent")
                        input_truck = []
                elif self.end_stream.is_set():
                    logger.info("capture ended, stop filter")
                    self.end_packet.set()
                    break
                else:
                    logger.info("no packet to filter, waiting")
                    time.sleep(SLEEP_TIME)
            logger.debug(f"time start, {time_start}")
        except Exception as exc:
            logger.error("Runtime exception, aborting")
            self._handle_exception(exc)
        logger.error(f"q_input size : {len(self.q_input)}")
        logger.error(f"q_packet size : {len(self.q_packet)}")

    def format_packet(self):
        items = []
        workspace = []
        packet_truck = []
        default_length = 48
        try:
            while True:
                if self.abort_signal.is_set():
                    logger.info("abort packing")
                    return
                elif self.q_stream:
                    logger.info("packing attempt")
                    with self.q_stream_lock:
                        items, self.q_stream = self.q_stream, []
                    workspace += [f'{c:x}'.zfill(2) for elmt in items for c in elmt]
                    i = 0
                    while i < len(workspace):
                        if (len(workspace) - i) < default_length:
                            logger.info("not enough core packet data")
                            break
                        bus_id = self._read_data(workspace[i+12:i+14])
                        logger.debug(f"bus_id, {bus_id}")
                        if bus_id != self.bus_number:  # Hard code
                            logger.error("Wrong bus id at expected location, data stream is incomplete/misaligned! Aborting.")
                            self.abort_signal.set()
                            break
                        packet_length = default_length
                        transfer_type = int(workspace[i+9])
                        logger.debug(f"transfer type, {transfer_type}")
                        if transfer_type == 0:  # ISO request
                            packet_length += 16
                        data_length = self._read_data(workspace[i+36:i+40])
                        logger.debug(f"data length, {data_length}")
                        packet_length += data_length
                        if (len(workspace) - i) < packet_length:
                            logger.info("incomplete packet data, wait")
                            break
                        packet_truck.append(workspace[i:i+packet_length])
                        logger.info("packet made")
                        i += packet_length
                    workspace = workspace[i:]
                    with self.q_packet_lock:
                        self.q_packet += packet_truck
                    packet_truck = []
                    logger.info("packet truck sent")
                elif self.end_capture.is_set():
                    logger.info("capture ended, stop packing")
                    self.end_stream.set()
                    break
                else:
                    logger.info("empty, waiting for packing")
                    time.sleep(SLEEP_TIME)
        except Exception as exc:
            logger.error("Runtime exception, aborting")
            self._handle_exception(exc)
        logger.error(f"q_stream size : {len(self.q_stream)}")
        logger.error(f"q_input size : {len(self.q_input)}")

    def read_stream(self):
        try:
            with io.open(file=self.usbmon_file, mode='rb', closefd=True) as s:
                time_start = time.time()
                logger.info(f"time start, {time_start}")
                try:
                    logger.info("read start")
                    while True:
                        if self.abort_signal.is_set():
                            logger.info("abort read")
                            return
                        elif self.end_capture.is_set():
                            logger.info("capture ended, stop reading")
                            break
                        elif s.peek(1):
                            with self.q_stream_lock:
                                self.q_stream.append(s.read(io.DEFAULT_BUFFER_SIZE))
                        if time.time() - time_start > self.duration:
                            logger.info("duration exceeded, stop capture")
                            self.end_capture.set()
                    logger.info("read end")
                except Exception as exc:
                    logger.error("Runtime exception, aborting")
                    self._handle_exception(exc)
        except PermissionError as perm_exc:
            logger.error("Insufficient permission for reading usbmon character device, aborting.")
            self._handle_exception(perm_exc)
        logger.error(f"q_stream size : {len(self.q_stream)}")

        if not self.abort_signal.is_set():
            print("Capture finished, pending final processing...")

    def main(self, verbose_log=False):
        set_log_verbosity(verbose_log)
        print("Starting capture.")

        read_thread = Thread(target=self.read_stream, name="read_thread")
        packet_thread = Thread(target=self.format_packet, name="packet_thread")
        filter_thread = Thread(target=self.filter_data, name="filter_thread")
        record_thread = Thread(target=self.record_data, name="record_thread")

        read_thread.start()
        packet_thread.start()
        filter_thread.start()
        record_thread.start()

        read_thread.join()
        packet_thread.join()
        filter_thread.join()
        record_thread.join()

        if self.abort_signal.is_set():
            print("Due to an error, the application was interrupted. Please try again.")
        else:
            print(f"Capture file ready! See result in '{self.output_file}'.")

if __name__ == "__main__":
    app = App(7, 3, "record.csv", 1)
    app.main()
