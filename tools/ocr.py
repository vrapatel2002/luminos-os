"""OCR tool using Tesseract to extract text from images."""

import logging
import os
import io
try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

from .base import Tool

logger = logging.getLogger("hive.tools.ocr")


class OCRTool(Tool):
    def __init__(self, config: dict):
        super().__init__(config)
        self.engine = config.get("engine", "tesseract")
        self.tesseract_path = config.get("tesseract_path", "")
        
        # Configure pytesseract path if provided
        if self.tesseract_path and pytesseract:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

    async def execute(self, params: dict) -> dict:
        if not self.enabled:
            return {"success": False, "error": "OCR tool is disabled"}
        
        if not pytesseract or not Image:
             return {"success": False, "error": "pytesseract or Pillow not installed"}

        image_path = params.get("image_path")
        image_bytes = params.get("image_bytes")

        try:
            image = None
            if image_path:
                if not os.path.exists(image_path):
                    return {"success": False, "error": f"Image file not found: {image_path}"}
                image = Image.open(image_path)
            elif image_bytes:
                image = Image.open(io.BytesIO(image_bytes))
            else:
                 return {"success": False, "error": "No image_path or image_bytes provided"}

            # Perform OCR
            text = pytesseract.image_to_string(image)
            return {"success": True, "result": text}

        except Exception as e:
            # Check for common Tesseract-not-found error
            msg = str(e)
            if "tesseract is not installed" in msg.lower() or "not find" in msg.lower():
                return {
                    "success": False, 
                    "error": f"Tesseract binary not found at '{self.tesseract_path}'. Please install Tesseract or check path."
                }
            
            logger.error(f"OCR failed: {e}")
            return {"success": False, "error": f"OCR failed: {e}"}

    def get_name(self) -> str:
        return "ocr"

    def get_description(self) -> str:
        return "Extract text from images using OCR. Use this for reading text in screenshots, photos, or scanned documents. Do NOT use the vision model for text extraction."
