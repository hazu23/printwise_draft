import os
import re
from datetime import datetime, time

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    send_from_directory, session, url_for,
)

from users import db
from users.auth import is_valid_email
from users.models import Account, PrintRequest
from users.shop_helpers import account_printshop, save_image, signed_in_shop_worker

staff_bp = Blueprint('staff_bp', __name__, template_folder="templates", static_folder="static", url_prefix='/staff')

@staff_bp.route('/')
def index():
    account = signed_in_shop_worker()
    if account is None:
        return redirect(url_for('auth.login'))
    return redirect(url_for('staff_bp.dashboard'))


@staff_bp.route('/dashboard')
def dashboard():
    """Show one shared overview for staff members and printshop admins."""
    account = signed_in_shop_worker()
    if account is None:
        return redirect(url_for('auth.login'))
    shops = account.accessible_printshops()
    shop_ids = [shop.id for shop in shops]
    requests = []
    if shop_ids:
        requests = PrintRequest.query.filter(
            PrintRequest.printshop_id.in_(shop_ids),
            PrintRequest.status != 'cancelled',
        ).order_by(PrintRequest.created_at.desc(), PrintRequest.id.desc()).all()

    today_start = datetime.combine(datetime.now().date(), time.min)
    stats = {
        'pending': sum(item.status == 'pending' for item in requests),
        'printing': sum(item.status == 'in_progress' for item in requests),
        'ready': sum(item.status == 'ready' for item in requests),
        'receipts': sum(item.payment_status == 'for_verification' for item in requests),
        'today': sum(item.created_at and item.created_at >= today_start for item in requests),
    }
    page_shop_name = (
        shops[0].name if len(shops) == 1
        else ('All managed printshops' if shops else 'No printshop assigned')
    )
    return render_template(
        'staff/dashboard.html', account=account, shops=shops,
        page_shop_name=page_shop_name, stats=stats, recent_requests=requests[:5],
    )


@staff_bp.route('/profile', methods=('GET', 'POST'))
def account_profile():
    """Let a staff member or admin update their personal account profile."""
    account = signed_in_shop_worker()
    if account is None:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        if request.form.get('remove_profile_picture') == '1':
            if account.profile_picture_path:
                account.profile_picture_path = None
                db.session.commit()
                session['user_profile_picture'] = None
                flash('Your profile picture has been removed.', 'success')
            else:
                flash('You do not have a profile picture to remove.', 'error')
            return redirect(url_for('staff_bp.account_profile'))

        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '').strip().lower()
        phone_number = request.form.get('phone_number', '').strip()
        if not full_name or not email:
            flash('Full name and email address are required.', 'error')
        elif full_name != full_name.strip() or '  ' in full_name or len(full_name) > 50:
            flash('Use single spaces in your name.', 'error')
        elif len(full_name.split()) < 2:
            flash('Enter your first and last name.', 'error')
        elif not is_valid_email(email):
            flash('Enter an email address from a supported provider.', 'error')
        elif phone_number and not re.fullmatch(r'[0-9+()\- ]{7,30}', phone_number):
            flash('Enter a valid phone number.', 'error')
        elif Account.query.filter(Account.email == email, Account.id != account.id).first():
            flash('That email address is already being used.', 'error')
        else:
            picture = request.files.get('profile_picture')
            if picture is not None and picture.filename:
                folder = os.path.join(current_app.root_path, 'static', 'images', 'profiles')
                saved = save_image(picture, folder, 'images/profiles')
                if saved is None:
                    flash('The profile picture must be a JPG or PNG image.', 'error')
                    return render_template('staff/account_profile.html', account=account)
                account.profile_picture_path = saved
            account.full_name = full_name
            account.email = email
            account.phone_number = phone_number or None
            db.session.commit()
            session['user_name'] = account.full_name
            session['user_profile_picture'] = account.profile_picture_path
            flash('Your profile has been updated.', 'success')
            return redirect(url_for('staff_bp.account_profile'))

    return render_template('staff/account_profile.html', account=account)


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
