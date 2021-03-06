"""
ccextractor-web | controller.py

Author   : Saurabh Shrivastava
Email    : saurabh.shrivastava54+ccextractorweb[at]gmail.com
Link     : https://github.com/saurabhshri

"""
import os
import hashlib
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, g
from mod_dashboard.models import UploadedFiles
from mod_dashboard.forms import UploadForm
from mod_auth.controller import login_required
from mod_auth.models import Users
from werkzeug import secure_filename
from database import db

mod_dashboard = Blueprint("mod_dashboard", __name__)


BUF_SIZE = 65536  # reading file in 64kb chunks

@mod_dashboard.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    from flask import current_app as app
    form = UploadForm()
    if form.validate_on_submit():
        uploaded_file = request.files[form.file.name]
        if uploaded_file:
            filename = secure_filename(uploaded_file.filename)
            temp_path = os.path.join(app.config['TEMP_UPLOAD_FOLDER'], filename)
            uploaded_file.save(temp_path)
            file_hash = create_file_hash(temp_path)
            if file_exist(file_hash):
                os.remove(temp_path)
                flash('File with same hash already uploaded, the file has been made available to you for processing.', 'warning')
            else:
                size = os.path.getsize(temp_path)
                filename, extension = os.path.splitext(filename)
                file_db = UploadedFiles(original_name=filename,
                                hash=file_hash,
                                original_uploader=g.user.id,
                                extension=extension,
                                size=size,
                                parameters=form.parameters.data,
                                remark=form.remark.data)

                db.session.add(file_db)
                db.session.commit()

                file_db.user.append(g.user)
                db.session.commit()

                os.rename(temp_path, os.path.join(app.config['TEMP_UPLOAD_FOLDER'] + file_hash + extension))
                flash('File uploaded.', 'success')
                return redirect(url_for('mod_auth.profile'))
    return render_template('mod_dashboard/upload.html', form=form, accept=form.accept)

def create_file_hash(path):
    hash = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            hash.update(data)
    return hash.hexdigest()

def file_exist(file_hash):
    file = UploadedFiles.query.filter(UploadedFiles.hash == file_hash).first()
    if file is None:
        return False
    else:
        users_with_file_access = Users.query.filter(Users.files.any(id=file.id)).all()
        if g.user not in users_with_file_access:
            file.user.append(g.user)
            db.session.commit()
        return True
