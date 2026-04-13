import smtplib
from email.message import EmailMessage
import os
import mimetypes

async def send_health_report_email(
    sensor_data: dict, 
    ai_analysis: str, 
    plant_id: int = 0,
    smtp_user: str = None,
    smtp_password: str = None
) -> bool:
    """
    發送 Email 健康報告。
    只讀取傳入的使用者資料庫憑證，不依賴環境變數。
    """
    if not smtp_user or not smtp_password:
        print("⚠️ [Mailer] SMTP 帳號或密碼未設定 (請先綁定帳號)，跳過寄送信件。")
        return False
        
    msg = EmailMessage()
    msg['Subject'] = '🌱 智慧盆栽 - 每日健康報告'
    msg['From'] = f"智慧盆栽小助理 <{smtp_user}>"
    msg['To'] = smtp_user # 自己寄給自己
    
    temp_val = sensor_data.get('temp')
    hum_val = sensor_data.get('humidity')
    moist_val = sensor_data.get('moisture')
    lux_val = sensor_data.get('lux')

    fmt_temp = f"{temp_val:.2f}" if isinstance(temp_val, (int, float)) else 'N/A'
    fmt_hum = f"{hum_val:.2f}" if isinstance(hum_val, (int, float)) else 'N/A'
    fmt_moist = f"{moist_val:.2f}" if isinstance(moist_val, (int, float)) else 'N/A'
    # Lux 通常是整數，但統一格式也無妨。這裡也可視情況轉整數 f"{int(lux_val)}"
    fmt_lux = f"{lux_val:.0f}" if isinstance(lux_val, (int, float)) else 'N/A'

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #4CAF50;">🌱 您的植物健康報告</h2>
        
        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin-top:0;">🪴 來自 AI 的悄悄話：</h3>
            <p style="line-height: 1.6;">{ai_analysis}</p>
        </div>
        
        <h3>📊 感測器數據紀錄</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; min-width: 300px;">
          <tr style="background-color: #e8f5e9;"><th>環境溫度</th><td>{fmt_temp} °C</td></tr>
          <tr><th>環境濕度</th><td>{fmt_hum} %</td></tr>
          <tr style="background-color: #e8f5e9;"><th>土壤濕度</th><td>{fmt_moist} %</td></tr>
          <tr><th>環境光照</th><td>{fmt_lux} Lux</td></tr>
        </table>
        
        <p style="margin-top: 30px; font-size: 14px; color: #666;">
          本郵件由樹莓派自動產生，最新的實體相片與環境趨勢圖已附於信件附檔中，請查收。
        </p>
      </body>
    </html>
    """
    
    msg.set_content("如果您看到這行字，代表您的信箱不支援 HTML 格式。請啟用 HTML 以查看精美的植物報告。")
    msg.add_alternative(html_content, subtype='html')
    
    # 附加照片 (從 RAM disk 取出)
    from app.logic.camera import get_ram_path
    photo_real_path = get_ram_path() / f"latest_plant_{plant_id}.jpg"
    if photo_real_path.exists():
        with open(photo_real_path, 'rb') as fp:
            msg.add_attachment(fp.read(), maintype='image', subtype='jpeg', filename="Plant_Photo.jpg")
    else:
        print(f"⚠️ [Mailer] 找不到照片檔案: {photo_real_path}")

    # 附加圖表 (從記憶體繪製)
    from app.logic.dataviz import generate_history_plot
    buf = await generate_history_plot(limit=50, plant_id=plant_id)
    if buf:
        msg.add_attachment(buf.getvalue(), maintype='image', subtype='png', filename="Trend_Chart.png")


    try:
        # 使用 Gmail smtp.gmail.com:587 TLS 發信
        print("📨 [Mailer] 正在連線至 SMTP 伺服器...")
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        print("✅ [Mailer] 健康報告 Email 已成功寄出！")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ [Mailer] SMTP 登入失敗：請確認信箱密碼或是是否已啟用「應用程式專用密碼」。")
        return False
    except Exception as e:
        print(f"❌ [Mailer] Email 寄送失敗: {e}")
        return False

async def send_alert_email(
    plant_id: int,
    plant_nickname: str,
    smtp_user: str,
    smtp_password: str,
    alert_type: str = "offline",
    anomaly_msg: str = ""
) -> bool:
    """發送無 AI、無數據的純斷線警告或數值異常信"""
    if not smtp_user or not smtp_password:
        return False
        
    msg = EmailMessage()
    if alert_type == "offline":
        msg['Subject'] = f'⚠️ {plant_nickname} - 裝置斷線警告'
    else:
        msg['Subject'] = f'⚠️ {plant_nickname} - 感測器數值異常警告'
    msg['From'] = f"智慧盆栽小助理 <{smtp_user}>"
    msg['To'] = smtp_user
    
    from app.logic.camera import get_ram_path
    photo_real_path = get_ram_path() / f"latest_plant_{plant_id}.jpg"
    has_photo = photo_real_path.exists()
    
    photo_wording = "樹莓派相機剛才拍下了植物最近的狀況（如附件）。" if has_photo else "由於目前未偵測到樹莓派相機或相機尚未連接，因此無法附上植物即時畫面。"

    if alert_type == "offline":
        title_html = '<h2 style="color: #F44336;">⚠️ 您的智慧盆栽已失去連線</h2>'
        desc_html = f'<p>系統已經偵測到 <b>{plant_nickname}</b> 的感測器與水泵失去連線。</p>'
        reasons_html = """
        <p>可能原因：</p>
        <ul>
          <li>ESP32 電源中斷或當機</li>
          <li>Wi-Fi 分享器斷線</li>
        </ul>
        """
    else:
        title_html = '<h2 style="color: #FF9800;">⚠️ 您的智慧盆栽感測器出現異常</h2>'
        desc_html = f'<p>系統偵測到 <b>{plant_nickname}</b> 有極度不合理的感測器數值，已中斷本次 AI 分析與澆水判定以保護植物。</p>'
        reasons_html = f"""
        <div style="background-color: #fff3e0; padding: 15px; border-left: 5px solid #FF9800; margin-bottom: 15px;">
            <h4 style="margin-top: 0; color: #e65100;">異常情形：</h4>
            <ul style="margin-bottom: 0;">{anomaly_msg}</ul>
        </div>
        <p>可能原因：感測器排線鬆脫、硬體接觸不良或短路。</p>
        """

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        {title_html}
        {desc_html}
        {reasons_html}
        <p>{photo_wording}</p>
        <p style="color: #d32f2f;"><b>注意：</b>在您修復硬體連線前，自動排程系統與澆水紀錄將全面暫停。</p>
      </body>
    </html>
    """
    msg.set_content("裝置已斷線，請檢查硬體。")
    msg.add_alternative(html_content, subtype='html')
    
    if has_photo:
        with open(photo_real_path, 'rb') as fp:
            msg.add_attachment(fp.read(), maintype='image', subtype='jpeg', filename="Emergency_Photo.jpg")

    try:
        print("📨 [Mailer] 正在發送緊急斷線警告信...")
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        print("✅ [Mailer] 斷線警告信已成功寄出！")
        return True
    except Exception as e:
        print(f"❌ [Mailer] 警告信寄送失敗: {e}")
        return False
