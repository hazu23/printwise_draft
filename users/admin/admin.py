import os
import re
from datetime import datetime
from urllib.parse import urlparse

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from users import db
from users.models import Account
from users.shop_helpers import account_printshop, save_image

admin_bp = Blueprint('admin_bp', __name__, template_folder="templates", static_folder="static", url_prefix='/admin')

CONTACT_EMAIL_PATTERN = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+')
PHONE_PATTERN = re.compile(r'[0-9+()\- ]{7,30}')
ACCOUNT_NUMBER_PATTERN = re.compile(r'[0-9+()\- ]{4,30}')


def _safe_website_url(value):
    """Return a normalized HTTP(S) URL, or None when it is unsafe."""
    if not value:
        return None
    raw_parsed = urlparse(value)
    if raw_parsed.scheme and raw_parsed.scheme.lower() not in {'http', 'https'}:
        return None
    candidate = value if re.match(r'^https?://', value, re.IGNORECASE) else f'https://{value}'
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {'http', 'https'} or not parsed.hostname:
        return None
    if parsed.username or parsed.password or len(candidate) > 255:
        return None
    return candidate


@admin_bp.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    if session.get('user_role') != 'admin':
        abort(403)
    return redirect(url_for('staff_bp.dashboard'))


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

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    location = request.form.get('location', '').strip()
    contact_phone = request.form.get('contact_phone', '').strip()
    contact_email = request.form.get('contact_email', '').strip().lower()
    website_input = request.form.get('website', '').strip()
    safe_website = _safe_website_url(website_input)
    if not name or not location:
        flash('Printshop name and location are required.', 'error')
        return _show_profile(shop)
    if len(name) > 120 or len(location) > 255 or len(description) > 4000:
        flash('One of the printshop text fields is too long.', 'error')
        return _show_profile(shop)
    if contact_phone and not PHONE_PATTERN.fullmatch(contact_phone):
        flash('Enter a valid contact phone number.', 'error')
        return _show_profile(shop)
    if contact_email and (len(contact_email) > 255 or not CONTACT_EMAIL_PATTERN.fullmatch(contact_email)):
        flash('Enter a valid printshop email address.', 'error')
        return _show_profile(shop)
    if website_input and safe_website is None:
        flash('Enter a valid HTTP or HTTPS website address.', 'error')
        return _show_profile(shop)

    shop.name = name
    shop.description = description or None
    shop.location = location
    shop.contact_phone = contact_phone or None
    shop.contact_email = contact_email or None
    shop.website = safe_website
    shop.temporarily_closed = request.form.get('temporarily_closed') == '1'
    opening_text = request.form.get('opening_time', '').strip()
    closing_text = request.form.get('closing_time', '').strip()
    if bool(opening_text) != bool(closing_text):
        flash('Enter both the opening and closing time.', 'error')
        return _show_profile(shop)
    try:
        shop.opening_time = datetime.strptime(opening_text, '%H:%M').time() if opening_text else None
        shop.closing_time = datetime.strptime(closing_text, '%H:%M').time() if closing_text else None
    except ValueError:
        flash('Choose valid opening and closing times.', 'error')
        return _show_profile(shop)
    shop.business_hours = shop.opening_status()['details']

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
    payment_account_name = request.form.get('payment_account_name', '').strip()
    payment_account_number = request.form.get('payment_account_number', '').strip()
    if len(qr_name) > 50 or len(payment_account_name) > 100:
        flash('The first payment option contains text that is too long.', 'error')
        return _show_profile(shop)
    if payment_account_number and not ACCOUNT_NUMBER_PATTERN.fullmatch(payment_account_number):
        flash('Enter a valid first payment account number.', 'error')
        return _show_profile(shop)
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
        shop.payment_qr_name = qr_name
    shop.payment_account_name = payment_account_name or None
    shop.payment_account_number = payment_account_number or None

    second_upload = request.files.get('payment_qr_2')
    second_name = request.form.get('payment_qr_2_name', '').strip()
    second_account_name = request.form.get('payment_qr_2_account_name', '').strip()
    second_account_number = request.form.get('payment_qr_2_account_number', '').strip()
    if len(second_name) > 50 or len(second_account_name) > 100:
        flash('The second payment option contains text that is too long.', 'error')
        return _show_profile(shop)
    if second_account_number and not ACCOUNT_NUMBER_PATTERN.fullmatch(second_account_number):
        flash('Enter a valid second payment account number.', 'error')
        return _show_profile(shop)
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
        shop.payment_qr_2_name = second_name
    shop.payment_qr_2_account_name = second_account_name or None
    shop.payment_qr_2_account_number = second_account_number or None

    db.session.commit()
    flash('Printshop profile updated.', 'success')
    return redirect(url_for('admin_bp.printshop_profile'))
