"""
ccextractor-web | mod_auth/controller.py

Author   : Saurabh Shrivastava
Email    : saurabh.shrivastava54+ccextractorweb[at]gmail.com
Link     : https://github.com/saurabhshri

"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, g
from mail import send_simple_message

import hmac
import hashlib
import time

from database import db
from functools import wraps

from mod_auth.models import Users
from mod_auth.forms import SignupEmailForm, SignupForm, LoginForm

mod_auth = Blueprint("mod_auth", __name__)

@mod_auth.before_app_request
def before_app_request():
    user_id = session.get('user_id', 0)
    g.user = Users.query.filter(Users.id == user_id).first()

def generate_username(email):
    #TODO : Disallow a set of usernames such as 'admin'
    base_username = username = email.split('@')[0]
    count_suffix = 1
    while True:
        user = Users.query.filter_by(username=username).first()
        if user is not None:
            username = '{base_username}-{count_suffix}'.format(base_username=base_username, count_suffix=str(count_suffix))
            count_suffix += 1
        else:
            break

    return username

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('You need to login first.', 'error')
            return redirect(url_for('mod_auth.login', next=request.endpoint))

        return f(*args, **kwargs)

    return decorated_function


@mod_auth.route('/signup', methods=['GET', 'POST'])
def signup():

    if g.user is not None:
        flash('Currently logged in as ' + g.user.username, 'success')
        return redirect(url_for('.profile'))

    form = SignupEmailForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(email=form.email.data).first()
        if user is not None:
            flash('Email is already registered!', 'error')
            return redirect(url_for('.login'))
        else:
            expires = int(time.time()) + 86400
            verification_code = generate_verification_code(
                "{email}{expires}".format(email=form.email.data, expires=expires))
            send_verification_mail(form.email.data, verification_code, expires)
            flash('Please check your email for verification and further instructions.', 'success')
    return render_template("mod_auth/signup.html", form=form)


def generate_verification_code(data):
    from flask import current_app as app
    key = app.config.get('HMAC_KEY')

    key_bytes= bytes(key, 'latin-1')
    data_bytes = bytes(data, 'latin-1')

    return hmac.new(key_bytes, data_bytes , hashlib.sha256).hexdigest()

def send_verification_mail(email, verification_code, expires):

    from flask import current_app as app

    verification_url = app.config['ROOT_URL'] + '/verify'
    subject = "Please verify your email address for account activation."
    body = render_template('mod_auth/verification_mail.html', url=verification_url, email=email,
                           verification_code=verification_code, expires=expires)
    return send_simple_message(email, subject, str(body))

@mod_auth.route('/verify/<string:email>/<string:received_verification_code>/<int:expires>', methods=['GET', 'POST'])
def verify_account(email, received_verification_code, expires):

    if g.user is not None:
        flash('Currently logged in as ' + g.user.username, 'success')
        return redirect(url_for('.profile'))

    if time.time() <= expires:

        expected_verification_code = generate_verification_code("{email}{expires}".format(email=email, expires=expires))

        if hmac.compare_digest(expected_verification_code, received_verification_code):
            flash('Verification complete! Proceed to signup.', 'success')
            user = Users.query.filter_by(email=email).first()
            if user is None:
                form = SignupForm()
                if form.validate_on_submit():
                    user = Users(username=generate_username(email),
                                 email=email,
                                 password=form.password.data,
                                 name=form.name.data)
                    db.session.add(user)
                    db.session.commit()

                    send_signup_confirmation_mail(user.email)

                    flash('Signup Complete! Please Login to continue.', 'success')
                else:
                    return render_template("mod_auth/verify.html", form=form, email=email)
            else:
                flash('Email is already registered!', 'error')
            return redirect(url_for('.login'))

        flash('Verification failed! Incorrect email address/verification code. Please try again.', 'error-message')
    else:
        flash('The verification link is expired. Please try again.', 'error-message')

    return redirect(url_for('.signup'))


def send_signup_confirmation_mail(email):
    subject = "Account creation successful!"
    body = render_template('mod_auth/signup_confirmation.html')
    return send_simple_message(email, subject, str(body))

@mod_auth.route('/login', methods=['GET', 'POST'])
def login():
    user_id = session.get('user_id', 0)
    g.user = Users.query.filter(Users.id == user_id).first()

    redirect_location = request.args.get('next', '')

    if g.user is not None:
        print(g.user.username)
        flash('Logged in as ' + g.user.username, 'success')
        if len(redirect_location) == 0:
            return redirect(url_for('.profile'))

        else:
            return redirect(url_for(redirect_location))

    form = LoginForm(request.form)

    if form.validate_on_submit():
        user = Users.query.filter_by(email=form.email.data).first()
        if user and user.is_password_valid(form.password.data):
            session['user_id'] = user.id
            if len(redirect_location) == 0:
                return redirect(url_for('.profile'))
            else:
                return redirect(url_for(redirect_location))
        else:
            flash('Wrong username or password', 'error')

        return redirect(url_for('.login'))

    return render_template("mod_auth/login.html", form=form, next=redirect_location)


@mod_auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    files = g.user.files
    return render_template("mod_auth/profile.html", user=g.user, files=files)

@mod_auth.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('.login'))
