import os
import re
from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_

from users import db
from users.auth import is_valid_email
from users.models import Account, Customer, PrintRequest, PrintShop, PrintShopServices
from users.shop_helpers import save_image


customer_bp = Blueprint(
    'customer_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/users/customer/static',
)


@customer_bp.route('/')
def index():
    return render_template('index.html')


@customer_bp.route('/profile', methods=('GET', 'POST'))
def profile():
    """Let a signed-in customer view and edit their account details."""
    if not session.get('user_id'):
        flash('Please log in to view your profile.', 'error')
        return redirect(url_for('auth.login'))
    if session.get('user_role') != 'customer':
        abort(403)

    account = Account.query.get_or_404(session['user_id'])
    # Repair older customer accounts created before the customers table was used.
    if account.customer is None:
        account.customer = Customer(account_id=account.id)
        db.session.add(account.customer)
        db.session.commit()
    if request.method == 'POST':
        # Removing the picture is a separate action, so the other fields do not
        # need to be submitted or changed at the same time.
        if request.form.get('remove_profile_picture') == '1':
            if account.customer and account.customer.profile_picture_path:
                account.customer.profile_picture_path = None
                db.session.commit()
                session['user_profile_picture'] = None
                flash('Your profile picture has been removed.', 'success')
            else:
                flash('You do not have a profile picture to remove.', 'error')
            return redirect(url_for('customer_bp.profile'))

        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '').strip().lower()
        phone_number = request.form.get('phone_number', '').strip()

        if not full_name or not email:
            flash('Full name and email address are required.', 'error')
        elif full_name != full_name.strip() or '  ' in full_name or len(full_name) > 50:
            flash('Use single spaces in your name, with no spaces at the beginning or end.', 'error')
        elif len(full_name.split()) < 2 or not full_name.split()[0].isalpha() or not full_name.split()[-1].isalpha():
            flash('Enter your first and last name using letters.', 'error')
        elif not is_valid_email(email):
            flash('Enter an email address from a supported provider.', 'error')
        elif phone_number and not re.fullmatch(r'[0-9+()\- ]{7,30}', phone_number):
            flash('Enter a valid phone number using numbers, spaces, +, parentheses, or hyphens.', 'error')
        else:
            duplicate = Account.query.filter(
                Account.email == email,
                Account.id != account.id,
            ).first()
            if duplicate:
                flash('That email address is already being used by another account.', 'error')
            else:
                profile_picture = request.files.get('profile_picture')
                if profile_picture is not None and profile_picture.filename:
                    picture_folder = os.path.join(
                        current_app.root_path,
                        'customer', 'static', 'images', 'profiles',
                    )
                    saved_picture = save_image(
                        profile_picture, picture_folder, 'images/profiles'
                    )
                    if saved_picture is None:
                        flash('The profile picture must be a JPG or PNG image.', 'error')
                        return render_template('profile.html', account=account)
                    account.customer.profile_picture_path = saved_picture

                account.full_name = full_name
                account.email = email
                account.customer.phone_number = phone_number or None
                db.session.commit()
                session['user_name'] = account.full_name
                session['user_profile_picture'] = account.customer.profile_picture_path
                flash('Your profile has been updated.', 'success')
                return redirect(url_for('customer_bp.profile'))

    return render_template('profile.html', account=account)


@customer_bp.route('/printshops')
def printshops():
    # Require a signed-in account before allowing access to the directory.
    if 'user_id' not in session:
        flash('Please log in to browse printshops.', 'error')
        return redirect(url_for('auth.login'))
        # Staff and admins work with requests, so send them to their own home page.
    if session.get('user_role') in ('staff', 'admin'):
        shop_worker = Account.query.get(session['user_id'])
        return redirect(url_for(shop_worker.home_endpoint()))

    # Fetch printshops in name order for the directory.
    printshops = PrintShop.query.order_by(PrintShop.name.asc()).all()

    # Prepare each shop's active services and products for the details modal.
    shop_cards = []
    for shop in printshops:
        services = [
            {
                'name': service.name,
                'category': service.category,
                'description': service.description,
            }
            for service in shop.active_services()
        ]
        shop_cards.append({'shop': shop, 'services': services, 'opening_status': shop.opening_status()})

    return render_template('printshops.html', shop_cards=shop_cards)


@customer_bp.route('/myrequests')
def dashboard():
    # Only a signed-in customer can see their own request history.
    if not session.get('user_id'):
        flash('Please log in as a customer to view your requests.', 'error')
        return redirect(url_for('auth.login'))
    if session.get('user_role') != 'customer':
        abort(403)

    # Load this customer's requests, with the newest request shown first.
    base_query = PrintRequest.query.filter_by(customer_account_id=session['user_id'])
    all_requests = base_query.order_by(PrintRequest.created_at.desc()).all()

    # Only allow the three status filters shown on the page.
    selected_status = request.args.get('status', 'all')
    if selected_status not in {'all', 'in_progress', 'ready', 'completed'}:
        selected_status = 'all'

    # Count a few common statuses for the summary at the top of the page.
    status_counts = {
        'in_progress': sum(item.status == 'in_progress' for item in all_requests),
        'ready': sum(item.status == 'ready' for item in all_requests),
        'completed': sum(item.status == 'completed' for item in all_requests),
    }

    # Search and dates narrow the visible list but do not change summary totals.
    total_requests = len(all_requests)
    search = request.args.get('q', '').strip()[:100]
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    filtered_query = base_query
    if search:
        pattern = f'%{search}%'
        filtered_query = filtered_query.join(PrintShop, PrintRequest.printshop_id == PrintShop.id).join(
            PrintShopServices, PrintRequest.service_id == PrintShopServices.id
        ).filter(or_(
            PrintShop.name.ilike(pattern),
            PrintShopServices.name.ilike(pattern),
            PrintRequest.request_reference.ilike(pattern),
            PrintRequest.payment_reference.ilike(pattern),
        ))
    try:
        if date_from:
            filtered_query = filtered_query.filter(PrintRequest.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        if date_to:
            filtered_query = filtered_query.filter(PrintRequest.created_at < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    except ValueError:
        flash('Choose valid dates for the filters.', 'error')
    if selected_status != 'all':
        filtered_query = filtered_query.filter(PrintRequest.status == selected_status)
    page = request.args.get('page', 1, type=int)
    pagination = filtered_query.order_by(
        PrintRequest.created_at.desc(), PrintRequest.id.desc()
    ).paginate(page=max(page, 1), per_page=10, error_out=False)
    print_requests = pagination.items

    # Keep the saved filenames private, but prepare a safe view link for each file.
    request_files = {}
    request_details = []
    for print_request in print_requests:
        request_files[print_request.id] = []
        saved_paths = print_request.uploaded_file_paths()
        for file_index, saved_path in enumerate(saved_paths):
            stored_filename = saved_path.replace('\\', '/').rsplit('/', 1)[-1]
            display_filename = stored_filename[33:] if len(stored_filename) > 33 and stored_filename[32] == '_' else stored_filename
            request_files[print_request.id].append({
                'name': display_filename,
                'url': url_for(
                    'request_bp.view_uploaded_file',
                    request_id=print_request.id,
                    file_index=file_index,
                ),
            })

        request_details.append({
            'id': print_request.id,
            'reference': print_request.request_reference or f'Request #{print_request.id}',
            'payment_reference': print_request.payment_reference or '',
            'shop': print_request.printshop.name,
            'service': print_request.service.name,
            'submitted': print_request.created_at.strftime('%b %d, %Y') if print_request.created_at else 'Date unavailable',
            'quantity': print_request.quantity,
            'options': print_request.selected_options or {},
            'notes': print_request.notes or '',
            'files': request_files[print_request.id],
        })

    return render_template(
        'my_requests.html',
        print_requests=print_requests,
        status_counts=status_counts,
        selected_status=selected_status,
        total_requests=total_requests,
        request_files=request_files,
        request_details=request_details,
        pagination=pagination,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )
