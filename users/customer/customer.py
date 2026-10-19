from flask import Blueprint, render_template

customer_bp = Blueprint('customer_bp', __name__, template_folder="templates", static_folder="static", static_url_path="/users/customer/static")

@customer_bp.route('/')
def index():
    return render_template("index.html")