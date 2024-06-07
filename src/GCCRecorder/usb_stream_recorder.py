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
from abc import ABC, abstractmethod

from src.GCCRecorder.gc_conversion import _get_endianness, PacketData, Player
from src.GCCRecorder.usb_stream_processer import UsbStreamProcesser

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


class UsbStreamRecorder(ABC):

    @abstractmethod
    def record(self):
        pass


class BasicUsbStreamRecorder(UsbStreamRecorder):

    def __init__(self, context, verbose_log, processer: UsbStreamProcesser):
        set_log_verbosity(verbose_log)
        self.context = context
        self.processer = processer

    def record(self):
        player = Player(self.context.player_port)
        items = []
        epoch = None
        logger.info(f"Recording inputs from port n°{self.context.player_port}")
        logger.info(f"Opening output file : {self.context.output_file}")
        with open(self.context.output_file, "w") as fic:
            fic.write(Player.data_format + os.linesep)
            try:
                while True:
                    if self.context.abort_signal.is_set():
                        logger.info("abort record")
                        return
                    with self.processer.q_out_lock:
                        items, self.processer.q_out = self.processer.q_out, []
                    if not items:
                        if self.context.end_packet.is_set():
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
                self.context._handle_exception(exc)
            #logger.info("copy temp data to final file")
            #shutil.copyfile(fic.name, self.context.output_file)

