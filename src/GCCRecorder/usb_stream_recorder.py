import logging
import os
import time
from abc import ABC, abstractmethod

from src.GCCRecorder.gc_conversion import Player
from src.GCCRecorder.usb_stream_processer import UsbStreamProcesser

SLEEP_TIME = 0.01

logger = logging.getLogger("core.recorder")


class UsbStreamRecorder(ABC):

    @abstractmethod
    def record(self):
        pass


class BasicUsbStreamRecorder(UsbStreamRecorder):

    def __init__(self, context, verbose_log, processer: UsbStreamProcesser):
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

