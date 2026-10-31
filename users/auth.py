import re # re is used to check the shape of an email address.

# Flask tools for routes, requests, pages, messages, JSON, redirects, and sessions.
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
# Werkzeug hashes passwords for storage and checks a password at login.
from werkzeug.security import check_password_hash, generate_password_hash

from users import db # db is how we talk to the MySQL database.
from users.models import Account, Customer # These are the tables we use here.

# A Blueprint groups related routes. Its name is used in url_for, like auth.login.
auth = Blueprint('auth', __name__)
# This pattern accepts a simple email shape such as name@example.com.
Email_Pattern = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
# Registration accepts only addresses from these email provider domains.
Allowed_Emails = {
    'gmail.com', 'googlemail.com',
    'outlook.com', 'hotmail.com', 'live.com', 'msn.com',
    'yahoo.com', 'yahoo.co.uk', 'yahoo.ca', 'yahoo.com.au', 'ymail.com', 'rocketmail.com',
    'icloud.com', 'me.com', 'mac.com',
    'aol.com', 'proton.me', 'protonmail.com', 'gmx.com', 'gmx.net', 'mail.com',
    'zoho.com', 'fastmail.com', 'hey.com', 'tuta.com', 'tutanota.com', 'yandex.com', 'yandex.ru', 'lu.edu.ph', 'deped.gov.ph',
}


# Check the email shape and whether its domain is in the allowed list.
def _is_valid_email(email):
    if not isinstance(email, str) or len(email) > 100 or not Email_Pattern.fullmatch(email):
        return False
    # Get the part after @ and make it lowercase.
    domain = email.rsplit('@', 1)[1].lower().rstrip('.')
    return domain in Allowed_Emails


# Return an error message for the first invalid field. Return None if everything is fine.
def _registration_error(name, email, password, confirmation):
    if not name or not email or not password or not confirmation:
        return 'Please fill in every field.'
    # No spaces at the start or end, no double spaces, and at most 50 characters.
    if name != name.strip() or '  ' in name or len(name) > 50:
        return 'Enter your full name using single spaces, with no spaces at the beginning or end.'
    parts = name.split(' ')  # Break the full name into words.
    # Need a first and last name, each with letters only.
    if len(parts) < 2 or not parts[0].isalpha() or not parts[-1].isalpha():
        return 'Enter your first and last name using letters.'
    if not _is_valid_email(email):
        return 'Enter an email address from a supported provider, such as Gmail, Outlook, Yahoo, or iCloud.'
    if any(character.isspace() for character in password):
        return "Spaces aren't allowed in passwords."
    if len(password) < 8:
        return 'Your password must be at least 8 characters long.'
    if not any(character.isalpha() for character in password):
        return 'Your password must include at least one letter.'
    if not any(character.isdigit() for character in password):
        return 'Your password must include at least one number.'
    if not any(not character.isalnum() for character in password):
        return 'Your password must include at least one special character.'
    if password != confirmation:
        return 'The passwords do not match.'
    return None  # None means every check passed.


# This connects the function to GET /login and POST /login.
@auth.route('/login', methods=('GET', 'POST'))
def login():
    # A signed-in user should not see the login form again.
    if 'user_id' in session:
        role = session.get('user_role')
        if role == 'customer':
            return redirect(url_for('customer_bp.printshops'))
        if role == 'staff':
            return redirect(url_for('staff_bp.index'))
        if role == 'admin':
            return redirect(url_for('admin_bp.index'))
        return redirect(url_for('customer_bp.index'))

    # GET shows the form. POST means the form was submitted.
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Look for an account with this email in the accounts table.
        account = Account.query.filter_by(email=email).first()

        # Show an error if there is no account or the password is wrong.
        if account is None or not check_password_hash(account.password_hash, password):
            flash('Email or password is incorrect.', 'error')
        else:
            session.clear()  # Remove any old session information.
            session['user_id'] = account.id
            session['user_name'] = account.full_name
            session['user_role'] = account.role
            flash('Welcome back!', 'success')
            if account.role == 'customer':
                return redirect(url_for('customer_bp.printshops'))
            return redirect(url_for('customer_bp.index'))
    return render_template('auth/login.html')


# This connects the function to GET /register and POST /register.
@auth.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        name = request.form.get('name', '')
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirmation = request.form.get('confirm_password', '')
        error = _registration_error(name, email, password, confirmation)

        if error:
            flash(error, 'error')
        else:
            # Check if the email is already used.
            old_account = Account.query.filter_by(email=email).first()
            if old_account is not None:
                flash('That email address is already in use.', 'error')
            else:
                # Make the account row. We save a hash, never the real password.
                new_account = Account(
                    full_name=name,
                    email=email,
                    password_hash=generate_password_hash(password),
                    role='customer',
                )
                db.session.add(new_account)
                db.session.commit()  # After this, new_account.id has a value.

                # Make the matching customer row, linked by the account id.
                new_customer = Customer(account_id=new_account.id)
                db.session.add(new_customer)
                db.session.commit()

                flash('Your account is ready. You can log in now.', 'success')
                return redirect(url_for('auth.login'))
    return render_template('auth/register.html')


# Logout only accepts POST so a link can't log someone out by accident.
@auth.route('/logout', methods=('POST',))
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('customer_bp.index'))


# The register page JavaScript sends an email here for a quick check.
@auth.route('/check-email', methods=('POST',))
def check_email():
    payload = request.get_json(silent=True) or {}
    email = payload.get('email', '') if isinstance(payload, dict) else ''
    valid = _is_valid_email(email)
    return jsonify({'valid': bool(valid)})