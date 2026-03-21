import cv2
import time
import os
from datetime import datetime
from pathlib import Path
try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None

UPLOAD_DIR = Path("app/static/uploads/history")

def capture_plant_photo() -> str | None:
    """
    使用 Picamera2 獲取影像，並結合 OpenCV 進行尺寸調整與存檔。
    回傳圖片的相對路徑 (例如 "/static/uploads/history/log_2024...jpg") 以供資料庫儲存。
    """
    if Picamera2 is None:
        print("⚠️ Picamera2 未安裝或無法匯入，跳過拍照。")
        return None
        
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    file_path = UPLOAD_DIR / filename
    
    picam2 = None
    try:
        picam2 = Picamera2()
        picam2.start()
        
        # 讓相機預熱 2 秒，以利自動曝光估算
        time.sleep(2)
        
        # Picamera2 直接擷取 numpy 原生陣列 (RGB 格式)
        img_array = picam2.capture_array("main")
        
        # OpenCV 處理：Picamera2 取得的是 RGB，OpenCV 存檔需要 BGR
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # OpenCV 處理：縮放解析度以節省儲存空間與 Email 附件大小
        # 例如固定寬度 1280，等比例縮放
        h, w = img_bgr.shape[:2]
        new_w = 1280
        new_h = int((new_w / w) * h)
        img_resized = cv2.resize(img_bgr, (new_w, new_h))
        
        # OpenCV 處理：可加入時間戳記浮水印 (選配功能，可註解)
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(img_resized, timestamp_str, (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2, cv2.LINE_AA)
        
        # 最終利用 OpenCV 參數進行 JPEG 存檔
        cv2.imwrite(str(file_path), img_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        
        return f"/static/uploads/history/{filename}"
        
    except Exception as e:
        print(f"❌ 相機拍照任務失敗: {e}")
        return None
    finally:
        if picam2:
            picam2.stop()
