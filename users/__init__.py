from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
import secrets

db = SQLAlchemy()

DATABASE_URL = "mysql+pymysql://printwise:printwise123@localhost/printwisedb"

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = secrets.token_hex(32)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", DATABASE_URL)
    db.init_app(app)

    from users import models

    with app.app_context():
        db.create_all()

    from users.auth import auth
    from users.customer.customer import customer_bp
    from users.staff.staff import staff_bp
    from users.admin.admin import admin_bp

    app.register_blueprint(auth)
    app.register_blueprint(customer_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_bp)

    return app