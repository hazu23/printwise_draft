from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
import secrets

# Create one SQLAlchemy object for the project. The app connects it to MySQL
# inside create_app() below, and models.py uses it to define database tables.
db = SQLAlchemy()

# Use DATABASE_URL from the environment when provided; otherwise use the local
# development connection string configured for this project.
DATABASE_URL = "mysql+pymysql://printwise:printwise123@localhost/printwisedb"

def create_app():
    # Build and configure the Flask application. The secret key signs session
    # cookies so Flask can recognize a user's session between requests.
    app = Flask(__name__)
    app.config['SECRET_KEY'] = secrets.token_hex(32)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", DATABASE_URL)

    # Attach SQLAlchemy to this Flask app so models and routes can use the DB.
    db.init_app(app)

    # Import the model classes before creating tables, so SQLAlchemy knows all
    # table definitions. create_all() creates missing tables; it does not alter
    # existing tables or remove columns.
    from users import models

    with app.app_context():
        db.create_all()

    # Import the route groups after the app and models are ready.
    from users.auth import auth
    from users.customer.customer import customer_bp
    from users.staff.staff import staff_bp
    from users.admin.admin import admin_bp

    # Register each blueprint so its routes become available in the app.
    app.register_blueprint(auth)
    app.register_blueprint(customer_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_bp)

    return app