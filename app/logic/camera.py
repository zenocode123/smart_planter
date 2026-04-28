import cv2
import time
from datetime import datetime
from pathlib import Path
import subprocess
import shutil





UPLOAD_DIR = Path("app/static/uploads/photos")
# 確保資料夾存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_ram_path() -> Path:
    """回傳照片儲存目錄（供 mailer 等模組使用）。"""
    return UPLOAD_DIR


def capture_plant_photo(plant_id: int = 0) -> str | None:
    """
    優先使用 Raspberry Pi 5 的 rpicam-still 獲取影像，
    若無此指令則退回使用 OpenCV 處理。
    改為存放在實體資料夾中並加上時間戳記，以保存歷史紀錄。
    回傳用於 API 的虛擬路徑。
    """
    # 拍照前先強制刪除舊照片，避免相機斷線時被誤抓舊檔
    latest_path = UPLOAD_DIR / f"latest_plant_{plant_id}.jpg"
    if latest_path.exists():
        try:
            latest_path.unlink()
        except OSError:
            pass

    current_time = int(time.time())
    filename = f"plant_{plant_id}_{current_time}.jpg"
    file_path = UPLOAD_DIR / filename

    # 檢查是否有 rpicam-still
    if shutil.which("rpicam-still"):
        try:
            # 呼叫 rpicam-still 拍照，設定 1 秒 (1000ms) 暖機曝光
            subprocess.run(
                [
                    "rpicam-still",
                    "-n",  # 不顯示預覽
                    "--width",
                    "1280",
                    "--height",
                    "960",
                    "--timeout",
                    "2000",
                    "-o",
                    str(file_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # 使用 OpenCV 讀取並加上浮水印
            img_bgr = cv2.imread(str(file_path))
            if img_bgr is not None:
                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(
                    img_bgr,
                    timestamp_str,
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imwrite(
                    str(file_path), img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                )

            # 同步更新 latest_plant_{plant_id}.jpg 供 mailer 使用
            latest_path = UPLOAD_DIR / f"latest_plant_{plant_id}.jpg"
            shutil.copy2(str(file_path), str(latest_path))

            return f"/static/uploads/photos/{filename}"
        except Exception as e:
            print(f"⚠️ rpicam-still 拍照發生錯誤: {e}，嘗試退回 OpenCV。")

    cap = None

    try:
        # 嘗試開啟相機 (通常是 0)
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("⚠️ OpenCV 無法開啟相機設備，跳過拍照。")
            return None

        time.sleep(2)

        ret, frame = cap.read()
        if not ret:
            print("⚠️ OpenCV 無法從相機讀取畫面，跳過拍照。")
            return None

        img_bgr = frame

        h, w = img_bgr.shape[:2]
        new_w = 1280
        new_h = int((new_w / w) * h)
        img_resized = cv2.resize(img_bgr, (new_w, new_h))

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            img_resized,
            timestamp_str,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.imwrite(str(file_path), img_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

        # 同步更新 latest_plant_{plant_id}.jpg 供 mailer 使用
        latest_path = UPLOAD_DIR / f"latest_plant_{plant_id}.jpg"
        shutil.copy2(str(file_path), str(latest_path))

        return f"/static/uploads/photos/{filename}"

    except Exception as e:
        print(f"❌ 相機拍照任務失敗: {e}")
        return None
    finally:
        if cap is not None:
            cap.release()
