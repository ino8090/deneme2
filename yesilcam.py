import os
import sys
import json
import requests
import subprocess
import yt_dlp

# --- AYARLAR VE YAPILANDIRMA ---
M3U_URL = "https://raw.githubusercontent.com/ino8090/0101/refs/heads/main/SD.m3u"
LOGO_URL = "https://raw.githubusercontent.com/ino8090/0101/refs/heads/main/file_000000001218821086dc1a6d6539a2b9.png"
STATE_FILE = "state_yesilcam.json"
RTMP_DEST = "rtmp://ssh101.bozztv.com:1935/ssh101/0212tvv"
LOGO_LOCAL = "logo.png"

print(f"🔧 Kullanılan M3U : {M3U_URL}")
print(f"🔧 Kullanılan Logo : {LOGO_URL}")
print(f"🔧 State dosyası : {STATE_FILE}")
print(f"🔧 RTMP hedefi : {RTMP_DEST}")


# --- 1. LOGO İNDİRME ---
def download_logo(url, output_path):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Logo indirildi ve '{output_path}' olarak kaydedildi.")
    except Exception as e:
        print(f"⚠️ Logo indirilemedi: {e}")


# --- 2. GÜVENLİ STATE OKUMA VE YAZMA ---
def load_state(filepath):
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Yerel state dosyası bozuk/boş, sıfırlanıyor.")
            return {"last_index": 0}
        except Exception as e:
            print(f"⚠️ State okuma hatası: {e}")
            return {"last_index": 0}
    else:
        print("ℹ️ State dosyası bulunamadı veya boş, yeni başlatılıyor.")
        return {"last_index": 0}

def save_state(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ State kaydetme hatası: {e}")


# --- 3. M3U OYNATMA LİSTESİ ÇEKME ---
def fetch_m3u_links(url):
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        lines = res.text.splitlines()
        links = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
        return links
    except Exception as e:
        print(f"❌ M3U listesi çekilemedi: {e}")
        return []


# --- 4. YOUTUBE CANLI / VİDEO AKIŞ LİNKİ ÇIKARMA (BOT ENGELİ AŞICI) ---
def get_youtube_stream_url(youtube_url):
    print(f"🔍 YouTube Akış Linki Çıkarılıyor: {youtube_url}")
    
    # GitHub Actions ip engellerini aşmak için player_client fallback yapılandırması
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'tvhtml5', 'web']
            }
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            stream_url = info.get('url')
            if stream_url:
                return stream_url
            else:
                print(f"❌ YouTube akışı bulunamadı: {youtube_url}")
                return None
    except Exception as e:
        print(f"❌ YouTube akışı alınamadı ({youtube_url}). Hata Detayı: {e}")
        return None


# --- 5. FFMPEG İLE RTMP YAYINI ---
def stream_to_rtmp(video_stream_url, logo_path, rtmp_url):
    # FFmpeg filtresi: Sağ üst köşeye logo yerleştirir ve 1280x720 30fps re-encode eder
    ffmpeg_cmd = [
        "ffmpeg",
        "-re",
        "-i", video_stream_url,
        "-i", logo_path,
        "-filter_complex", "[0:v]scale=1280:720[main];[main][1:v]overlay=W-w-10:10[outv]",
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-maxrate", "3000k",
        "-bufsize", "6000k",
        "-pix_fmt", "yuv420p",
        "-g", "60",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-f", "flv",
        rtmp_url
    ]
    
    try:
        print(f"🚀 FFmpeg yayını başlatılıyor...")
        process = subprocess.Popen(ffmpeg_cmd)
        process.wait()
    except Exception as e:
        print(f"⚠️ Yayın hatası: {e}")


# --- ANA AKIŞ ---
def main():
    download_logo(LOGO_URL, LOGO_LOCAL)
    
    state = load_state(STATE_FILE)
    links = fetch_m3u_links(M3U_URL)
    
    if not links:
        print("❌ Yayınlanacak geçerli link bulunamadı!")
        sys.exit(1)
        
    start_index = state.get("last_index", 0) % len(links)
    
    for i in range(len(links)):
        current_index = (start_index + i) % len(links)
        target_link = links[current_index]
        
        # State güncelle
        state["last_index"] = current_index + 1
        save_state(STATE_FILE, state)
        
        # YouTube linki kontrolü
        if "youtube.com" in target_link or "youtu.be" in target_link:
            stream_url = get_youtube_stream_url(target_link)
        else:
            stream_url = target_link
            
        if stream_url:
            print(f"▶️ İndeks {current_index} oynatılıyor: {target_link}")
            stream_to_rtmp(stream_url, LOGO_LOCAL, RTMP_DEST)
        else:
            print(f"⏭️ Bağlantı alınamadı, sonraki videoya geçiliyor...")

if __name__ == "__main__":
    main()
