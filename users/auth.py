import json # json reads and writes the users.json account file.
import os # os handles folders and file paths.
import re # re provides regular-expression support for email checks.
import tempfile # tempfile creates a temporary file so saved data can be replaced safely.
import threading # threading provides a lock to coordinate simultaneous requests in this process.
import uuid # uuid creates unique IDs for newly registered users.

# Flask tools used to define routes, read requests, render pages, display messages,
# return JSON, redirect browsers, and store signed-in user data in sessions.
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
# Werkzeug hashes passwords for storage and verifies a submitted password later.
from werkzeug.security import check_password_hash, generate_password_hash

# A Blueprint groups related Flask routes. Its name appears in endpoint names like auth.login.
auth = Blueprint('auth', __name__)
# A lock prevents two requests in this Python process from changing users.json at once.
users_lock = threading.Lock()
# This pattern accepts a simple email shape such as name@example.com.
Email_Pattern = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
# Registration accepts only addresses from these known email provider domains.
Allowed_Emails = {
    'gmail.com', 'googlemail.com',
    'outlook.com', 'hotmail.com', 'live.com', 'msn.com',
    'yahoo.com', 'yahoo.co.uk', 'yahoo.ca', 'yahoo.com.au', 'ymail.com', 'rocketmail.com',
    'icloud.com', 'me.com', 'mac.com',
    'aol.com', 'proton.me', 'protonmail.com', 'gmx.com', 'gmx.net', 'mail.com',
    'zoho.com', 'fastmail.com', 'hey.com', 'tuta.com', 'tutanota.com', 'yandex.com', 'yandex.ru',
}


# Build and return the path to this app's account JSON file.
def users_file():
    # Ensure Flask's instance folder exists; exist_ok avoids an error if it already does.
    os.makedirs(current_app.instance_path, exist_ok=True)
    # Keep user data in instance/users.json, separate from the Python source files.
    return os.path.join(current_app.instance_path, 'users.json')


# Read every account from the JSON file and return a Python list.
def load_users():
    path = users_file()  # Get the file path and create its parent folder if needed.
    if not os.path.exists(path):  # If no one has registered yet, there are no accounts.
        return []

    try:
        # 'r' means read mode; UTF-8 is the text encoding; json.load parses the file.
        with open(path, 'r', encoding='utf-8') as json_file:
            users = json.load(json_file)
    # Report missing/unreadable files or invalid JSON instead of silently losing accounts.
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError('The local user file could not be read. Preserve it and check its contents.') from error

    # The top-level value should be a list, with one dictionary per user.
    if not isinstance(users, list):
        raise RuntimeError('The local user file has an invalid format. Preserve it and check its contents.')
    return users  # Return the parsed list to the caller.


# Save the supplied list of account records to users.json.
def _save_users(users):
    path = users_file()  # Destination path for the permanent JSON file.
    temp_path = None  # This will hold the temporary file's path for cleanup.
    try:
        # Write beside users.json so os.replace can swap files safely on the same drive.
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', newline='\n', dir=current_app.instance_path,
            prefix='users-', suffix='.tmp', delete=False,
        ) as temp_file:
            temp_path = temp_file.name  # Remember the temporary file's path.
            # Convert Python values into readable JSON text; indent adds formatting.
            json.dump(users, temp_file, ensure_ascii=False, indent=2)
            temp_file.write('\n')  # Add a final newline for readability.
        os.replace(temp_path, path)  # Replace users.json only after the full new file is written.
    finally:
        # If saving failed, remove any temporary file left behind.
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# Check both email syntax and whether its domain is in the allowed-provider list.
def _is_valid_email(email):
    # Reject non-text input, addresses over 100 characters, and strings that don't match the pattern.
    if not isinstance(email, str) or len(email) > 100 or not Email_Pattern.fullmatch(email):
        return False
    # Get the part after @, lowercase it, and remove a trailing dot if there is one.
    domain = email.rsplit('@', 1)[1].lower().rstrip('.')
    # 'in' checks whether this domain appears in Allowed_Emails above.
    return domain in Allowed_Emails


# Return an error message for the first invalid registration field; return None if all pass.
def _registration_error(name, email, password, confirmation):
    # Empty strings are false in Python; this checks that every required value was submitted.
    if not name or not email or not password or not confirmation:
        return 'Please fill in every field.'
    # Reject leading/trailing spaces, repeated spaces, and names longer than 50 characters.
    if name != name.strip() or '  ' in name or len(name) > 50:
        return 'Enter your full name using single spaces, with no spaces at the beginning or end.'
    parts = name.split(' ')  # Break the full name into separate words.
    # Require at least a first and last name, each containing letters only.
    if len(parts) < 2 or not parts[0].isalpha() or not parts[-1].isalpha():
        return 'Enter your first and last name using letters.'
    # Reuse the same syntax and provider checks used by the live email-check route.
    if not _is_valid_email(email):
        return 'Enter an email address from a supported provider, such as Gmail, Outlook, Yahoo, or iCloud.'
    # A password cannot contain whitespace such as spaces or tabs.
    if any(character.isspace() for character in password):
        return "Spaces aren't allowed in passwords."
    if len(password) < 8:  # Require at least eight characters.
        return 'Your password must be at least 8 characters long.'
    if not any(character.isalpha() for character in password):  # Require at least one letter.
        return 'Your password must include at least one letter.'
    if not any(character.isdigit() for character in password):  # Require at least one number.
        return 'Your password must include at least one number.'
    if not any(not character.isalnum() for character in password):  # Require a punctuation mark or symbol.
        return 'Your password must include at least one special character.'
    if password != confirmation:  # Catch a typo in the repeated-password field.
        return 'The passwords do not match.'
    return None  # None means every validation check passed.


# This decorator connects the function to GET /login and POST /login.
@auth.route('/login', methods=('GET', 'POST'))
def login():
    # GET displays the form; POST means the form was submitted.
    if request.method == 'POST':
        # Read the email, remove surrounding spaces, and lowercase it for consistent matching.
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')  # Do not trim passwords; their contents matter.
        # Hold the lock while loading accounts so a write cannot happen at the same time.
        with users_lock:
            users = load_users()
        # Find the matching account; next(..., None) returns None if no account matches.
        user = next((item for item in users if item.get('email') == email), None)

        # Reject a missing account or a password that does not match the saved hash.
        if user is None or not check_password_hash(user.get('password_hash', ''), password):
            flash('Email or password is incorrect.', 'error')  # Show a one-time error on the page.
        else:
            # session management: Clear any old session, then store the logged-in user’s ID, name, and role.
            session.clear()  # Remove any old user's session information.
            session['user_id'] = user['id']  # Store the account ID in Flask's signed session.
            session['user_name'] = user['name']  # Used for the greeting in the navigation bar.
            session['user_role'] = user['role']  # Saved for role-based features.
            flash('Welcome back!', 'success')
            return redirect(url_for('customer_bp.index'))  # Go to the customer home page.
    # Display the login template on first visit or after an unsuccessful login.
    return render_template('auth/login.html')


# This decorator connects the function to GET /register and POST /register.
@auth.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':  # Only process account data after the form is submitted.
        name = request.form.get('name', '')  # Read the full name, or use empty text if missing.
        email = request.form.get('email', '').strip().lower()  # Normalize email for duplicate checks.
        password = request.form.get('password', '')
        confirmation = request.form.get('confirm_password', '')
        error = _registration_error(name, email, password, confirmation)  # Run server-side validation.

        if error:  # A non-empty error string means a validation rule failed.
            flash(error, 'error')
        else:
            # Keep the duplicate check and save together to avoid same-process races.
            with users_lock:
                users = load_users()  # Read the existing account records.
                if any(item.get('email') == email for item in users):  # True if this email is already taken.
                    flash('That email address is already in use.', 'error')
                else:
                    # Add a new record; the raw password is never written to JSON.
                    users.append({
                        'id': str(uuid.uuid4()),  # Generate a unique account ID.
                        'name': name,
                        'email': email,
                        'password_hash': generate_password_hash(password),  # Save a one-way hash, not the password.
                        'role': 'customer',  # Public registration creates customer accounts.
                    })
                    _save_users(users)  # Persist the updated list in users.json.
                    flash('Your account is ready. You can log in now.', 'success')
                    return redirect(url_for('auth.login'))  # Send the user to the login page.
    # Display the form on first visit or when submitted data failed validation.
    return render_template('auth/register.html')


# session management: The logout route clears the session.
# Only accept POST for logout; loading a page/link should not log someone out by accident.
@auth.route('/logout', methods=('POST',))
def logout():
    session.clear()  # Remove the current user's signed-in session data.
    flash('You have been logged out.', 'success')
    return redirect(url_for('customer_bp.index'))  # Return to the customer home page.


# The registration-page JavaScript sends an email here for an immediate format/provider check.
@auth.route('/check-email', methods=('POST',))
def check_email():
    payload = request.get_json(silent=True) or {}  # Parse JSON; use an empty dictionary if absent/invalid.
    # Read the email only when the JSON body is an object (Python represents it as a dict).
    email = payload.get('email', '') if isinstance(payload, dict) else ''
    valid = _is_valid_email(email)  # Use the same validation as account registration.
    return jsonify({'valid': bool(valid)})  # Send a JSON true/false result back to the browser.


