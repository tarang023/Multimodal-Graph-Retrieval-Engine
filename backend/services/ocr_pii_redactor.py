import cv2
import easyocr
import os
import re
import logging
import traceback

logger = logging.getLogger(__name__)
 
logger.info("Initializing EasyOCR Deep Learning Model...")
reader = easyocr.Reader(['en'], gpu=False)

def sanitize_and_save_ocr(input_path: str, output_dir: str) -> str:
    """
    Uses EasyOCR (Deep Learning) to find text in the image, looks for credit card 
    number patterns, and draws solid redaction blocks over them using OpenCV.
    
    Returns the path to the sanitized file on success, or an empty string on failure.
    """
    logger.info("━━━ [EASY-OCR PII REDACTOR] START ━━━")
    logger.info(f"  input_path : {input_path}")
    logger.info(f"  output_dir : {output_dir}")
    
    if not os.path.exists(input_path):
        logger.error(f"  ✗ FAILED — input file does not exist: '{input_path}'")
        return ""
        
    try:
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.basename(input_path)
        
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
            
        logger.info("  [2/3] Running EasyOCR Deep Learning Inference ...")
        
        results = reader.readtext(img)
        
        redacted_count = 0
        REDACT_COLOR = (30, 30, 30) # Dark charcoal
        
        
        pii_patterns = [
            # 16-digit Credit Cards 
            re.compile(r'\b(?:\d{4}[ -]?){3}\d{4}\b'),
            
            # Fully Obfuscated Cards **** **** **** 1234 
            re.compile(r'\b(?:\*{4}[ -]?){3}\d{4}\b'),
            
            # 3. Bank Account Numbers  
            re.compile(r'\b\d{13,19}\b'),
            
            # 4.  Social Security Numbers 123-45-6789
            re.compile(r'\b\d{3}[- ]?\d{2}[- ]?\d{4}\b')
        ]
        
        for bbox, text, prob in results:
            # Check if the text matches ANY of our strict PII patterns
            if any(pattern.search(text) for pattern in pii_patterns):
                # bbox format from EasyOCR is: [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
                # We need the top-left (0) and bottom-right (2) coordinates for OpenCV
                top_left = tuple(map(int, bbox[0]))
                bottom_right = tuple(map(int, bbox[2]))
                
                # Draw redaction block over the sensitive text
                cv2.rectangle(img, top_left, bottom_right, REDACT_COLOR, thickness=-1)
                redacted_count += 1
                
        logger.info(f"  ✓ Redacted {redacted_count} potential PII block(s) via EasyOCR")
        
        logger.info(f"  [3/3] Saving sanitized image to {output_path} ...")
        write_ok = cv2.imwrite(output_path, img)
        if not write_ok:
            logger.error("  ✗ FAILED — cv2.imwrite failed.")
            return ""
            
        logger.info("━━━ [EASY-OCR PII REDACTOR] SUCCESS ━━━")
        return output_path
        
    except Exception as exc:
        logger.error(f"  ✗ EXCEPTION in sanitize_and_save_ocr: {exc}")
        logger.error(traceback.format_exc())
        return ""