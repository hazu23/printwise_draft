from flask import Flask
import secrets

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = secrets.token_hex(32)

    from users.auth import auth
    from users.customer.customer import customer_bp
    from users.staff.staff import staff_bp
    from users.admin.admin import admin_bp

    app.register_blueprint(auth)
    app.register_blueprint(customer_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_bp)

    return app
