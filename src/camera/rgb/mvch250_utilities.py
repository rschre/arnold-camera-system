import logging

from MvCameraControl_class import (
    MV_CC_DEVICE_INFO,
    MV_GENTL_GIGE_DEVICE,
    MV_GIGE_DEVICE,
    POINTER,
    cast,
    ctypes,
)

logger = logging.getLogger(__name__)


# HIKROBOT MVS Functions
def to_hex_str(num: int) -> str:
    chaDic = {10: "a", 11: "b", 12: "c", 13: "d", 14: "e", 15: "f"}
    hexStr = ""
    if num < 0:
        num = num + 2**32
    while num >= 16:
        digit = num % 16
        hexStr = chaDic.get(digit, str(digit)) + hexStr
        num //= 16
    hexStr = chaDic.get(num, str(num)) + hexStr
    return hexStr


def decoding_char(c_ubyte_value):
    c_char_p_value = ctypes.cast(c_ubyte_value, ctypes.c_char_p)
    try:
        decode_str = c_char_p_value.value.decode(  # type: ignore
            "gbk"
        )  # Chinese characters
    except UnicodeDecodeError:
        decode_str = str(c_char_p_value.value)
    return decode_str


def list_devices(device_info_list):
    devices_list = []
    logger.debug("Listing available GigE devices...")
    for i in range(0, device_info_list.nDeviceNum):
        mvcc_dev_info = cast(
            device_info_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)
        ).contents
        if (
            mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE
            or mvcc_dev_info.nTLayerType == MV_GENTL_GIGE_DEVICE
        ):
            user_defined_name = decoding_char(
                mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName
            )
            model_name = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName)
            nip1 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xFF000000) >> 24
            nip2 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00FF0000) >> 16
            nip3 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000FF00) >> 8
            nip4 = mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000FF
            logger.debug(
                "\nGigE device: [%d]" % i
                + "\nDevice User Defined Name: "
                + user_defined_name
                + "\nDevice Model Name: "
                + model_name
                + "\nCurrent IP: %d.%d.%d.%d \n" % (nip1, nip2, nip3, nip4)
            )
            devices_list.append(
                "["
                + str(i)
                + "]GigE: "
                + user_defined_name
                + " "
                + model_name
                + "("
                + str(nip1)
                + "."
                + str(nip2)
                + "."
                + str(nip3)
                + "."
                + str(nip4)
                + ")"
            )

        if len(devices_list) == 0:
            logger.debug("No GigE devices found.")
    return devices_list
