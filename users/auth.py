import re # re is used to check the shape of an email address.
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from users import db # db is how we talk to the mysql database.
from users.email_service import AccountTokenService, EmailDeliveryError, EmailService
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


def is_valid_email(email):
    """Public email check reused by customer profile editing."""
    return _is_valid_email(email)


def _password_error(password, confirmation):
    """Return the first password validation error, or None when it is valid."""
    if not password or not confirmation:
        return 'Enter and confirm your password.'
    if len(password) > 128:
        return 'Your password is too long.'
    if any(character.isspace() for character in password):
        return "Spaces aren't allowed in passwords."
    if len(password) < 8:
        return 'Your password must be at least 8 characters long.'
    if not any(character.isalpha() for character in password):
        return 'Your password must include at least one letter.'
    if not any(character.isdigit() for character in password):
        return 'Your password must include at least one number.'
    if password != confirmation:
        return 'The passwords do not match.'
    return None


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
    return _password_error(password, confirmation)


def _token_service():
    """Create the signed-link helper using this application's secret key."""
    return AccountTokenService(current_app.config['SECRET_KEY'])


def _public_url(endpoint, **values):
    """Build a deployed URL when configured, or use the current request host."""
    path = url_for(endpoint, _external=False, **values)
    public_base_url = current_app.config.get('PUBLIC_BASE_URL', '')
    return f'{public_base_url}{path}' if public_base_url else url_for(
        endpoint, _external=True, **values
    )


def _send_verification_email(account):
    """Email a 24-hour verification link to one new account."""
    token = _token_service().create_verification_token(account)
    verification_url = _public_url('auth.verify_email', token=token)
    body = (
        f'Hello {account.full_name},\n\n'
        'Welcome to PrintWise. Verify your email address by opening this link:\n\n'
        f'{verification_url}\n\n'
        'This link expires in 24 hours. If you did not create this account, '
        'you can ignore this email.\n'
    )
    EmailService(current_app).send(
        account.email,
        'Verify your PrintWise account',
        body,
    )


def _send_password_reset_email(account):
    """Email a one-hour password reset link without sending any password."""
    token = _token_service().create_password_reset_token(account)
    reset_url = _public_url('auth.reset_password', token=token)
    body = (
        f'Hello {account.full_name},\n\n'
        'A password reset was requested for your PrintWise account. '
        'Open this link to choose a new password:\n\n'
        f'{reset_url}\n\n'
        'This link expires in one hour and stops working after your password '
        'is changed. If you did not request this, you can ignore this email.\n'
    )
    EmailService(current_app).send(
        account.email,
        'Reset your PrintWise password',
        body,
    )


# This connects the function to GET /login and POST /login.
@auth.route('/login', methods=('GET', 'POST'))
def login():
    # A signed-in user should not see the login form again.
    if 'user_id' in session:
        signed_in_account = Account.query.get(session['user_id'])
        if signed_in_account:
            return redirect(url_for(signed_in_account.home_endpoint()))
        session.clear()

    # GET shows the form. POST means the form was submitted.
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Look for an account with this email in the accounts table.
        account = Account.query.filter_by(email=email).first()

        # Show an error if there is no account or the password is wrong.
        if account is None or not check_password_hash(account.password_hash, password):
            flash('Email or password is incorrect.', 'error')
        elif not account.is_active:
            flash('This account has been deactivated. Contact your printshop administrator.', 'error')
        elif not account.email_verified:
            flash('Verify your email address before logging in.', 'error')
            return redirect(url_for('auth.resend_verification', email=email))
        else:
            session.clear()  # Remove any old session information.
            session['user_id'] = account.id
            session['user_name'] = account.full_name
            session['user_role'] = account.role
            session['user_profile_picture'] = (
                account.customer.profile_picture_path
                if account.is_customer() and account.customer
                else account.profile_picture_path
            )
            # Keep the signed-in session for up to the configured eight hours.
            session.permanent = True
            flash('Welcome back!', 'success')
            return redirect(url_for(account.home_endpoint()))
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
                    email_verified=False,
                )
                db.session.add(new_account)
                db.session.flush()  # After this, new_account.id has a value.
                new_customer = Customer(account_id=new_account.id)
                db.session.add(new_customer)
                db.session.commit()

                try:
                    _send_verification_email(new_account)
                    flash('Account created. Check your email for the verification link.', 'success')
                except EmailDeliveryError:
                    current_app.logger.exception('Could not send account verification email.')
                    flash('Your account was created, but the verification email could not be sent. Try resending it.', 'error')
                return redirect(url_for('auth.resend_verification', email=email))
    return render_template('auth/register.html')


@auth.route('/verify-email/<token>')
def verify_email(token):
    """Verify a new account using its signed, expiring email link."""
    token_data = _token_service().read_verification_token(
        token,
        current_app.config['EMAIL_VERIFY_MAX_AGE'],
    )
    account = Account.query.get(token_data.get('account_id')) if token_data else None
    if account is None or account.email != token_data.get('email'):
        flash('That verification link is invalid or has expired.', 'error')
        return redirect(url_for('auth.resend_verification'))

    if not account.email_verified:
        account.email_verified = True
        db.session.commit()
    flash('Your email is verified. You can log in now.', 'success')
    return redirect(url_for('auth.login'))


@auth.route('/resend-verification', methods=('GET', 'POST'))
def resend_verification():
    """Send another verification email without revealing unknown accounts."""
    email = request.values.get('email', '').strip().lower()
    if request.method == 'POST':
        account = Account.query.filter_by(email=email).first()
        if account and account.is_active and not account.email_verified:
            try:
                _send_verification_email(account)
            except EmailDeliveryError:
                current_app.logger.exception('Could not resend verification email.')
        flash('If that account still needs verification, a new email has been sent.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/resend_verification.html', email=email)


@auth.route('/forgot-password', methods=('GET', 'POST'))
def forgot_password():
    """Email a password reset link while preventing account enumeration."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        account = Account.query.filter_by(email=email).first()
        if account and account.is_active:
            try:
                _send_password_reset_email(account)
            except EmailDeliveryError:
                current_app.logger.exception('Could not send password reset email.')
        flash('If an active account uses that email, a reset link has been sent.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html')


@auth.route('/reset-password/<token>', methods=('GET', 'POST'))
def reset_password(token):
    """Let the owner of a valid one-hour link choose a new password."""
    token_service = _token_service()
    token_data = token_service.read_password_reset_token(
        token,
        current_app.config['PASSWORD_RESET_MAX_AGE'],
    )
    account = Account.query.get(token_data.get('account_id')) if token_data else None
    if (
        account is None
        or not account.is_active
        or not token_service.password_token_matches(account, token_data)
    ):
        flash('That password reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirmation = request.form.get('confirm_password', '')
        error = _password_error(password, confirmation)
        if error:
            flash(error, 'error')
        else:
            account.password_hash = generate_password_hash(password)
            db.session.commit()
            session.clear()
            flash('Your password has been changed. You can log in now.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html')


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
