from datetime import timedelta

from flask import Flask, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
import os
import secrets

# Create one SQLAlchemy object for the project. The app connects it to MySQL
# inside create_app() below, and models.py uses it to define database tables.
db = SQLAlchemy()

# Use DATABASE_URL from the environment when provided; otherwise use the local
# development connection string configured for this project.
DATABASE_URL = "mysql+pymysql://printwise:printwise123@localhost/printwisedb"


def _environment_flag(name, default=False):
    """Read a true/false environment setting in a beginner-friendly format."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_production():
    """Return True when the app is intentionally running as production."""
    environment = os.environ.get('APP_ENV', os.environ.get('FLASK_ENV', 'development'))
    return environment.strip().lower() == 'production'


def _load_secret_key(app, production):
    """Use an environment secret in production and a stable local secret in development."""
    environment_secret = os.environ.get('SECRET_KEY')
    if environment_secret:
        return environment_secret

    if production:
        raise RuntimeError('SECRET_KEY must be set in the production environment.')

    # The instance folder is excluded from Git. Saving the development key here
    # keeps local sessions valid when Flask is restarted without publishing it.
    os.makedirs(app.instance_path, exist_ok=True)
    secret_file = os.path.join(app.instance_path, 'development_secret_key.txt')
    if os.path.exists(secret_file):
        with open(secret_file, 'r', encoding='utf-8') as file:
            return file.read().strip()

    new_secret = secrets.token_hex(32)
    with open(secret_file, 'w', encoding='utf-8') as file:
        file.write(new_secret)
    return new_secret

def create_app():
    # Build and configure the Flask application. The secret key signs session
    # cookies so Flask can recognize a user's session between requests.
    app = Flask(__name__)
    production = _is_production()
    app.config['SECRET_KEY'] = _load_secret_key(app, production)
    environment_database = os.environ.get('DATABASE_URL')
    if production and not environment_database:
        raise RuntimeError('DATABASE_URL must be set in the production environment.')
    app.config['SQLALCHEMY_DATABASE_URI'] = environment_database or DATABASE_URL
    # SMTP credentials are read from environment variables so passwords are
    # never committed to source control. Port 587 with TLS works for Gmail and
    # many other providers; deployments can override every setting.
    app.config['SMTP_HOST'] = os.environ.get('SMTP_HOST', '')
    app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', '587'))
    app.config['SMTP_USERNAME'] = os.environ.get('SMTP_USERNAME', '')
    app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD', '')
    app.config['SMTP_FROM_EMAIL'] = os.environ.get('SMTP_FROM_EMAIL', '')
    app.config['SMTP_USE_TLS'] = _environment_flag('SMTP_USE_TLS', True)
    app.config['SMTP_USE_SSL'] = _environment_flag('SMTP_USE_SSL', False)
    app.config['PUBLIC_BASE_URL'] = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
    app.config['EMAIL_VERIFY_MAX_AGE'] = 24 * 60 * 60
    app.config['PASSWORD_RESET_MAX_AGE'] = 60 * 60
    # Flask stores a signed session identifier in a cookie. These settings keep
    # JavaScript from reading it, restrict cross-site sending, and expire it.
    app.config['SESSION_COOKIE_NAME'] = 'printwise_session'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # Secure cookies require HTTPS, so enable this automatically in production.
    app.config['SESSION_COOKIE_SECURE'] = production
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True
    # Limit uploaded request attachments to 16 MB.
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # Attach SQLAlchemy to this Flask app so models and routes can use the DB.
    db.init_app(app)

    # Require a valid session token on all POST, PUT, PATCH, and DELETE requests.
    from users.security import init_browser_security, init_csrf
    init_browser_security(app, production)
    init_csrf(app)

    # Import the model classes before creating tables, so SQLAlchemy knows all
    # table definitions. create_all() creates missing tables; it does not alter
    # existing tables or remove columns.
    from users import models

    with app.app_context():
        db.create_all()

    @app.before_request
    def refresh_signed_in_account():
        """Reject deleted accounts and refresh role/name stored in the session."""
        # Static CSS, JavaScript, and images do not need a database lookup.
        if request.endpoint and request.endpoint.endswith('.static'):
            return None
        account_id = session.get('user_id')
        if not account_id:
            return None
        account = models.Account.query.get(account_id)
        if account is None or not account.is_active:
            session.clear()
            return None
        session['user_name'] = account.full_name
        session['user_role'] = account.role
        if account.is_customer() and account.customer:
            session['user_profile_picture'] = account.customer.profile_picture_path
        else:
            session['user_profile_picture'] = account.profile_picture_path
        return None

    # Import the route groups after the app and models are ready.
    from users.auth import auth
    from users.customer.customer import customer_bp
    from users.customer.print_requests import request_bp
    from users.staff.requests import shop_requests_bp
    from users.staff.staff import staff_bp
    from users.admin.admin import admin_bp
    from users.admin.staff_management import admin_staff_bp
    from users.admin.service_management import admin_services_bp
    from users.notifications import notifications_bp, register_notification_context

    # Register each blueprint so its routes become available in the app.
    app.register_blueprint(auth)
    app.register_blueprint(customer_bp)
    app.register_blueprint(request_bp)
    app.register_blueprint(shop_requests_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_staff_bp)
    app.register_blueprint(admin_services_bp)
    app.register_blueprint(notifications_bp)
    register_notification_context(app)
    from users.file_cleanup import register_cleanup_command
    register_cleanup_command(app)

    # Branded responses replace Flask's plain default error pages.
    @app.errorhandler(400)
    def bad_request(error):
        return render_template('errors/400.html', error=error), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def upload_too_large(error):
        return render_template('errors/413.html'), 413

    return app
