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

from src.GCCRecorder.usb_stream_reader import BasicUsbStreamReader
from src.GCCRecorder.usb_stream_processer import BasicUsbStreamProcesser
from src.GCCRecorder.usb_stream_recorder import BasicUsbStreamRecorder

SLEEP_TIME = 0.01

logger = logging.getLogger("core")
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
        self.end_capture = Event()
        self.end_packet = Event()
        self.abort_signal = Event()
        self.device_number = device_number
        self.bus_number = bus_number
        self.usbmon_file = f"/dev/usbmon{self.bus_number}"
        self.output_file = output_file
        self.duration = duration
        self.player_port = player_port

    def _handle_exception(self, exc):
        logger.error(exc)
        self.abort_signal.set()
        raise exc

    def main(self, verbose_log=False):
        set_log_verbosity(verbose_log)
        print("Starting capture.")

        reader = BasicUsbStreamReader(self, verbose_log)
        processer = BasicUsbStreamProcesser(self, verbose_log, reader)
        recorder = BasicUsbStreamRecorder(self, verbose_log, processer)

        read_thread = Thread(target=reader.read, name="read_thread")
        packet_thread = Thread(target=processer.process, name="process_thread")
        record_thread = Thread(target=recorder.record, name="record_thread")

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
