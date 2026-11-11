import os

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from users import db
from users.models import Account
from users.shop_helpers import account_printshop, save_image

admin_bp = Blueprint('admin_bp', __name__, template_folder="templates", static_folder="static", url_prefix='/admin')


@admin_bp.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    if session.get('user_role') != 'admin':
        abort(403)
    return redirect(url_for('shop_requests.inbox'))


def _admin_account():
    """Return the signed-in admin or stop access by another role."""
    if not session.get('user_id'):
        return None
    account = Account.query.get(session['user_id'])
    if account is None or not account.has_role('admin'):
        abort(403)
    return account


def _show_profile(shop):
    """Render the shared profile view with admin editing controls enabled."""
    services = shop.active_services() if shop else []
    return render_template('staff/printshop_profile.html', shop=shop, services=services)


@admin_bp.route('/printshop-profile', methods=('GET', 'POST'))
def printshop_profile():
    """Let an admin view and customize their printshop profile."""
    account = _admin_account()
    if account is None:
        return redirect(url_for('auth.login'))
    shop = account_printshop(account)
    if shop is None or request.method == 'GET':
        return _show_profile(shop)

    if request.form.get('remove_logo') == '1':
        if shop.logo_path:
            shop.logo_path = None
            db.session.commit()
            flash('Printshop profile picture removed.', 'success')
        else:
            flash('This printshop does not have a profile picture.', 'error')
        return redirect(url_for('admin_bp.printshop_profile'))

    remove_qr = request.form.get('remove_payment_qr')
    if remove_qr in {'primary', 'secondary'}:
        if remove_qr == 'primary':
            had_qr = bool(shop.payment_qr_path)
            shop.payment_qr_path = None
        else:
            had_qr = bool(shop.payment_qr_2_path)
            shop.payment_qr_2_path = None
        db.session.commit()
        flash(
            'Payment QR image removed.' if had_qr else 'No QR image was configured for that option.',
            'success' if had_qr else 'error',
        )
        return redirect(url_for('admin_bp.printshop_profile'))

    clear_details = request.form.get('clear_payment_details')
    if clear_details in {'primary', 'secondary'}:
        if clear_details == 'primary':
            had_details = bool(shop.payment_account_name or shop.payment_account_number)
            shop.payment_account_name = None
            shop.payment_account_number = None
        else:
            had_details = bool(shop.payment_qr_2_account_name or shop.payment_qr_2_account_number)
            shop.payment_qr_2_account_name = None
            shop.payment_qr_2_account_number = None
        db.session.commit()
        flash(
            'Digital wallet account details cleared.' if had_details else 'No account details were saved for that option.',
            'success' if had_details else 'error',
        )
        return redirect(url_for('admin_bp.printshop_profile'))

    shop.name = request.form.get('name', '').strip()
    shop.description = request.form.get('description', '').strip() or None
    shop.location = request.form.get('location', '').strip()
    shop.contact_phone = request.form.get('contact_phone', '').strip() or None
    shop.contact_email = request.form.get('contact_email', '').strip() or None
    shop.website = request.form.get('website', '').strip() or None
    shop.business_hours = request.form.get('business_hours', '').strip() or None
    if not shop.name or not shop.location:
        flash('Printshop name and location are required.', 'error')
        return _show_profile(shop)

    logo = request.files.get('logo')
    if logo is not None and logo.filename:
        logo_folder = os.path.join(current_app.root_path, 'customer', 'static', 'images', 'printshops')
        saved_logo = save_image(logo, logo_folder, 'images/printshops')
        if saved_logo is None:
            flash('The logo must be a JPG or PNG image.', 'error')
            return _show_profile(shop)
        shop.logo_path = saved_logo

    qr_folder = os.path.join(current_app.instance_path, 'payment_qr_codes')
    qr_upload = request.files.get('payment_qr')
    qr_name = request.form.get('payment_qr_name', '').strip()
    if qr_upload is not None and qr_upload.filename:
        if not qr_name:
            flash('Enter a payment QR name, such as GCash or Maya.', 'error')
            return _show_profile(shop)
        shop.payment_qr_path = save_image(qr_upload, qr_folder, 'payment_qr_codes')
        if shop.payment_qr_path is None:
            flash('The payment QR must be a JPG or PNG image.', 'error')
            return _show_profile(shop)
    if shop.payment_qr_path:
        if not qr_name:
            flash('The configured payment QR needs a name.', 'error')
            return _show_profile(shop)
        shop.payment_qr_name = qr_name[:50]
    shop.payment_account_name = request.form.get('payment_account_name', '').strip()[:100] or None
    shop.payment_account_number = request.form.get('payment_account_number', '').strip()[:30] or None

    second_upload = request.files.get('payment_qr_2')
    second_name = request.form.get('payment_qr_2_name', '').strip()
    if second_upload is not None and second_upload.filename:
        if not second_name:
            flash('Enter a name for the second payment QR.', 'error')
            return _show_profile(shop)
        shop.payment_qr_2_path = save_image(second_upload, qr_folder, 'payment_qr_codes')
        if shop.payment_qr_2_path is None:
            flash('The second payment QR must be a JPG or PNG image.', 'error')
            return _show_profile(shop)
    if shop.payment_qr_2_path:
        if not second_name:
            flash('The second payment QR needs a service name.', 'error')
            return _show_profile(shop)
        shop.payment_qr_2_name = second_name[:50]
    shop.payment_qr_2_account_name = request.form.get('payment_qr_2_account_name', '').strip()[:100] or None
    shop.payment_qr_2_account_number = request.form.get('payment_qr_2_account_number', '').strip()[:30] or None

    db.session.commit()
    flash('Printshop profile updated.', 'success')
    return redirect(url_for('admin_bp.printshop_profile'))
