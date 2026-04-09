from flask import Flask, request, render_template
import os
import docx2txt
from pypdf import PdfReader  # Fix 5: replaced deprecated PyPDF2
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.utils import secure_filename  # Fix 3: secure filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'


def extract_text_from_pdf(file_path):
    text = ""
    reader = PdfReader(file_path)  # Fix 5: cleaner pypdf usage
    for page in reader.pages:
        text += page.extract_text() or ""  # handle None return from extract_text
    return text


def extract_text_from_docx(file_path):
    return docx2txt.process(file_path)


def extract_text_from_txt(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def extract_text(file_path):
    if file_path.endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith('.docx'):
        return extract_text_from_docx(file_path)
    elif file_path.endswith('.txt'):
        return extract_text_from_txt(file_path)
    else:
        return ""


@app.route("/")
def matchresume():
    return render_template('matchresume.html')


@app.route('/matcher', methods=['POST'])
def matcher():
    if request.method == 'POST':
        job_description = request.form['job_description']
        resume_files = request.files.getlist('resumes')

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)  # Fix 2: always create folder

        resumes = []
        valid_resume_files = []
        saved_paths = []   # Fix 4: track for cleanup
        empty_resumes = [] # Fix 6: track unreadable files

        for resume_file in resume_files:
            filename = secure_filename(resume_file.filename)  # Fix 3: sanitize
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume_file.save(file_path)
            saved_paths.append(file_path)

            text = extract_text(file_path)

            if not text.strip():  # Fix 6: handle scanned/image-based PDFs
                empty_resumes.append(resume_file.filename)
            else:
                resumes.append(text)
                valid_resume_files.append(resume_file)

        # Fix 4: delete uploaded files after extraction
        for path in saved_paths:
            if os.path.exists(path):
                os.remove(path)

        warning = None
        if empty_resumes:
            warning = f"These files could not be read (possibly scanned): {', '.join(empty_resumes)}"

        if not resumes or not job_description:
            return render_template('matchresume.html',
                                   message="Please upload resumes and enter a job description.",
                                   warning=warning)

        # Vectorize job description and resumes
        vectorizer = TfidfVectorizer().fit_transform([job_description] + resumes)
        vectors = vectorizer.toarray()

        # Calculate cosine similarities
        job_vector = vectors[0]
        resume_vectors = vectors[1:]
        similarities = cosine_similarity([job_vector], resume_vectors)[0]

        # Get top 5 resumes and their similarity scores  # Fix 1: updated comment
        top_indices = similarities.argsort()[-5:][::-1]
        top_resumes = [valid_resume_files[i].filename for i in top_indices]
        similarity_scores = [round(similarities[i], 2) for i in top_indices]

        return render_template('matchresume.html',
                               message="Top matching resumes:",
                               top_resumes=top_resumes,
                               similarity_scores=similarity_scores,
                               warning=warning)

    return render_template('matchresume.html')


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))