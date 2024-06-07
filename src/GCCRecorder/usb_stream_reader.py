# This file is part of the GC Input Recorder program.
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

import io
import logging
import time
from abc import ABC, abstractmethod
from threading import Lock

SLEEP_TIME = 0.01

logger = logging.getLogger("core.reader")


class UsbStreamReader(ABC):

    @abstractmethod
    def read(self):
        pass


class BasicUsbStreamReader(UsbStreamReader):

    def __init__(self, context, verbose_log):
        self.context = context
        self.q_out, self.q_out_lock = bytearray(), Lock()

    def read(self):
        try:
            with io.open(file=self.context.usbmon_file, mode='rb', closefd=True) as s:
                time_start = time.time()
                logger.debug(f"time start, {time_start}")
                try:
                    logger.info("read start")
                    while True:
                        if self.context.abort_signal.is_set():
                            logger.info("abort read")
                            return
                        elif self.context.end_capture.is_set():
                            logger.info("capture ended, stop reading")
                            break
                        with self.q_out_lock:
                            self.q_out.extend(s.read(io.DEFAULT_BUFFER_SIZE))
                        logger.debug("reading...")
                        if time.time() - time_start > self.context.duration:
                            logger.info("duration exceeded, stop capture")
                            self.context.end_capture.set()
                    logger.info("read end")
                except Exception as exc:
                    logger.error("Runtime exception, aborting")
                    self.context._handle_exception(exc)
        except PermissionError as perm_exc:
            logger.error("Insufficient permission for reading usbmon character device, aborting.")
            self.context._handle_exception(perm_exc)
        if not self.context.abort_signal.is_set():
            print("Capture finished, pending final processing...")

