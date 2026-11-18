import base64
from io import BytesIO
import mss
from PIL import Image

class ScreenCapture:
    @staticmethod
    def capture_screen_base64() -> str:
        """Takes a screenshot of the primary monitor and returns it as a base64-encoded JPEG string."""
        with mss.mss() as sct:
            # Grab the primary monitor screen
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            
            # Convert raw bytes to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            
            # Compress into JPEG in-memory
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=80)
            
            # Encode to base64 string
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            print("[Faulkner Vision] Captured screen snapshot.")
            return img_str