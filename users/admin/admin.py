from flask import Blueprint, abort, redirect, session, url_for

admin_bp = Blueprint('admin_bp', __name__, template_folder="templates", static_folder="static", url_prefix='/admin')


@admin_bp.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    if session.get('user_role') != 'admin':
        abort(403)
    return redirect(url_for('shop_requests.inbox'))
