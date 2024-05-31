"""
core.py: Performs high-level actions according to user input.

In particular, multi-threading is set up and ran here.

Methods:
    set_log_verbosity: Define log verbosity from command-line flags.

Classes:
    App: Manage multi-threaded capture of target USB data stream.

"""

import logging
from threading import Event, Thread

from src.GCCRecorder.usb_stream_processer import BasicUsbStreamProcesser
from src.GCCRecorder.usb_stream_reader import BasicUsbStreamReader
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
    """
    Define log verbosity from command-line flags.

    Arguments:
        verbose_log: How verbose the logs should be (0 = minimum, 1 = somewhat, 2 = very).
    """
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
    """
    Manage multi-threaded capture of target USB data stream.

    Firstly, global contextual data is set up here. That includes user input, as well as Event flags that will be used for thread synchronization.
    Then, thread routines are imported from relevant modules, and started in "main" method.
    Each thread is named to help investigate logs.

    Attributes:
        end_capture: Event flag used to synchronize read and process threads.
        end_packet: Event flag used to synchronize process and record threads.
        abort_signal: Event flag used to urgently abort all threads.
        device_number: Number of device whose packets should be captured.
        bus_number: Number of USB bus where target device can be found.
        usbmon_file: Name of usbmon pipe to listen to, derived from bus number.
        output_file: Output file name, where record thread writes final data.
        duration: Duration of capture.
        player_port: Adapter port to listen to
    Methods:
        __init__: Constructor, simply set attributes.
        _handle_exception: Generic actions performed in case of unexpected error in a thread.
        main: Main loop of the application.
    """
    def __init__(self, device_number, bus_number, player_port, output_file, duration):
        """
        Constructor, simply set attributes.

        All parameters are expected to be user input.

        Parameters:
            device_number: Number of device whose packets should be captured.
            bus_number: Number of USB bus where target device can be found.
            player_port: Adapter port to listen to
            output_file: Output file name, where record thread writes final data.
            duration: Duration of capture.
        """
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
        """
        Generic actions performed in case of unexpected error in a thread.

        Typically, we want to log the exact error class and message, as well as tell all threads to stop immediately.

        Arguments:
            exc: Caught exception.
        """
        logger.error(exc)
        self.abort_signal.set()
        raise exc

    def main(self, verbose_log=False):
        """
        Main loop of the application.

        Instances of "UsbStreamReader", "UsbStreamProcesser", and "UsbStreamRecorder" are instantiated here.
        By definition of these classes, the methods to start threads are standardized.

        Arguments:
            verbose_log: How verbose the logs should be (0 = minimum, 1 = somewhat, 2 = very).
        """
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
