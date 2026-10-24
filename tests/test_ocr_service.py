import unittest
from unittest.mock import patch

from services.ocr_service import OCRLimitExceeded, _ocr_image


class FakeImage:
    def __init__(self, size):
        self.size = size


class TestOCRBounds(unittest.TestCase):
    def test_rejects_images_over_pixel_limit(self):
        image = FakeImage((5000, 5000))
        with patch("services.ocr_service.MAX_IMAGE_PIXELS", 1_000_000):
            with self.assertRaises(OCRLimitExceeded):
                _ocr_image(image, 0)

    def test_rejects_expired_ocr_time_budget(self):
        image = FakeImage((10, 10))
        with patch("services.ocr_service.OCR_TIMEOUT_SECONDS", 1), patch(
            "services.ocr_service.time.monotonic", side_effect=[10, 12]
        ):
            with self.assertRaises(OCRLimitExceeded):
                _ocr_image(image, 10)


if __name__ == "__main__":
    unittest.main()
