import os

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for

from users import db
from users.models import Account, PrintRequest


shop_requests_bp = Blueprint('shop_requests', __name__, template_folder='templates')

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


def _make_request_details(print_request):
    """Prepare request information for the details modal."""
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

    return {
        'id': print_request.id,
        'shop': print_request.printshop.name,
        'customer_name': print_request.customer.full_name,
        'customer_email': print_request.customer.email,
        'service': print_request.service.name,
        'quantity': print_request.quantity,
        'quantity_unit': 'package(s)' if print_request.service.name.strip().lower() == 'id picture' else 'copies',
        'options': print_request.selected_options or {},
        'notes': print_request.notes or '',
        'status': status_key,
        'status_label': status_key.replace('_', ' ').title(),
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
    if shop_ids:
        print_requests = PrintRequest.query.filter(
            PrintRequest.printshop_id.in_(shop_ids)
        ).order_by(PrintRequest.created_at.desc(), PrintRequest.id.desc()).all()

    request_details = [_make_request_details(item) for item in print_requests]
    status_counts = {
        'all': len(request_details),
        'pending': 0,
        'accepted': 0,
        'in_progress': 0,
        'ready': 0,
        'completed': 0,
        'declined': 0,
    }
    for item in request_details:
        if item['status'] in status_counts:
            status_counts[item['status']] += 1

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
    )


@shop_requests_bp.route('/requests/<int:request_id>/status', methods=('POST',))
def update_status(request_id):
    """Save a new status for a request belonging to this user's shop."""
    login_redirect = _check_shop_user()
    if login_redirect:
        return login_redirect

    shops = _get_accessible_shops()
    shop_ids = [shop.id for shop in shops]
    print_request = _get_authorized_request_or_404(request_id, shop_ids)
    new_status = request.form.get('status', '').strip().lower()

    if not print_request.change_status(new_status):
        flash('Choose a valid request status.', 'error')
        return redirect(url_for('shop_requests.inbox'))
    db.session.commit()
    flash('Request status updated.', 'success')
    return redirect(url_for('shop_requests.inbox'))


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
