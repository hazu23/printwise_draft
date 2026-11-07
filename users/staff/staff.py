from flask import Blueprint, abort, redirect, session, url_for

staff_bp = Blueprint('staff_bp', __name__, template_folder="templates", static_folder="static", url_prefix='/staff')


@staff_bp.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    if session.get('user_role') != 'staff':
        abort(403)
    return redirect(url_for('shop_requests.inbox'))