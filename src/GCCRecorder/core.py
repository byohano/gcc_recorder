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

from src.GCCRecorder.gc_conversion import _get_endianness, PacketData, Player

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
        self.q_stream, self.q_stream_lock = bytearray(), Lock()
        self.q_input, self.q_input_lock = [], Lock()
        self.end_capture = Event()
        self.end_packet = Event()
        self.abort_signal = Event()
        self.device_number = 7
        self.bus_number = 3
        self.usbmon_file = f"/dev/usbmon{self.bus_number}"
        self.output_file = output_file
        self.duration = duration
        self.player_port = player_port

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
                    with self.q_input_lock:
                        items, self.q_input = self.q_input, []
                    if not items:
                        if self.end_packet.is_set():
                            logger.info("no more data, stop record")
                            break
                        else:
                            logger.info("waiting for data")
                            time.sleep(SLEEP_TIME)
                            continue
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
            except Exception as exc:
                logger.error("Runtime exception, aborting")
                self._handle_exception(exc)
            #logger.info("copy temp data to final file")
            #shutil.copyfile(fic.name, self.output_file)


    def format_packet(self):
        items = b''
        workspace = b''
        input_truck = []
        default_length = 48
        time_start = None
        try:
            while True:
                if self.abort_signal.is_set():
                    logger.info("abort packing")
                    return
                with self.q_stream_lock:
                    items, self.q_stream = bytes(self.q_stream), bytearray()
                if not items:
                    if self.end_capture.is_set():
                        logger.info("capture ended, stop packing")
                        self.end_packet.set()
                        break
                    else:
                        logger.info("empty, waiting for packing")
                        time.sleep(SLEEP_TIME)
                        continue
                logger.info("packing attempt")
                #logger.debug(f"items, {items}")
                workspace += items
                i = 0
                while i < len(workspace):
                    #logger.debug(f"workspace, {workspace[:100]}")
                    if (len(workspace) - i) < default_length:
                        logger.info("not enough core packet data")
                        break
                    binary_data = struct.unpack(f'{_get_endianness()}QBBBBHBBQLLLLQ', workspace[i:i+default_length])
                    logger.info(f"binary data, {binary_data}")
                    bus_id = binary_data[5]
                    logger.debug(f"bus_id, {bus_id}")
                    if bus_id != self.bus_number:  # Hard code
                        logger.error("Wrong bus id at expected location, data stream is incomplete/misaligned! Aborting.")
                        self.abort_signal.set()
                        break
                    packet_length = default_length
                    transfer_type = binary_data[2]
                    logger.debug(f"transfer type, {transfer_type}")
                    if transfer_type == 0:  # ISO request
                        packet_length += 16
                    data_length = binary_data[12]
                    logger.debug(f"data length, {data_length}")
                    if data_length == 0:
                        logger.info("not a data packet, skipping")
                        i += packet_length
                        continue
                    packet_length += data_length
                    if (len(workspace) - i) < packet_length:
                        logger.info("incomplete packet data, wait")
                        break
                    device_number = binary_data[4]
                    logger.debug(f"device number, {device_number}")
                    if device_number != self.device_number:
                        logger.info("wrong device, discarding")
                        i += packet_length
                        continue
                    sec, usec = binary_data[8], binary_data[9]
                    packet_time = float(f"{sec}.{str(usec).zfill(6)}")
                    logger.debug(f"packet time, {packet_time}")
                    input_truck.append(PacketData(packet_time, workspace[i+packet_length-data_length+1:i+packet_length]))
                    i += packet_length
                    logger.info("packet made")
                    if not time_start:
                        time_start = packet_time
                    if (packet_time - time_start) > self.duration:
                        logger.info("duration exceeded, discarding remaining packets")
                        break
                workspace = workspace[i:]
                with self.q_input_lock:
                    self.q_input += input_truck
                logger.info("packet truck sent")
                input_truck = []
        except Exception as exc:
            logger.error("Runtime exception, aborting")
            self._handle_exception(exc)

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
                        with self.q_stream_lock:
                            self.q_stream.extend(s.read(io.DEFAULT_BUFFER_SIZE))
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
        if not self.abort_signal.is_set():
            print("Capture finished, pending final processing...")

    def main(self, verbose_log=False):
        set_log_verbosity(verbose_log)
        print("Starting capture.")

        read_thread = Thread(target=self.read_stream, name="read_thread")
        packet_thread = Thread(target=self.format_packet, name="packet_thread")
        record_thread = Thread(target=self.record_data, name="record_thread")

        read_thread.start()
        packet_thread.start()
        record_thread.start()

        read_thread.join()
        packet_thread.join()
        record_thread.join()

        if self.abort_signal.is_set():
            print("Due to an error, the application was interrupted. Please try again.")
        else:
            print(f"Capture file ready! See result in '{self.output_file}'.")

if __name__ == "__main__":
    app = App(7, 3, "record.csv", 1)
    app.main()
