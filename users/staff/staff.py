from flask import Blueprint, render_template

staff_bp = Blueprint('staff_bp', __name__, template_folder="templates", static_folder="static", url_prefix='/staff')

@staff_bp.route('/')
def index():
    return render_template("staff_dashboard.html")