import logging

from camera.hsi.fx17_wrapper import FX17CameraWrapper
from camera.rgb.mvch250_wrapper import MVCH250CameraWrapper

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def main():
    cam_rgb = MVCH250CameraWrapper()

    cam_rgb.open()
    logger.info(
        f"Camera opened successfully with GigE device index {cam_rgb.n_connect_num}."
    )

    cam_rgb.get_parameter("AcquisitionFrameRate")

    cam_rgb.close()
    logger.info("Camera closed successfully.")


if __name__ == "__main__":
    main()
