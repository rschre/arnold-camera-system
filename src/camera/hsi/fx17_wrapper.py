# Wrapper for controlling the Specim FX17 camera using the spectralcam module
from spectralcam.specim import FX17
from spectralcam.gentl import GCSystem

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

	def start_acquisition(self):
		"""
		Start image acquisition.
		"""
		if self.camera is not None:
			self.camera.start()

	def stop_acquisition(self):
		"""
		Stop image acquisition.
		"""
		if self.camera is not None:
			self.camera.stop()

	def get_frame(self):
		"""
		Acquire a single frame from the camera.
		Returns the frame data (numpy array or similar).
		"""
		if self.camera is not None:
			return self.camera.get_frame()
		return None

	def disconnect(self):
		"""
		Disconnect and clean up resources.
		"""
		if self.camera is not None:
			self.camera.close()
		if self.interface is not None:
			self.interface.close()
		if self.system is not None:
			self.system.close()
		self.camera = None
		self.interface = None
		self.system = None
		self.connected = False
