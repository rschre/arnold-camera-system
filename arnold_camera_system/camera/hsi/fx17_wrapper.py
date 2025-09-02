# Wrapper for controlling the Specim FX17 camera using the spectralcam module
import time
from typing import Any

from spectralcam.gentl import GCSystem
from spectralcam.specim import FX17


class FX17CameraWrapper:
    """
    High-level wrapper for Specim FX17 camera using spectralcam.
    Provides methods to connect, configure, start/stop acquisition, and get frames.
    """

    def __init__(self):
        self.system = None
        self.interface = None
        self.camera = None
        self.connected = False

    def connect(self, auto_configure: bool = True) -> bool:
        """
        Discover and connect to the FX17 camera. Optionally set default configuration.
        Returns True if connected, False otherwise.
        """
        self.system = GCSystem()
        cam, intf = self.system.discover(FX17)
        if cam is not None:
            self.camera = cam
            self.interface = intf
            self.connected = True
            if auto_configure:
                self.set_defaults()
            return True
        return False

    def set_defaults(self, frame_rate: float = 80.0, exposure_time: float = 100.0):
        """
        Set default parameters for the camera.
        """
        if self.camera is not None:
            self.camera.set_defaults(frame_rate=frame_rate, exposure_time=exposure_time)

    def open_stream(self):
        """
        Open a stream for continuous image acquisition. Required to acquire images."
        """
        if self.camera is not None:
            self.camera.open_stream()

    def start_timed_capture(self, duration: int) -> Any:
        """
        Start a timed capture for a specified duration in ms.
        """
        if self.camera is not None:
            self.open_stream()
            self.camera.start_acquire(True)

        time.sleep(duration / 1000.0)

        if self.camera is not None:
            data = self.camera.stop_acquire()
            self.camera.close_stream()
            return data

    def close(self):
        """
        Close the camera and release resources.
        """
        if self.system is not None:
            self.system.close()

        self.camera = None
        self.interface = None
        self.system = None
        self.connected = False
