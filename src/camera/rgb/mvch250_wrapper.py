import logging
import traceback
from typing import Any, Optional

import numpy as np
from CameraParams_header import MV_TRIGGER_MODE_OFF
from CamOperation_class import CameraOperation
from MvCameraControl_class import (
    MV_CC_DEVICE_INFO,
    MV_CC_DEVICE_INFO_LIST,
    MV_GIGE_DEVICE,
    MVCC_FLOATVALUE,
    POINTER,
    MvCamera,
    byref,
    c_bool,
    cast,
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
    ):
        self.width = int(width)
        self.height = int(height)

        self._init_mvs_sdk()

        self.obj_cam: MvCamera = MvCamera()
        self.st_device_list: MV_CC_DEVICE_INFO_LIST = self._get_device_info_list()
        self.n_connect_num = self._get_camera_index()
        self.mv_handler: Optional[CameraOperation] = self._get_mv_handler()

        self._is_open: bool = False
        self._last_frame: Optional[np.ndarray] = None
        self._last_timestamp: Optional[float] = None

    def _init_mvs_sdk(self):
        try:
            MvCamera.MV_CC_Initialize()
        except Exception:
            logger.error(
                f"Failed to initialize MVS SDK: {traceback.format_exc()}. Make sure it is installed and if it's not located at C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64 that you manually add it to the PATH variable"
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

        if param_type == "float":
            stFloatParam = MVCC_FLOATVALUE()
            memset(byref(stFloatParam), 0, sizeof(stFloatParam))
            ret = self.obj_cam.MV_CC_GetFloatValue(name, stFloatParam)
            if ret != 0:
                logger.warning(f"get float value fail! {to_hex_str(ret)}")
            logger.debug(f"Parameter {name}: {stFloatParam.fCurValue}")
            return stFloatParam.fCurValue

    def set_parameter(self, name: str, value: Any) -> bool:
        if self._is_open is False:
            raise RuntimeError("Camera is not open")
        raise NotImplementedError("Replace with Hikrobot control setters")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
