import cv2
import numpy as np
import os
import logging
import traceback

logger = logging.getLogger(__name__)


def sanitize_image(input_path: str, output_path: str) -> str:
    """
    Reads an image, detects contours that resemble text regions (potential PII),
    and applies a solid redaction block over them.  A guaranteed redaction bar is
    also painted across the bottom 12 % of the image to mask any credit-card /
    account numbers that typically appear in receipt footers.

    Returns the output_path on success, or an empty string on failure.
    """
    logger.info("━━━ [PII REDACTOR] START ━━━")
    logger.info(f"  input_path  : {input_path}")
    logger.info(f"  output_path : {output_path}")

    # ── Pre-flight checks ─────────────────────────────────────────────────────
    if not os.path.exists(input_path):
        logger.error(f"  ✗ FAILED — input file does not exist: '{input_path}'")
        return ""

    file_size = os.path.getsize(input_path)
    logger.info(f"  input file size : {file_size} bytes")
    if file_size == 0:
        logger.error("  ✗ FAILED — input file is empty (0 bytes)")
        return ""

    try:
        # ── Step 1: Read image ────────────────────────────────────────────────
        logger.info("  [1/6] Reading image with cv2.imread ...")
        img = cv2.imread(input_path)
        if img is None:
            logger.error(
                f"  ✗ FAILED — cv2.imread returned None for '{input_path}'. "
                "Possible causes: unsupported format, corrupted file, or "
                "opencv-python-headless cannot decode this codec."
            )
            return ""

        h_img, w_img = img.shape[:2]
        logger.info(f"  ✓ Image loaded  — size: {w_img}×{h_img} px, channels: {img.shape[2]}")

        # ── Step 2: Grayscale + morphological gradient ────────────────────────
        logger.info("  [2/6] Grayscale + morphological gradient ...")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ellipse_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, ellipse_kernel)

        # ── Step 3: Otsu binarisation ─────────────────────────────────────────
        logger.info("  [3/6] Otsu binarisation ...")
        _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

        # ── Step 4: Connect text blobs & find contours ────────────────────────
        logger.info("  [4/6] Connecting text blobs and finding contours ...")
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        connected = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, h_kernel)
        contours, _ = cv2.findContours(
            connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        logger.info(f"  ✓ Found {len(contours)} raw contours")

        # ── Step 5: Redact text-like regions ─────────────────────────────────
        logger.info("  [5/6] Applying redaction blocks ...")
        REDACT_COLOR = (30, 30, 30)
        redacted_count = 0

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h) if h > 0 else 0
            if w > 40 and h > 8 and aspect_ratio > 2.5:
                pad = 4
                y1 = max(0, y - pad)
                y2 = min(h_img, y + h + pad)
                cv2.rectangle(img, (x, y1), (x + w, y2), REDACT_COLOR, thickness=-1)
                redacted_count += 1

        logger.info(f"  ✓ Redacted {redacted_count} text-like contour(s)")

        # Guaranteed footer bar (bottom 12 %)
        footer_start = int(h_img * 0.88)
        cv2.rectangle(img, (0, footer_start), (w_img, h_img), REDACT_COLOR, thickness=-1)
        logger.info(f"  ✓ Footer bar painted  — rows {footer_start}→{h_img}")

        # Guaranteed header bar (top 6 %)
        header_end = int(h_img * 0.06)
        cv2.rectangle(img, (0, 0), (w_img, header_end), REDACT_COLOR, thickness=-1)
        logger.info(f"  ✓ Header bar painted  — rows 0→{header_end}")

        # ── Step 6: Write sanitised image ─────────────────────────────────────
        logger.info(f"  [6/6] Writing sanitised image to '{output_path}' ...")
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        write_ok = cv2.imwrite(output_path, img)
        if not write_ok:
            logger.error(
                f"  ✗ FAILED — cv2.imwrite returned False for '{output_path}'. "
                "Check disk space and that the directory is writable."
            )
            return ""

        saved_size = os.path.getsize(output_path)
        logger.info(f"  ✓ Sanitised image saved — {saved_size} bytes")
        logger.info("━━━ [PII REDACTOR] SUCCESS ━━━")
        return output_path

    except Exception as exc:
        logger.error(f"  ✗ EXCEPTION in sanitize_image: {exc}")
        logger.error(traceback.format_exc())
        return ""
