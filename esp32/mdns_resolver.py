import socket
import select
import time

def resolve_mdns(hostname, timeout_sec=5):
    """
    廣播查詢 mDNS 並解析 .local 結尾的主機名稱為 IP 位址。
    如果在超時時間內找不到，則回傳 None。
    """
    if hostname.endswith('.local'):
        hostname = hostname[:-6]
    
    # mDNS 多播位址與埠號
    MDNS_ADDR = '224.0.0.251'
    MDNS_PORT = 5353

    # 建構基礎的 mDNS [A Record] 查詢封包
    # Transaction ID: 0x0000, Flags: 0x0000 (Standard request)
    # Questions: 1, Answer RRs: 0, Authority RRs: 0, Additional RRs: 0
    packet = bytearray(b'\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00')
    
    # 寫入查詢名稱 (例如: 11 raspberrypi 5 local 0)
    for part in [hostname, 'local']:
        packet.append(len(part))
        packet.extend(part.encode('utf-8'))
    packet.append(0) # 字串結尾的 Null byte
    
    # QTYPE: A (0x0001) IPv4 位址
    # QCLASS: IN (0x0001)
    packet.extend(b'\x00\x01\x00\x01')

    # 建立 UDP Socket 進行多播發送
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    
    try:
        # 發送查詢請求
        sock.sendto(packet, (MDNS_ADDR, MDNS_PORT))
        
        # Poll 迴圈等待回應
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            r, _, _ = select.select([sock], [], [], 1.0)
            if r:
                data, addr = sock.recvfrom(1024)
                
                # 簡單的封包解析：尋找 A Record 回應特徵
                # Type A(0x0001), Class IN(0x0001) 後面會接著 TTL(4 bytes)
                # 與資料長度 Data Length (0x0004)，再來就是 4 bytes 的 IP
                idx = 0
                while idx < len(data) - 10:
                    if data[idx:idx+4] == b'\x00\x01\x00\x01' and data[idx+8:idx+10] == b'\x00\x04':
                        ip_bytes = data[idx+10:idx+14]
                        ip = ".".join([str(b) for b in ip_bytes])
                        return ip
                    idx += 1
    except Exception as e:
        print("mDNS error:", e)
    finally:
        sock.close()
        
    return None
