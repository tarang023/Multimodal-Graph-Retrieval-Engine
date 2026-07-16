import cv2
import pytesseract
import os
import re
import logging
import traceback

logger = logging.getLogger(__name__)

def sanitize_and_save_ocr(input_path: str, output_dir: str) -> str:
    """
    Uses pytesseract to find text in the image, looks for credit card number patterns,
    and draws solid redaction blocks over them using OpenCV.
    
    Returns the path to the sanitized file on success, or an empty string on failure.
    """
    logger.info("━━━ [OCR PII REDACTOR] START ━━━")
    logger.info(f"  input_path : {input_path}")
    logger.info(f"  output_dir : {output_dir}")
    
    if not os.path.exists(input_path):
        logger.error(f"  ✗ FAILED — input file does not exist: '{input_path}'")
        return ""
        
    try:
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.basename(input_path)
        
        # In our pipeline, it comes as 'raw_filename.ext'. We want 'sanitized_filename.ext'
        if filename.startswith("raw_"):
            out_filename = filename.replace("raw_", "sanitized_", 1)
        else:
            out_filename = f"sanitized_{filename}"
            
        output_path = os.path.join(output_dir, out_filename)
        
        logger.info("  [1/3] Reading image with cv2.imread ...")
        img = cv2.imread(input_path)
        if img is None:
            logger.error("  ✗ FAILED — cv2.imread returned None.")
            return ""
            
        logger.info("  [2/3] Running pytesseract OCR ...")
        # Get bounding box estimates for text
        # 'data' will have columns: level, page_num, block_num, par_num, line_num, word_num, left, top, width, height, conf, text
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        
        # Common credit card pattern: 13-19 digits, possibly with spaces or dashes
        # We look for chunks of digits.
        cc_pattern = re.compile(r'(?:\d[ -]*?){13,19}')
        
        redacted_count = 0
        REDACT_COLOR = (30, 30, 30) # Dark charcoal
        
        # Combine words into lines for better regex matching, but since we need bounding boxes,
        # we will check individual words for numbers and if they look like parts of a CC.
        # A simpler approach: if a word contains 4+ digits, redact it just to be safe.
        digit_chunk = re.compile(r'\d{4,}')
        
        for i, text in enumerate(data['text']):
            if not text.strip():
                continue
                
            # If the text fragment matches 4 or more digits (part of a CC number)
            if digit_chunk.search(text):
                x = data['left'][i]
                y = data['top'][i]
                w = data['width'][i]
                h = data['height'][i]
                
                # Draw redaction block
                cv2.rectangle(img, (x, y), (x + w, y + h), REDACT_COLOR, thickness=-1)
                redacted_count += 1
                
        logger.info(f"  ✓ Redacted {redacted_count} potential PII block(s) via OCR")
        
        logger.info(f"  [3/3] Saving sanitized image to {output_path} ...")
        write_ok = cv2.imwrite(output_path, img)
        if not write_ok:
            logger.error("  ✗ FAILED — cv2.imwrite failed.")
            return ""
            
        logger.info("━━━ [OCR PII REDACTOR] SUCCESS ━━━")
        return output_path
        
    except Exception as exc:
        logger.error(f"  ✗ EXCEPTION in sanitize_and_save_ocr: {exc}")
        logger.error(traceback.format_exc())
        return ""
