from flask import Flask, render_template, request, send_from_directory, redirect, url_for, jsonify, session, Response
from werkzeug.utils import secure_filename
import time
import os
import json
import openai
from utils import table_of_content_chunk, chat_completion, table_of_content_exist_checker, page_chunks
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = "a_complex_string_which_is_difficult_to_guess"
# app.secret_key = os.getenv("SECRET_KEY") if SECRET_KEY is in .env
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['QUESTION'] = "请用中文告诉我这个章节内容的重点是什么？"
app.config['QUESTION'] = "请用中文告诉我这一页内容的重点是什么？"
pdf_folder = os.path.join(app.root_path, 'static', 'pdfs')
progress = 0  # 这个变量将存储进度信息

def get_notes_file_path(filename):
    filename = secure_filename(filename)
    return os.path.join(app.root_path, 'static', 'notes', filename + '.json')


def save_note(filename, page_num, note):
    filepath = get_notes_file_path(filename)

    # 先读取现有的笔记
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            notes = json.load(f)
    else:
        notes = {}

    # 更新对应的笔记
    notes[str(page_num)] = note

    # 写回文件
    with open(filepath, 'w') as f:
        json.dump(notes, f)


def load_note(filename, page_num):
    filepath = get_notes_file_path(filename)

    # 如果文件存在，则读取对应的笔记
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            notes = json.load(f)
        return notes.get(str(page_num), '')  # 如果没有对应的笔记，则返回空字符串
    else:
        return ''  # 如果文件不存在，则返回空字符串


@app.route('/')
def home():
    pdf_files = os.listdir(app.config['UPLOAD_FOLDER'])  # 修改这里，改为读取上传的 PDF 文件
    return render_template('index.html', pdf_files=pdf_files)


@app.route("/progress")
def get_progress():
    def generate():
        global progress
        while progress < 100:
            yield f"data:{progress}\n\n"
            time.sleep(1)
        progress = 0
    return Response(generate(), mimetype='text/event-stream')


@app.route('/uploads/<path:filename>')  # 新增这个路由，用于提供上传的 PDF 文件
def serve_uploaded_pdf(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return redirect(url_for('home'))  # 上传文件后，重定向回主界面
    return render_template('upload.html')


@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    # 安全地处理文件名
    filename = secure_filename(filename)
    # 删除上传的PDF文件
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    # 删除JSON文件
    json_path = os.path.join(app.root_path, 'static', 'pdfs', filename + '.json')
    if os.path.exists(json_path):
        os.remove(json_path)
    # 删除 notes 文件
    notes_path = get_notes_file_path(filename)
    if os.path.exists(notes_path):
        os.remove(notes_path)
    # 重定向回主页
    return redirect(url_for('home'))


@app.route('/delete_analysis/<filename>', methods=['POST'])
def delete_analysis(filename):
    # 安全地处理文件名
    filename = secure_filename(filename)
    # 删除 JSON 文件
    json_path = os.path.join(app.root_path, 'static', 'pdfs', filename + '.json')
    if os.path.exists(json_path):
        os.remove(json_path)
    # 删除 notes 文件
    notes_path = get_notes_file_path(filename)
    if os.path.exists(notes_path):
        os.remove(notes_path)
    # 重定向回主页
    return redirect(url_for('home'))


@app.route('/view/<filename>')
def view_pdf(filename):
    session['filename'] = filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    chunks_path = os.path.join(app.root_path, 'static', 'pdfs', filename + '.json')

    if os.path.exists(chunks_path):
        with open(chunks_path, 'r') as f:
            chunk_data = json.load(f)
            total_usage = chunk_data.get('total_usage', 'N/A')
    else:
        total_usage = 'N/A'  # 如果 chunks 文件不存在，则 total_usage 为 'N/A'

    return render_template('view_pdf.html', filename=filename, total_usage=total_usage)


@app.route('/api/generate_chunks/<filename>', methods=['POST'])
def generate_chunks(filename):
    global progress
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    chunks_path = os.path.join(app.root_path, 'static', 'pdfs', filename + '.json')
    chunks_info = []
    if_toc_valid = table_of_content_exist_checker(file_path)
    if if_toc_valid:
        app.config['QUESTION'] = "请用中文告诉我这个段落内容的重点是什么？"
        chunks, pages, chunks_names = table_of_content_chunk(file_path)
    else:
        app.config['QUESTION'] = "请用中文告诉我这一页内容的重点是什么？"
        chunks, pages, chunks_names = page_chunks(file_path)
    total_usage = 0
    chunks_count = len(chunks)
    for i, chunk in enumerate(chunks):
        chunk_words_count = len(chunk.split(' '))
        if chunk_words_count >= 5:
            chunk, usage = chat_completion(app.config['QUESTION'], chunk, temperature=0.1)
        else:
            chunk = ' '
            usage = 0
        progress = (i + 1) / chunks_count * 100
        total_usage += usage
        chunks_info.append(chunk)
    chunk_data = {
        'chunks': chunks_info,
        'pages': pages,
        'chunks_names': chunks_names,
        'total_usage': f'{total_usage}USD'
    }
    with open(chunks_path, 'w') as f:
        json.dump(chunk_data, f)

    return jsonify(chunk_data)  # 返回生成的 chunks 数据


@app.route('/api/chunks/<int:page_num>', methods=['GET'])
def get_chunks(page_num):
    filename = session['filename']
    if not filename:
        return jsonify({'error': 'No file selected'}), 400  # 如果没有选择文件，返回错误信息

    chunks_path = os.path.join(app.root_path, 'static', 'pdfs', filename + '.json')

    if not os.path.exists(chunks_path):
        return jsonify({'error': 'Chunks data not found'}), 404  # 如果没有找到 chunks 数据，返回错误信息

    with open(chunks_path, 'r') as f:
        chunk_data = json.load(f)

    chunks = chunk_data['chunks']
    pages = chunk_data['pages']
    chunks_names = chunk_data['chunks_names']

    page_chunks = []
    for i, page in enumerate(pages):
        if page == page_num:
            page_chunks.append(chunks_names[i] + ': \n' + chunks[i])
    return jsonify({'chunks': page_chunks})


@app.route('/download_chunks/<filename>', methods=['GET'])
def download_chunks(filename):
    chunks_path = os.path.join(app.root_path, 'static', 'pdfs', filename + '.json')
    if os.path.exists(chunks_path):
        return send_from_directory(directory=os.path.join(app.root_path, 'static', 'pdfs'), path=filename + '.json', as_attachment=True)
    else:
        return "File not found.", 404


@app.route('/api/notes/<filename>/<int:page_num>', methods=['GET', 'POST'])
def handle_notes(filename, page_num):
    # 根据请求方法进行不同的处理
    if request.method == 'POST':
        # 保存笔记
        note = request.form.get('note')
        save_note(filename, page_num, note)  # 你需要自己实现这个函数
        return 'Note saved.', 200
    else:
        # 加载笔记
        note = load_note(filename, page_num)  # 你需要自己实现这个函数
        return jsonify({'note': note})


@app.route('/api/notes/<filename>/first_page', methods=['GET'])
def get_first_page_note(filename):
    # 读取第一页的笔记
    note = load_note(filename, 1)
    return jsonify({'note': note})


@app.route('/api/notes_first_nonempty/<filename>', methods=['GET'])
def get_first_nonempty_note(filename):
    filepath = get_notes_file_path(filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            notes = json.load(f)

        # 将笔记按页码排序
        sorted_notes = sorted(notes.items(), key=lambda x: int(x[0]))

        # 找到第一条非空的笔记
        for page_num, note in sorted_notes:
            if note.strip():  # 如果笔记不为空
                return jsonify({'page_num': page_num, 'note': note})

    # 如果没有找到非空的笔记，或者文件不存在，则返回空字符串
    return jsonify({'page_num': None, 'note': ''})


if __name__ == "__main__":
    load_dotenv()
    openai.api_key = os.getenv('OPENAI_API_KEY')
    app.run(host='0.0.0.0')
