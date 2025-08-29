import datetime
import logging
import time

import cv2
import numpy as np
from MvCameraControl_class import _MV_DISPLAY_FRAME_INFO_

from camera.hsi.fx17_wrapper import FX17CameraWrapper
from camera.rgb.mvch250_param_types import MV_CH250_PARAM_TYPE
from camera.rgb.mvch250_wrapper import MVCH250CameraWrapper

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

first_frame_displayed = False


def show_frame_callback(frame: np.ndarray, frame_info: _MV_DISPLAY_FRAME_INFO_):
    global first_frame_displayed
    try:
        width = frame_info.nWidth
        height = frame_info.nHeight
        buffer_size = frame.size
        expected_size_8bit = width * height
        expected_size_16bit = width * height * 2
        logger.debug(
            f"Callback called: frame dtype={frame.dtype}, shape={frame.shape}, width={width}, height={height}, buffer_size={buffer_size}, expected_size_8bit={expected_size_8bit}, expected_size_16bit={expected_size_16bit}"
        )
        if buffer_size == expected_size_8bit:
            img = frame.reshape((height, width))
            logger.debug(
                f"Image reshaped for 8-bit Bayer: {img.shape}, dtype={img.dtype}, min={img.min()}, max={img.max()}"
            )
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BAYER_RG2RGB)
        elif buffer_size == expected_size_16bit:
            img = frame.view(np.uint16).reshape((height, width))
            logger.debug(
                f"Image reshaped for 16-bit Bayer: {img.shape}, dtype={img.dtype}, min={img.min()}, max={img.max()}"
            )
            # For BayerRG12, right-shift by 4 bits to get 8-bit
            img_8bit = (img >> 4).astype(np.uint8)
            logger.debug(
                f"Converted to 8-bit from 12-bit: min={img_8bit.min()}, max={img_8bit.max()}"
            )
            img_rgb = cv2.cvtColor(img_8bit, cv2.COLOR_BAYER_RG2RGB)
        else:
            logger.error(
                f"Buffer size {buffer_size} does not match expected Bayer size for 8-bit ({expected_size_8bit}) or 16-bit ({expected_size_16bit})"
            )
            return
        if img_rgb.max() == 0:
            logger.warning(
                "Image is all black after conversion. Check exposure, Bayer pattern, or camera output."
            )
        # Resize for display if too large
        max_display_width = 1280
        max_display_height = 720
        scale = min(max_display_width / width, max_display_height / height, 1.0)
        if scale < 1.0:
            img_rgb_disp = cv2.resize(
                img_rgb, (int(width * scale), int(height * scale))
            )
        else:
            img_rgb_disp = img_rgb
        # Overlay timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(
            img_rgb_disp,
            timestamp,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow("MV-CH250 Live (RGB)", img_rgb_disp)
        first_frame_displayed = True
        cv2.waitKey(1)
    except Exception as e:
        logger.error(f"Error displaying frame: {e}", exc_info=True)


def main():
    global first_frame_displayed
    cam_rgb = MVCH250CameraWrapper(frame_callback=show_frame_callback)

    cam_rgb.open()
    logger.info(
        f"Camera opened successfully with GigE device index {cam_rgb.n_connect_num}."
    )

    for param in MV_CH250_PARAM_TYPE.keys():
        try:
            cam_rgb.get_parameter(param)
        except Exception as e:
            logger.warning(f"Failed to get parameter {param}: {e}")

    try:
        cam_rgb.start_grabbing()

        window_name = "MV-CH250 Live (RGB)"
        while cam_rgb._is_grabbing:
            if first_frame_displayed:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    cam_rgb._is_grabbing = False
                    break
            time.sleep(0.1)
    except Exception as e:
        logger.warning(f"Failed to start grabbing: {e}")
    finally:
        cam_rgb.close()
        cv2.destroyAllWindows()
        logger.info("Camera closed successfully.")


if __name__ == "__main__":
    main()
