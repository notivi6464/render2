from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from redis import Redis
from rq import Queue
import psutil
import platform
import os
from rq.job import Job
from worker import process_video

# Flask ve Redis ayarları
app = Flask(__name__)
app.secret_key = 'c54a4bd2916b2deadd789028c4ed1ed1'
app.config['UPLOAD_FOLDER'] = 'uploads'
CATEGORY_DIRECTORY = 'categories'
conn = Redis()
q = Queue(connection=conn)

def get_cpu_temperature():
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            return temps['coretemp'][0].current
        elif 'cpu_thermal' in temps:
            return temps['cpu_thermal'][0].current
    except (AttributeError, KeyError, IndexError):
        return "Not Available"

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/server')
def server():
    return render_template('server.html')

@app.route('/category/add', methods=['GET', 'POST'])
def category_add():
    if request.method == 'POST':
        category_name = request.form.get('category_name')

        if category_name:
            if not os.path.exists(CATEGORY_DIRECTORY):
                os.makedirs(CATEGORY_DIRECTORY)

            category_path = os.path.join(CATEGORY_DIRECTORY, category_name)
            existing_categories = [d.lower() for d in os.listdir(CATEGORY_DIRECTORY)]

            if category_name.lower() in existing_categories:
                flash(f"Category '{category_name}' already exists (case insensitive).", "warning")
            else:
                os.makedirs(category_path)
                flash(f"Category '{category_name}' created successfully!", "success")

            return redirect(url_for('category_add'))
        else:
            flash("Please enter a category name.", "danger")

    return render_template('category_add.html')

@app.route('/category/manage')
def category_manage():
    if os.path.exists(CATEGORY_DIRECTORY):
        categories = os.listdir(CATEGORY_DIRECTORY)
        categories = sorted(categories, key=lambda x: os.path.getctime(os.path.join(CATEGORY_DIRECTORY, x)))
    else:
        categories = []

    categories_with_id = list(enumerate(categories, 1))
    return render_template('category_manage.html', categories=categories_with_id)

@app.route('/category/edit/<category_name>', methods=['GET', 'POST'])
def category_edit(category_name):
    if request.method == 'POST':
        new_name = request.form.get('new_name')
        if new_name:
            old_path = os.path.join(CATEGORY_DIRECTORY, category_name)
            new_path = os.path.join(CATEGORY_DIRECTORY, new_name)
            
            if os.path.exists(new_path):
                flash(f"Category '{new_name}' already exists.", "danger")
            else:
                os.rename(old_path, new_path)
                flash(f"Category '{category_name}' renamed to '{new_name}' successfully!", "success")
                return redirect(url_for('category_manage'))
    
    return render_template('category_edit.html', category_name=category_name)

@app.route('/category/delete/<category_name>', methods=['POST'])
def category_delete(category_name):
    category_path = os.path.join(CATEGORY_DIRECTORY, category_name)
    if os.path.exists(category_path):
        os.rmdir(category_path)
        flash(f"Category '{category_name}' deleted successfully!", "success")
    else:
        flash(f"Category '{category_name}' does not exist.", "danger")
    return redirect(url_for('category_manage'))

@app.route('/render/add', methods=['GET', 'POST'])
def render_add():
    if os.path.exists(CATEGORY_DIRECTORY):
        categories = sorted(os.listdir(CATEGORY_DIRECTORY), key=lambda x: os.path.getctime(os.path.join(CATEGORY_DIRECTORY, x)))
    else:
        categories = []

    if request.method == 'POST':
        selected_category = request.form.get('category')  
        video_file = request.files.get('video_file')
        video_name = request.form.get('video_name')
        text_size = request.form.get('text_size')
        text_color = request.form.get('text_color')
        text_position = request.form.get('text_position')
        logo_file = request.files.get('logo_file')
        logo_size = request.form.get('logo_size')
        logo_position = request.form.get('logo_position')
        video_codec = request.form.get('video_codec')
        audio_codec = request.form.get('audio_codec')
        video_quality = request.form.get('video_quality')
        bitrate = request.form.get('bitrate')

        # Dosyaları ana dizine kaydet
        if video_file:
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_file.filename)
            video_file.save(video_path)
        
        logo_path = None
        if logo_file:
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_file.filename)
            logo_file.save(logo_path)

        # Render için iş kuyruğuna ekle
        job = q.enqueue(process_video, video_path, video_name, text_position, int(text_size), text_color, logo_path, video_quality, bitrate, selected_category, job_timeout=172800, meta={'category': selected_category})

        flash(f"Render işlemi başlatıldı. İş ID: {job.id}", "success")

        return redirect(url_for('render_add'))

    return render_template('render_add.html', categories=categories)

@app.route('/render/list')
def render_list():
    # Tüm işleri al ve durumlarını güncelle
    job_ids = q.job_ids
    jobs = []
    for job_id in job_ids:
        try:
            job = Job.fetch(job_id, connection=conn)
            job.refresh()  # İşin güncel durumunu al
            jobs.append({
                'id': job_id,
                'status': job.get_status(),
                'category': job.meta.get('category', 'Unknown'),
                'progress': job.meta.get('progress', 'Bilinmiyor'),
                'video_name': job.args[1]
            })
        except Exception as e:
            print(f"Hata: {e}")
    
    return render_template('render_list.html', jobs=jobs)

@app.route('/api/server-status')
def server_status():
    cpu_info = platform.uname().processor
    cpu_cores = psutil.cpu_count(logical=False)
    cpu_threads = psutil.cpu_count(logical=True)
    cpu_temperature = get_cpu_temperature()
    cpu_freq = psutil.cpu_freq().current
    cpu_usage_total = psutil.cpu_percent(interval=1)
    cpu_usage_per_core = psutil.cpu_percent(interval=1, percpu=True)
    
    ram_info = psutil.virtual_memory()
    swap_info = psutil.swap_memory()
    ram_total_gb = round(ram_info.total / (1024 ** 3), 2)
    ram_used_percent = ram_info.percent
    swap_total_gb = round(swap_info.total / (1024 ** 3), 2)
    swap_used_percent = swap_info.percent

    return jsonify({
        'cpu_info': cpu_info,
        'cpu_cores': cpu_cores,
        'cpu_threads': cpu_threads,
        'cpu_temperature': round(cpu_temperature, 1) if isinstance(cpu_temperature, (int, float)) else cpu_temperature,
        'cpu_freq': round(cpu_freq, 2),
        'cpu_usage_total': cpu_usage_total,
        'cpu_usage_per_core': cpu_usage_per_core,
        'ram_total_gb': ram_total_gb,
        'ram_used_percent': ram_used_percent,
        'swap_total_gb': swap_total_gb,
        'swap_used_percent': swap_used_percent
    })

@app.route('/explanation')
def explanation():
    return render_template('explanation.html')

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(CATEGORY_DIRECTORY):
        os.makedirs(CATEGORY_DIRECTORY)
    app.run(debug=True)
