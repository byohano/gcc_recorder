import logging
import struct
import time
from abc import ABC, abstractmethod
from threading import Lock

from src.GCCRecorder.gc_conversion import PacketData, _get_endianness
from src.GCCRecorder.usb_stream_reader import UsbStreamReader

SLEEP_TIME = 0.01

logger = logging.getLogger("core.processer")


class UsbStreamProcesser(ABC):

    @abstractmethod
    def process(self):
        pass


class BasicUsbStreamProcesser(UsbStreamProcesser):

    def __init__(self, context, verbose_log, reader: UsbStreamReader):
        self.context = context
        self.reader = reader
        self.q_out, self.q_out_lock = [], Lock()

    def process(self):
        items = b''
        workspace = b''
        input_truck = []
        default_length = 48
        time_start = None
        try:
            while True:
                if self.context.abort_signal.is_set():
                    logger.info("abort packing")
                    return
                with self.reader.q_out_lock:
                    items, self.reader.q_out = bytes(self.reader.q_out), bytearray()
                if not items:
                    if self.context.end_capture.is_set():
                        logger.info("capture ended, stop packing")
                        self.context.end_packet.set()
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
                    if bus_id != self.context.bus_number:  # Hard code
                        logger.error("Wrong bus id at expected location, data stream is incomplete/misaligned! Aborting.")
                        self.context.abort_signal.set()
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
                    if device_number != self.context.device_number:
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
                    if (packet_time - time_start) > self.context.duration:
                        logger.info("duration exceeded, discarding remaining packets")
                        break
                workspace = workspace[i:]
                with self.q_out_lock:
                    self.q_out += input_truck
                logger.info("packet truck sent")
                input_truck = []
        except Exception as exc:
            logger.error("Runtime exception, aborting")
            self.context._handle_exception(exc)

