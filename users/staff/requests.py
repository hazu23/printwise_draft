import os
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from users import db
from users.models import Account, PrintRequest, PrintShopServices
from users.notifications import notify_account
from users.customer.print_requests import (
    ALLOWED_PRINT_FILE_EXTENSIONS,
    REQUEST_HIDDEN_SERVICE_NAMES,
    _request_options_for,
    is_valid_print_upload,
)


shop_requests_bp = Blueprint('shop_requests', __name__, template_folder='templates')

# Photocopy is useful for face-to-face customers, so the staff form shows it.
# The customer online form continues using the original hidden-service list.
STAFF_REQUEST_HIDDEN_SERVICE_NAMES = REQUEST_HIDDEN_SERVICE_NAMES - {
    'photocopy', 'photocopy/xerox', 'print/xerox'
}

def _check_shop_user():
    """Require a signed-in staff member or printshop admin."""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    account = Account.query.get(session['user_id'])
    if account is None or not account.is_shop_worker():
        abort(403)

    return None


def _get_accessible_shops():
    """Return only printshops connected to the signed-in account."""
    account = Account.query.get(session['user_id'])
    return account.accessible_printshops() if account else []


def _get_authorized_request_or_404(request_id, shop_ids):
    """Find a request only if it belongs to one of this user's shops."""
    print_request = PrintRequest.query.filter_by(id=request_id).first_or_404()
    if not print_request.belongs_to_any_printshop(shop_ids):
        abort(404)
    return print_request


def _get_display_filename(stored_path):
    """Remove the private random prefix from an uploaded file's name."""
    stored_name = os.path.basename(stored_path.replace('\\', '/'))
    if len(stored_name) > 33 and stored_name[32] == '_':
        return stored_name[33:]
    return stored_name


def _filtered_request_query(shop_ids, include_cancelled=False, receipt_only=False):
    """Build the worker list query from search and date filter parameters."""
    query = PrintRequest.query.filter(PrintRequest.printshop_id.in_(shop_ids))
    if not include_cancelled:
        query = query.filter(PrintRequest.status != 'cancelled')
    if receipt_only:
        query = query.filter(PrintRequest.payment_receipt_path.isnot(None))

    search = request.args.get('q', '').strip()[:100]
    if search:
        pattern = f'%{search}%'
        query = query.outerjoin(Account, PrintRequest.customer_account_id == Account.id).join(
            PrintShopServices, PrintRequest.service_id == PrintShopServices.id
        ).filter(or_(
            Account.full_name.ilike(pattern),
            PrintRequest.walk_in_customer_name.ilike(pattern),
            PrintRequest.request_reference.ilike(pattern),
            PrintRequest.payment_reference.ilike(pattern),
            PrintShopServices.name.ilike(pattern),
        ))

    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    date_column = PrintRequest.payment_submitted_at if receipt_only else PrintRequest.created_at
    try:
        if date_from:
            query = query.filter(date_column >= datetime.strptime(date_from, '%Y-%m-%d'))
        if date_to:
            query = query.filter(date_column < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    except ValueError:
        flash('Choose valid dates for the filters.', 'error')
    return query, search, date_from, date_to


def _make_request_details(print_request):
    """Prepare request information for the details modal."""
    # These are the clear status names shown to staff and admins.
    status_labels = {
        'in_progress': 'Printing',
        'ready': 'Ready for pick up',
    }
    files = []
    for file_index, file_path in enumerate(print_request.uploaded_file_paths()):
        files.append({
            'name': _get_display_filename(file_path),
            'url': url_for(
                'shop_requests.download_request_file',
                request_id=print_request.id,
                file_index=file_index,
            ),
        })

    created_at = print_request.created_at
    submitted = created_at.strftime('%b %d, %Y at %I:%M %p') if created_at else 'Date unavailable'
    status_key = (print_request.status or 'pending').lower().replace(' ', '_')
    payment_status = print_request.payment_status or 'unpaid'
    payment_labels = {
        'unpaid': 'Unpaid',
        'for_verification': 'For verification',
        'partially_paid': 'Partially paid',
        'paid': 'Paid',
    }
    if print_request.customer is not None:
        customer_name = print_request.customer.full_name
        customer_contact = print_request.customer.email
        customer_email = print_request.customer.email
    else:
        customer_name = print_request.walk_in_customer_name or 'In-store customer'
        customer_contact = print_request.walk_in_customer_contact or 'No contact provided'
        customer_email = ''

    return {
        'id': print_request.id,
        'reference': print_request.request_reference or f'Request #{print_request.id}',
        'payment_reference': print_request.payment_reference or '',
        'shop': print_request.printshop.name,
        'customer_name': customer_name,
        'customer_contact': customer_contact,
        'customer_email': customer_email,
        'is_staff_created': print_request.customer_account_id is None,
        'edit_url': (
            url_for('shop_requests.new_walk_in_request', request_id=print_request.id)
            if print_request.customer_account_id is None else ''
        ),
        'service': print_request.service.name,
        'quantity': print_request.quantity,
        'quantity_unit': 'package(s)' if print_request.service.name.strip().lower() == 'id picture' else 'copies',
        'options': print_request.selected_options or {},
        'notes': print_request.notes or '',
        'status': status_key,
        'status_label': status_labels.get(status_key, status_key.replace('_', ' ').title()),
        'price': str(print_request.price) if print_request.price is not None else '',
        'price_label': f'₱{print_request.price:,.2f}' if print_request.price is not None else 'Price not set',
        'payment_status': payment_status,
        'payment_status_label': payment_labels.get(payment_status, 'Unpaid'),
        'payment_method': (print_request.payment_method or '').upper(),
        'payment_receipt_url': (
            url_for('shop_requests.view_payment_receipt', request_id=print_request.id)
            if print_request.payment_receipt_path else ''
        ),
        'submitted': submitted,
        'files': files,
    }


@shop_requests_bp.route('/requests')
def inbox():
    """Show print requests for this staff member's or admin's printshops."""
    login_redirect = _check_shop_user()
    if login_redirect:
        return login_redirect

    shops = _get_accessible_shops()
    shop_ids = [shop.id for shop in shops]
    print_requests = []
    pagination = None
    selected_status = request.args.get('status', 'all')
    allowed_statuses = {'all', 'pending', 'accepted', 'in_progress', 'ready', 'completed', 'declined'}
    if selected_status not in allowed_statuses:
        selected_status = 'all'
    search = request.args.get('q', '').strip()[:100]
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    if shop_ids:
        filtered_query, search, date_from, date_to = _filtered_request_query(shop_ids)
        all_filtered = filtered_query.all()
        if selected_status != 'all':
            filtered_query = filtered_query.filter(PrintRequest.status == selected_status)
        page = request.args.get('page', 1, type=int)
        pagination = filtered_query.order_by(
            PrintRequest.created_at.desc(), PrintRequest.id.desc()
        ).paginate(page=max(page, 1), per_page=10, error_out=False)
        print_requests = pagination.items
    else:
        all_filtered = []

    request_details = [_make_request_details(item) for item in print_requests]
    status_counts = {
        'all': len(all_filtered),
        'pending': 0,
        'accepted': 0,
        'in_progress': 0,
        'ready': 0,
        'completed': 0,
        'declined': 0,
    }
    for item in all_filtered:
        if item.status in status_counts:
            status_counts[item.status] += 1

    if len(shops) == 1:
        page_shop_name = shops[0].name
    elif shops:
        page_shop_name = 'All managed printshops'
    else:
        page_shop_name = 'No printshop assigned'

    return render_template(
        'staff/request_inbox.html',
        request_details=request_details,
        status_counts=status_counts,
        page_shop_name=page_shop_name,
        has_shop=bool(shops),
        shops=shops,
        pagination=pagination,
        selected_status=selected_status,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )


@shop_requests_bp.route('/receipts')
def receipts():
    """Show submitted payment receipts for this worker's printshops."""
    login_redirect = _check_shop_user()
    if login_redirect:
        return login_redirect

    shops = _get_accessible_shops()
    shop_ids = [shop.id for shop in shops]
    submitted_receipts = []
    pagination = None
    search = request.args.get('q', '').strip()[:100]
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    if shop_ids:
        receipt_query, search, date_from, date_to = _filtered_request_query(
            shop_ids, receipt_only=True
        )
        page = request.args.get('page', 1, type=int)
        pagination = receipt_query.order_by(
            PrintRequest.payment_submitted_at.desc(), PrintRequest.id.desc()
        ).paginate(page=max(page, 1), per_page=10, error_out=False)
        submitted_receipts = pagination.items

    if len(shops) == 1:
        page_shop_name = shops[0].name
    elif shops:
        page_shop_name = 'All managed printshops'
    else:
        page_shop_name = 'No printshop assigned'

    return render_template(
        'staff/receipts.html',
        receipts=submitted_receipts,
        page_shop_name=page_shop_name,
        pagination=pagination,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )


@shop_requests_bp.route('/requests/new', defaults={'request_id': None}, methods=('GET', 'POST'))
@shop_requests_bp.route('/requests/<int:request_id>/edit', methods=('GET', 'POST'))
def new_walk_in_request(request_id):
    """Create or update a request for a customer who visits in person."""
    login_redirect = _check_shop_user()
    if login_redirect:
        return login_redirect

    shops = _get_accessible_shops()
    if not shops:
        flash('No printshop is linked to this account.', 'error')
        return redirect(url_for('shop_requests.inbox'))

    shop_ids = [item.id for item in shops]
    if request_id is None:
        print_request = PrintRequest()
        shop = shops[0]
        is_editing = False
    else:
        print_request = _get_authorized_request_or_404(request_id, shop_ids)
        # Online customer requests cannot be changed through the walk-in form.
        if print_request.customer_account_id is not None:
            abort(404)
        shop = print_request.printshop
        is_editing = True

    # The account or existing request identifies its printshop, so staff do
    # not need to choose one again.
    services = [
        service for service in shop.active_services()
        if service.can_be_requested(STAFF_REQUEST_HIDDEN_SERVICE_NAMES)
    ]
    selected_service_id = request.values.get('service_id', type=int)
    if selected_service_id is None and is_editing:
        selected_service_id = print_request.service_id
    selected_options = (
        dict(print_request.selected_options or {})
        if request.method == 'GET' and is_editing else {}
    )

    def show_form():
        """Show the form again, including any values entered before an error."""
        service_options = {
            str(service.id): _request_options_for(service)
            for service in services
        }
        existing_files = []
        if is_editing:
            for file_index, file_path in enumerate(print_request.uploaded_file_paths()):
                existing_files.append({
                    'name': _get_display_filename(file_path),
                    'url': url_for(
                        'shop_requests.download_request_file',
                        request_id=print_request.id,
                        file_index=file_index,
                    ),
                })
        return render_template(
            'staff/walk_in_request.html',
            shop=shop,
            services=services,
            selected_service_id=selected_service_id,
            selected_options=selected_options,
            service_options=service_options,
            print_request=print_request,
            is_editing=is_editing,
            existing_files=existing_files,
        )

    if request.method == 'GET':
        return show_form()

    service = next(
        (
            item for item in services
            if item.id == selected_service_id and item.printshop_id == shop.id
        ),
        None,
    )
    if service is None:
        flash('Choose a service offered by the selected printshop.', 'error')
        return show_form()

    customer_name = request.form.get('customer_name', '').strip()
    if len(customer_name) > 100:
        flash('Customer name must be 100 characters or fewer.', 'error')
        return show_form()

    customer_contact = request.form.get('customer_contact', '').strip()
    if len(customer_contact) > 255:
        flash('Customer contact must be 255 characters or fewer.', 'error')
        return show_form()

    try:
        quantity = int(request.form.get('quantity', '1'))
        if quantity < 1:
            raise ValueError
    except (TypeError, ValueError):
        flash('Quantity must be a whole number greater than zero.', 'error')
        return show_form()

    notes = request.form.get('notes', '').strip()
    if len(notes) > 4000:
        flash('Notes must be 4,000 characters or fewer.', 'error')
        return show_form()

    # Validate the service-specific paper size, color, finish, or other fields.
    service_config = _request_options_for(service)
    for field in service_config.get('fields', []):
        key = field.get('key')
        if not isinstance(key, str) or not key.replace('_', '').isalnum():
            continue

        value = request.form.get(f'option_{key}', '').strip()
        selected_options[key] = value

        if field.get('required') and not value:
            flash(f"Please provide {field.get('label', 'the required option').lower()}.", 'error')
            return show_form()

        choices = field.get('choices')
        if isinstance(choices, list):
            allowed_values = [
                choice if isinstance(choice, str) else choice.get('value')
                for choice in choices
                if isinstance(choice, (str, dict))
            ]
            if value and value not in allowed_values:
                flash(f"Choose a valid value for {field.get('label', 'the option').lower()}.", 'error')
                return show_form()

    entered_price = request.form.get('price', '').strip()
    if entered_price and not print_request.set_price(entered_price):
        flash('Enter a valid price greater than zero.', 'error')
        return show_form()
    if not entered_price:
        print_request.price = None

    uploaded_files = [
        file for file in request.files.getlist('print_files')
        if file and file.filename
    ]
    safe_files = []
    for uploaded_file in uploaded_files:
        safe_filename = secure_filename(uploaded_file.filename)
        extension = os.path.splitext(safe_filename)[1].lower()
        if extension not in ALLOWED_PRINT_FILE_EXTENSIONS or not is_valid_print_upload(uploaded_file, extension):
            flash('Each attachment must be a PDF, Word document, JPG, or PNG file.', 'error')
            return show_form()
        safe_files.append((uploaded_file, safe_filename))

    saved_file_paths = list(print_request.uploaded_file_paths()) if is_editing else []
    if safe_files:
        upload_folder = os.path.join(current_app.instance_path, 'request_uploads')
        os.makedirs(upload_folder, exist_ok=True)
        for uploaded_file, safe_filename in safe_files:
            stored_filename = f'{uuid.uuid4().hex}_{safe_filename}'
            uploaded_file.save(os.path.join(upload_folder, stored_filename))
            saved_file_paths.append(f'request_uploads/{stored_filename}')

    # Save the edited values or finish creating the staff-created request.
    print_request.customer_account_id = None
    print_request.walk_in_customer_name = customer_name or None
    print_request.walk_in_customer_contact = customer_contact or None
    print_request.printshop_id = shop.id
    print_request.service_id = service.id
    print_request.quantity = quantity
    print_request.selected_options = selected_options
    print_request.file_paths = saved_file_paths
    print_request.notes = notes or None
    if not is_editing:
        print_request.status = 'accepted'

    if not is_editing:
        db.session.add(print_request)
        db.session.flush()
        print_request.assign_request_reference()
    db.session.commit()
    flash(
        'Print request updated.' if is_editing else 'Print request created.',
        'success',
    )
    return redirect(url_for('shop_requests.inbox'))


@shop_requests_bp.route('/requests/<int:request_id>/update', methods=('POST',))
def update_request(request_id):
    """Save price, request status, and payment status with one button."""
    login_redirect = _check_shop_user()
    if login_redirect:
        return login_redirect

    shops = _get_accessible_shops()
    shop_ids = [shop.id for shop in shops]
    print_request = _get_authorized_request_or_404(request_id, shop_ids)
    previous_status = print_request.status
    previous_price = print_request.price
    if not print_request.change_status(request.form.get('status')):
        db.session.rollback()
        flash('Choose a valid request status.', 'error')
        return redirect(url_for('shop_requests.inbox'))

    if not print_request.change_payment_status(request.form.get('payment_status')):
        db.session.rollback()
        flash('Choose a valid payment status.', 'error')
        return redirect(url_for('shop_requests.inbox'))

    price = request.form.get('price', '').strip()
    if price and not print_request.set_price(price):
        db.session.rollback()
        flash('Enter a valid price greater than zero.', 'error')
        return redirect(url_for('shop_requests.inbox'))

    customer_id = print_request.customer_account_id
    customer_link = url_for('customer_bp.dashboard')
    reference = print_request.request_reference or f'Request #{print_request.id}'
    if customer_id:
        if print_request.price is not None and print_request.price != previous_price:
            notify_account(
                customer_id,
                'Price set',
                f'{print_request.printshop.name} set the price of {reference} to ₱{print_request.price:,.2f}.',
                customer_link,
                'price',
            )
        status_changed = print_request.status != previous_status
        # Moving a pending request directly to Printing or Ready also means
        # the printshop accepted it, so save the acceptance alert as well.
        accepted_statuses = {'accepted', 'in_progress', 'ready', 'completed'}
        if status_changed and previous_status == 'pending' and print_request.status in accepted_statuses:
            notify_account(
                customer_id,
                'Request accepted',
                f'{reference} has been accepted by {print_request.printshop.name}.',
                customer_link,
                'request_status',
            )
        later_status_notifications = {
            'in_progress': ('Printing started', f'{print_request.printshop.name} started printing {reference}.'),
            'ready': ('Ready for pick up', f'{reference} is ready for pickup at {print_request.printshop.name}.'),
        }
        if status_changed and print_request.status in later_status_notifications:
            title, message = later_status_notifications[print_request.status]
            notify_account(customer_id, title, message, customer_link, 'request_status')

    db.session.commit()
    flash('Request changes saved.', 'success')
    return redirect(url_for('shop_requests.inbox'))


@shop_requests_bp.route('/requests/<int:request_id>/payment-receipt')
def view_payment_receipt(request_id):
    """Let authorized shop staff view a customer's payment receipt."""
    login_redirect = _check_shop_user()
    if login_redirect:
        return login_redirect

    shops = _get_accessible_shops()
    shop_ids = [shop.id for shop in shops]
    print_request = _get_authorized_request_or_404(request_id, shop_ids)
    if not print_request.payment_receipt_path:
        abort(404)

    filename = os.path.basename(print_request.payment_receipt_path.replace('\\', '/'))
    receipt_folder = os.path.join(current_app.instance_path, 'payment_receipts')
    return send_from_directory(receipt_folder, filename, as_attachment=False)


@shop_requests_bp.route('/requests/<int:request_id>/files/<int:file_index>')
def download_request_file(request_id, file_index):
    """Let authorized shop staff download an attached request file."""
    login_redirect = _check_shop_user()
    if login_redirect:
        return login_redirect

    shops = _get_accessible_shops()
    shop_ids = [shop.id for shop in shops]
    print_request = _get_authorized_request_or_404(request_id, shop_ids)
    file_paths = print_request.uploaded_file_paths()

    if file_index < 0 or file_index >= len(file_paths):
        abort(404)

    filename = os.path.basename(file_paths[file_index].replace('\\', '/'))
    upload_folder = os.path.join(current_app.instance_path, 'request_uploads')
    return send_from_directory(upload_folder, filename, as_attachment=True)
