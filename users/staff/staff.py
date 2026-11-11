import os

from flask import (
    Blueprint, abort, current_app, redirect, render_template,
    send_from_directory, url_for,
)

from users.shop_helpers import account_printshop, signed_in_shop_worker

staff_bp = Blueprint('staff_bp', __name__, template_folder="templates", static_folder="static", url_prefix='/staff')

@staff_bp.route('/')
def index():
    account = signed_in_shop_worker()
    if account is None:
        return redirect(url_for('auth.login'))
    return redirect(url_for('shop_requests.inbox'))


@staff_bp.route('/printshop-profile')
def printshop_profile():
    """Show staff a read-only view of their assigned printshop."""
    account = signed_in_shop_worker()
    if account is None:
        return redirect(url_for('auth.login'))
    if account.has_role('admin'):
        return redirect(url_for('admin_bp.printshop_profile'))

    shop = account_printshop(account)
    if shop is None:
        return render_template('staff/printshop_profile.html', shop=None, services=[])

    return render_template('staff/printshop_profile.html', shop=shop, services=shop.active_services())


@staff_bp.route('/printshop-profile/payment-qr/<slot>')
def view_payment_qr(slot):
    """Show the shop's payment QR only to its authorized staff and admin."""
    account = signed_in_shop_worker()
    if account is None:
        return redirect(url_for('auth.login'))
    shop = account_printshop(account)
    if shop is None:
        abort(404)
    if slot == 'primary':
        qr_path = shop.payment_qr_path
    elif slot == 'secondary':
        qr_path = shop.payment_qr_2_path
    else:
        abort(404)
    if not qr_path:
        abort(404)
    filename = os.path.basename(qr_path.replace('\\', '/'))
    folder = os.path.join(current_app.instance_path, 'payment_qr_codes')
    return send_from_directory(folder, filename, as_attachment=False)
