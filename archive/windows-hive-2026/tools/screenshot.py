"""Screenshot tool using Pillow."""

import logging
import io
try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

from .base import Tool

logger = logging.getLogger("hive.tools.screenshot")


class ScreenshotTool(Tool):
    def get_name(self) -> str:
        return "screenshot"

    def get_description(self) -> str:
        return "Capture a screenshot of the screen. Returns the image for OCR or vision analysis."

    async def execute(self, params: dict) -> dict:
        if not self.enabled:
            return {"success": False, "error": "Screenshot tool is disabled"}
        
        if not ImageGrab:
             return {"success": False, "error": "Pillow not installed"}

        region = params.get("region") # tuple (x, y, w, h)
        save_path = params.get("save_path")

        try:
            # Capture
            if region:
                # ImageGrab.grab(bbox=(left, top, right, bottom))
                bbox = (region[0], region[1], region[0] + region[2], region[1] + region[3])
                image = ImageGrab.grab(bbox=bbox)
            else:
                image = ImageGrab.grab()

            # Save if requested
            if save_path:
                image.save(save_path)

            # Convert to bytes for internal passing (e.g. to OCR or Vision)
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()

            return {
                "success": True, 
                "result": {
                    "saved_to": save_path if save_path else "memory",
                    "image_bytes": img_bytes,
                    "size": image.size
                }
            }

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return {"success": False, "error": str(e)}
