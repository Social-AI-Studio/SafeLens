import os
import logging
import threading
import pytesseract
import cv2
import numpy as np
from PIL import Image

try:
    import easyocr

    _HAS_EASYOCR = True
except ImportError:
    _HAS_EASYOCR = False

logger = logging.getLogger(__name__)
G_EASYOCR = None
G_EASYOCR_LOCK = threading.Lock()


def _get_easyocr_reader():
    """Get or create EasyOCR reader singleton (CPU-only, lazy-init)."""
    global G_EASYOCR

    if not _HAS_EASYOCR:
        return None

    if G_EASYOCR is None:
        with G_EASYOCR_LOCK:
            if G_EASYOCR is None:
                try:
                    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

                    reader = easyocr.Reader(["en"], gpu=False, verbose=False)

                    if hasattr(reader, "detector") and hasattr(reader.detector, "cpu"):
                        reader.detector = reader.detector.cpu()
                    if hasattr(reader, "recognizer") and hasattr(
                        reader.recognizer, "cpu"
                    ):
                        reader.recognizer = reader.recognizer.cpu()

                    G_EASYOCR = reader
                    logger.info("EasyOCR reader initialized successfully (CPU-only)")

                except Exception as e:
                    logger.info(
                        f"EasyOCR initialization failed, will use Tesseract fallback: {e}"
                    )
                    G_EASYOCR = None
                    return None

    return G_EASYOCR


def run_ocr(image_path):
    """
    Extract text from image using EasyOCR (primary) with Tesseract fallback.

    Args:
        image_path (str): Path to image file

    Returns:
        str: Extracted text, cleaned and normalized. Empty string on failure.
    """
    img = cv2.imread(image_path)
    if img is None:
        logger.debug(f"Could not load image: {image_path}")
        return ""

    try:
        reader = _get_easyocr_reader()
        if reader is not None:
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            results = reader.readtext(rgb_img, detail=0, paragraph=True)

            text = " ".join(results).strip()
            if text:
                cleaned_text = text.replace("\n", " ")
                logger.debug(f"EasyOCR extracted text: {cleaned_text[:50]}...")
                return cleaned_text
            else:
                logger.debug("EasyOCR returned empty result, falling back to Tesseract")

    except Exception as e:
        logger.debug(f"EasyOCR failed: {e}, falling back to Tesseract")

    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )

        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=1)

        img_pil = Image.fromarray(dilated)

        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(img_pil, config=custom_config)

        cleaned_text = text.strip().replace("\n", " ") if text.strip() else ""
        logger.debug(f"Tesseract extracted text: {cleaned_text[:50]}...")
        return cleaned_text

    except Exception as e:
        logger.debug(f"Tesseract fallback also failed: {e}")
        return ""
