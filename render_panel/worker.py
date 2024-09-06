import os
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, ImageClip
from redis import Redis
from rq import Worker, Queue, Connection, get_current_job

# Redis bağlantısı
conn = Redis()
q = Queue(connection=conn)

def convert_position(position):
    """Pozisyon değerini MoviePy için uygun formata dönüştür."""
    positions = {
        'center': 'center',
        'top': ('center', 'top'),
        'bottom': ('center', 'bottom'),
        'left': ('left', 'center'),
        'right': ('right', 'center'),
        'top left': ('left', 'top'),
        'top right': ('right', 'top'),
        'bottom left': ('left', 'bottom'),
        'bottom right': ('right', 'bottom')
    }
    return positions.get(position.lower(), 'center')

def update_progress(job, progress):
    """İşin ilerleme durumunu Redis'e kaydeder."""
    job.meta['progress'] = progress
    job.save_meta()

def process_video(file_path, text, position, font_size, color, logo_path, resolution, bitrate, category):
    try:
        # Seçilen kategoriye göre çıktı dizinini ayarla
        output_directory = os.path.join('categories', category)
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        job = get_current_job()  # Mevcut işi al
        update_progress(job, "Başlatıldı")

        # Videoyu yükle ve çözünürlüğü ayarla
        video = VideoFileClip(file_path)
        width, height = map(int, resolution.split('x'))
        video = video.resize(newsize=(width, height))

        # Metin ve logo kliplerini oluştur
        text_position = convert_position(position)
        text_clip = TextClip(text, fontsize=font_size, color=color).set_position(text_position).set_duration(video.duration)

        # Logo ekleme
        logo_clip = None
        if logo_path and os.path.exists(logo_path):
            logo_clip = ImageClip(logo_path).set_duration(video.duration).resize(height=50).set_position(('right', 'bottom'))

        # Videoya metin ve logo ekle
        clips = [video, text_clip]
        if logo_clip:
            clips.append(logo_clip)
        result = CompositeVideoClip(clips)

        # Bitrate formatını düzeltme
        if not bitrate.endswith('k'):
            bitrate = f'{bitrate}k'

        # Çıktı dosya yolu ve işleme
        output_path = os.path.join(output_directory, f'rendered_{os.path.basename(file_path).split(".")[0]}.mp4')

        update_progress(job, "İşleniyor...")

        result.write_videofile(output_path, codec='libx264', bitrate=bitrate, threads=4)

        # Tamamlama durumu güncelle
        update_progress(job, "Tamamlandı")

        # Geçici dosyaları sil
        temp_audio_path = output_path.replace(".mp4", "TEMP_MPY_wvf_snd.mp3")
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

        # İşleme tamamlandığında kaynak dosyaları sil
        os.remove(file_path)  # Video dosyasını sil
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)  # Logo dosyasını sil

    except Exception as e:
        print(f"Video işleme hatası: {str(e)}")
        update_progress(job, f"Hata: {str(e)}")

# Worker'ı başlat
if __name__ == '__main__':
    with Connection(conn):
        worker = Worker([q])
        worker.work(with_scheduler=True)
