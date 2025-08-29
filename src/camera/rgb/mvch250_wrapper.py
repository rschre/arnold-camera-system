import logging
import threading
import traceback
from typing import Any, Callable, Optional

import numpy as np
from CameraParams_header import MV_TRIGGER_MODE_OFF
from CamOperation_class import CameraOperation
from MvCameraControl_class import (
    MV_CC_DEVICE_INFO,
    MV_CC_DEVICE_INFO_LIST,
    MV_FRAME_OUT,
    MV_GIGE_DEVICE,
    MVCC_ENUMVALUE,
    MVCC_FLOATVALUE,
    MVCC_INTVALUE,
    POINTER,
    MvCamera,
    byref,
    c_bool,
    c_ubyte,
    cast,
    cdll,
    memset,
    sizeof,
)
from MvErrorDefine_const import MV_E_CALLORDER, MV_OK

from camera.rgb.mvch250_param_types import MV_CH250_PARAM_TYPE
from camera.rgb.mvch250_utilities import decoding_char, list_devices, to_hex_str

logger = logging.getLogger(__name__)


class MVCH250CameraWrapper:
    """
    Single-class implementation for Hikrobot MVS camera control.
    """

    def __init__(
        self,
        width: int = 5120,
        height: int = 5120,
        frame_callback: Optional[Callable[[np.ndarray, Any], None]] = None,
    ):
        self.width = int(width)
        self.height = int(height)

        self._init_mvs_sdk()

        self.obj_cam: MvCamera = MvCamera()
        self.st_device_list: MV_CC_DEVICE_INFO_LIST = self._get_device_info_list()
        self.n_connect_num = self._get_camera_index()
        self.mv_handler: Optional[CameraOperation] = self._get_mv_handler()

        self._is_open: bool = False
        self._is_grabbing: bool = False
        self._last_frame: Optional[np.ndarray] = None
        self._last_timestamp: Optional[float] = None
        self.st_frame_info: MV_FRAME_OUT = MV_FRAME_OUT()

        self._thread_handle: Optional[threading.Thread] = None
        self._buffer_lock: threading.Lock = threading.Lock()

        self._frame_callback = frame_callback

    def _init_mvs_sdk(self):
        try:
            MvCamera.MV_CC_Initialize()
        except Exception:
            logger.error(
                f"Failed to initialize MVS SDK: {traceback.format_exc()}. Make sure it is installed and if it's not located at C:/Program Files (x86)/Common Files/MVS/Runtime/Win64_x64 that you manually add it to the PATH variable"
            )
            raise

    def _get_device_info_list(self) -> MV_CC_DEVICE_INFO_LIST:
        device_info_list = MV_CC_DEVICE_INFO_LIST()
        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE, device_info_list)
        if ret != MV_OK:
            logger.error(f"Failed to enumerate devices: {to_hex_str(ret)}")
            raise RuntimeError("Failed to enumerate devices")
        return device_info_list

    def _get_camera_index(self) -> int:
        device_list = list_devices(self.st_device_list)
        camera_index = int([d[1] for d in device_list if "MV-CH250" in d][0])

        if camera_index is None:
            raise RuntimeError("No camera found")

        return camera_index

    def _get_mv_handler(self) -> CameraOperation:
        self.mv_handler = CameraOperation(
            self.obj_cam, self.st_device_list, self.n_connect_num
        )
        return self.mv_handler

    def open(self) -> None:
        """Open the connection to the MV-CH250 camera."""

        nConnectionNum = int(self.n_connect_num)
        stDeviceList = cast(
            self.st_device_list.pDeviceInfo[int(nConnectionNum)],
            POINTER(MV_CC_DEVICE_INFO),
        ).contents

        ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
        if ret != MV_OK:
            self.obj_cam.MV_CC_DestroyHandle()
            raise RuntimeError(
                f"Unable to open create device handle, err_num: {to_hex_str(ret)}"
            )

        ret = self.obj_cam.MV_CC_OpenDevice()
        if ret != MV_OK:
            self.obj_cam.MV_CC_DestroyHandle()
            raise RuntimeError(f"Unable to open device, err_num: {to_hex_str(ret)}")
        self._is_open = True

        # Detect optimal network packet size
        if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
            nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
            if int(nPacketSize) > 0:
                ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
                if ret != 0:
                    logger.warning("warning: set packet size fail! ret[0x%x]" % ret)
            else:
                logger.warning("warning: set packet size fail! ret[0x%x]" % nPacketSize)

        stBool = c_bool(False)
        ret = self.obj_cam.MV_CC_GetBoolValue("AcquisitionFrameRateEnable", stBool)
        if ret != 0:
            logger.warning(f"get acquisition frame rate enable fail! {to_hex_str(ret)}")

        # Set trigger mode as off
        ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
        if ret != 0:
            logger.warning(f"set trigger mode fail! {to_hex_str(ret)}")

    def close(self) -> None:
        if self.obj_cam is None:
            raise RuntimeError("Camera handler is not initialized")

        self._is_grabbing = False
        if self._thread_handle is not None:
            self._thread_handle.join(timeout=2)
            self._thread_handle = None

        ret = self.obj_cam.MV_CC_CloseDevice()

        if ret != MV_OK:
            raise RuntimeError(f"Unable to close device, err_num: {to_hex_str(ret)}")
        else:
            self._is_open = False

    def get_parameter(self, name: str) -> Any:
        if self._is_open is False:
            raise RuntimeError("Camera is not open")

        param_type = MV_CH250_PARAM_TYPE.get(name)
        if param_type is None:
            raise ValueError(f"Unknown parameter name: {name}")

        match param_type:
            case "float":
                stFloatParam = MVCC_FLOATVALUE()
                memset(byref(stFloatParam), 0, sizeof(stFloatParam))
                ret = self.obj_cam.MV_CC_GetFloatValue(name, stFloatParam)
                if ret != 0:
                    logger.warning(f"get float value fail! {to_hex_str(ret)}")
                logger.debug(f"Parameter {name}: {stFloatParam.fCurValue}")
                return stFloatParam.fCurValue
            case "int":
                stIntParam = MVCC_INTVALUE()
                memset(byref(stIntParam), 0, sizeof(stIntParam))
                ret = self.obj_cam.MV_CC_GetIntValue(name, stIntParam)
                if ret != 0:
                    logger.warning(f"get int value fail! {to_hex_str(ret)}")
                logger.debug(f"Parameter {name}: {stIntParam.nCurValue}")
                return stIntParam.nCurValue
            case "enum":
                stEnumParam = MVCC_ENUMVALUE()
                memset(byref(stEnumParam), 0, sizeof(stEnumParam))
                ret = self.obj_cam.MV_CC_GetEnumValue(name, stEnumParam)
                if ret != 0:
                    logger.warning(f"get enum value fail! {to_hex_str(ret)}")
                logger.debug(f"Parameter {name}: {stEnumParam.nCurValue}")
                return stEnumParam.nCurValue

    def set_parameter(self, name: str, value: int | float) -> None:
        if self._is_open is False:
            raise RuntimeError("Camera is not open")
        param_type = MV_CH250_PARAM_TYPE.get(name)
        if param_type is None:
            raise ValueError(f"Unknown parameter name: {name}")

        match param_type:
            case "float":
                stFloatParam = MVCC_FLOATVALUE()
                memset(byref(stFloatParam), 0, sizeof(stFloatParam))
                stFloatParam.fCurValue = float(value)
                ret = self.obj_cam.MV_CC_SetFloatValue(name, stFloatParam)
                if ret != 0:
                    logger.warning(f"set float value fail! {to_hex_str(ret)}")
            case "int":
                stIntParam = MVCC_INTVALUE()
                memset(byref(stIntParam), 0, sizeof(stIntParam))
                stIntParam.nCurValue = int(value)
                ret = self.obj_cam.MV_CC_SetIntValue(name, stIntParam)
                if ret != 0:
                    logger.warning(f"set int value fail! {to_hex_str(ret)}")
            case "enum":
                stEnumParam = MVCC_ENUMVALUE()
                memset(byref(stEnumParam), 0, sizeof(stEnumParam))
                stEnumParam.nCurValue = int(value)
                ret = self.obj_cam.MV_CC_SetEnumValue(name, stEnumParam)
                if ret != 0:
                    logger.warning(f"set enum value fail! {to_hex_str(ret)}")

    def start_grabbing(self) -> None:
        if self._is_open is False:
            raise RuntimeError("Camera is not open")

        ret = self.obj_cam.MV_CC_StartGrabbing()
        if ret != 0:
            logger.warning(f"start grabbing fail! {to_hex_str(ret)}")

        try:
            self._is_grabbing = True
            self._thread_handle = threading.Thread(target=self._grab_images)
            self._thread_handle.start()
        except Exception as e:
            logger.error(f"start grabbing thread fail! {e}")

    def _grab_images(self) -> None:
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))

        try:
            while self._is_grabbing:
                try:
                    ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
                    if 0 == ret:
                        # Copy image and image info
                        if self._last_frame is None:
                            self._last_frame = (
                                c_ubyte * stOutFrame.stFrameInfo.nFrameLen
                            )()
                        self.st_frame_info = stOutFrame.stFrameInfo

                        self._buffer_lock.acquire()
                        try:
                            cdll.msvcrt.memcpy(
                                byref(self._last_frame),
                                stOutFrame.pBufAddr,
                                self.st_frame_info.nFrameLen,
                            )
                        finally:
                            self._buffer_lock.release()

                        logger.debug(
                            "got one frame: Width[%d], Height[%d], nFrameNum[%d], FrameLen[%d]"
                            % (
                                self.st_frame_info.nWidth,
                                self.st_frame_info.nHeight,
                                self.st_frame_info.nFrameNum,
                                self.st_frame_info.nFrameLen,
                            )
                        )
                        # Call frame callback if set
                        if self._frame_callback is not None:
                            try:
                                arr = np.ctypeslib.as_array(
                                    self._last_frame,
                                    shape=(
                                        self.st_frame_info.nHeight,
                                        self.st_frame_info.nWidth,
                                    ),
                                )
                                logger.debug(
                                    f"Callback: arr.shape={arr.shape}, dtype={arr.dtype}, width={self.st_frame_info.nWidth}, height={self.st_frame_info.nHeight}"
                                )
                                self._frame_callback(arr, self.st_frame_info)
                            except Exception as e:
                                logger.error(
                                    f"Error in frame callback: {e}", exc_info=True
                                )
                        # Free buffer
                        self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                    else:
                        logger.warning(f"No data to grab, ret = {to_hex_str(ret)}")
                        if not self._is_grabbing or not self._is_open:
                            break
                        continue
                except Exception as inner:
                    logger.error(f"Exception in grabbing loop: {inner}", exc_info=True)
                    break
        except Exception as thread_exc:
            logger.error(
                f"Fatal exception in grabbing thread: {thread_exc}", exc_info=True
            )

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
