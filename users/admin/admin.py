from flask import Blueprint, render_template

admin_bp = Blueprint('admin_bp', __name__, template_folder="templates", static_folder="static", url_prefix='/admin')

@admin_bp.route('/')
def index():
    return render_template("admin_dashboard.html")