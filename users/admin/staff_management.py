"""Admin pages for creating and managing printshop staff accounts."""

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from users import db
from users.auth import is_valid_email
from users.models import Account, Staff
from users.shop_helpers import account_printshop


admin_staff_bp = Blueprint('admin_staff', __name__, url_prefix='/admin/staff')


def _admin_and_shop():
    """Return the signed-in admin and the printshop they manage."""
    if not session.get('user_id'):
        return None, None
    account = Account.query.get(session['user_id'])
    if account is None or not account.has_role('admin'):
        abort(403)
    return account, account_printshop(account)


def _staff_form_error(full_name, email, password, confirmation):
    """Return the first beginner-friendly validation error, if any."""
    if not full_name or not email or not password or not confirmation:
        return 'Complete every staff account field.'
    if full_name != full_name.strip() or '  ' in full_name or len(full_name) > 50:
        return 'Use single spaces in the staff member name.'
    parts = full_name.split()
    if len(parts) < 2 or not parts[0].isalpha() or not parts[-1].isalpha():
        return 'Enter the staff member’s first and last name using letters.'
    if not is_valid_email(email):
        return 'Enter an email address from a supported provider.'
    if len(password) < 8 or not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        return 'The temporary password must have at least 8 characters, one letter, and one number.'
    if any(char.isspace() for char in password):
        return 'Spaces are not allowed in passwords.'
    if password != confirmation:
        return 'The temporary passwords do not match.'
    return None


@admin_staff_bp.route('/')
def staff_accounts():
    account, shop = _admin_and_shop()
    if account is None:
        return redirect(url_for('auth.login'))
    staff_members = sorted(
        (member for member in shop.staff_members),
        key=lambda member: member.account.full_name.lower(),
    ) if shop else []
    return render_template(
        'admin/staff_accounts.html', shop=shop, staff_members=staff_members,
    )


@admin_staff_bp.route('/new', methods=('POST',))
def create_staff():
    account, shop = _admin_and_shop()
    if account is None:
        return redirect(url_for('auth.login'))
    if shop is None:
        flash('No printshop is connected to this admin account.', 'error')
        return redirect(url_for('admin_staff.staff_accounts'))

    full_name = request.form.get('full_name', '')
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirmation = request.form.get('confirm_password', '')
    error = _staff_form_error(full_name, email, password, confirmation)
    if error:
        flash(error, 'error')
    elif Account.query.filter_by(email=email).first():
        flash('That email address already belongs to an account.', 'error')
    else:
        staff_account = Account(
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password),
            role='staff',
            is_active=True,
            email_verified=True,
        )
        db.session.add(staff_account)
        db.session.flush()
        db.session.add(Staff(account_id=staff_account.id, printshop_id=shop.id))
        db.session.commit()
        flash('Staff account created and connected to your printshop.', 'success')
    return redirect(url_for('admin_staff.staff_accounts'))


@admin_staff_bp.route('/<int:account_id>/toggle', methods=('POST',))
def toggle_staff(account_id):
    account, shop = _admin_and_shop()
    if account is None:
        return redirect(url_for('auth.login'))
    if shop is None:
        abort(404)

    member = Staff.query.filter_by(account_id=account_id, printshop_id=shop.id).first_or_404()
    member.account.is_active = not member.account.is_active
    db.session.commit()
    state = 'reactivated' if member.account.is_active else 'deactivated'
    flash(f'{member.account.full_name} has been {state}.', 'success')
    return redirect(url_for('admin_staff.staff_accounts'))
