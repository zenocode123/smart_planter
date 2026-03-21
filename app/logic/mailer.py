import smtplib
from email.message import EmailMessage
import os
import mimetypes

async def send_health_report_email(
    sensor_data: dict, 
    ai_analysis: str, 
    photo_path_relative: str = None,
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
          <tr style="background-color: #e8f5e9;"><th>環境溫度</th><td>{sensor_data.get('temp', 'N/A')} °C</td></tr>
          <tr><th>環境濕度</th><td>{sensor_data.get('humidity', 'N/A')} %</td></tr>
          <tr style="background-color: #e8f5e9;"><th>土壤濕度</th><td>{sensor_data.get('moisture', 'N/A')} %</td></tr>
          <tr><th>環境光照</th><td>{sensor_data.get('lux', 'N/A')} Lux</td></tr>
        </table>
        
        <p style="margin-top: 30px; font-size: 14px; color: #666;">
          本郵件由樹莓派自動產生，最新的實體相片與環境趨勢圖已附於信件附檔中，請查收。
        </p>
      </body>
    </html>
    """
    
    msg.set_content("如果您看到這行字，代表您的信箱不支援 HTML 格式。請啟用 HTML 以查看精美的植物報告。")
    msg.add_alternative(html_content, subtype='html')
    
    # 將網頁相對路徑轉為實體路徑以利讀取檔案
    # 照片路徑
    if photo_path_relative:
        photo_real_path = "app" + photo_path_relative.replace("/static", "/static", 1)  # 簡單轉換為原本目錄
        if os.path.exists(photo_real_path):
            ctype, encoding = mimetypes.guess_type(photo_real_path)
            maintype, subtype = ctype.split('/', 1) if ctype else ('application', 'octet-stream')
            with open(photo_real_path, 'rb') as fp:
                msg.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename=f"Plant_Photo.jpg")
        else:
            print(f"⚠️ [Mailer] 找不到照片檔案: {photo_real_path}")

    # 附加圖表
    plot_path = "app/static/plots/history_chart.png"
    if os.path.exists(plot_path):
        ctype, _ = mimetypes.guess_type(plot_path)
        maintype, subtype = ctype.split('/', 1) if ctype else ('image', 'png')
        with open(plot_path, 'rb') as fp:
            msg.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename="Trend_Chart.png")

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
