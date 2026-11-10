from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from users.models import Account, PrintRequest, PrintShop


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
        shop_cards.append({'shop': shop, 'services': services})

    return render_template('printshops.html', shop_cards=shop_cards)


@customer_bp.route('/myrequests')
def dashboard():
    # Only a signed-in customer can see their own request history.
    if session.get('user_role') != 'customer':
        flash('Please log in as a customer to view your requests.', 'error')
        return redirect(url_for('auth.login'))

    # Load this customer's requests, with the newest request shown first.
    print_requests = PrintRequest.query.filter_by(
        customer_account_id=session['user_id'],
    ).order_by(PrintRequest.created_at.desc()).all()

    # Only allow the three status filters shown on the page.
    selected_status = request.args.get('status', 'all')
    if selected_status not in {'all', 'in_progress', 'ready', 'completed'}:
        selected_status = 'all'

    # Count a few common statuses for the summary at the top of the page.
    status_counts = {
        'in_progress': sum(item.status == 'in_progress' for item in print_requests),
        'ready': sum(item.status == 'ready' for item in print_requests),
        'completed': sum(item.status == 'completed' for item in print_requests),
    }

    # Keep the total count for the summary, then show only the selected status.
    total_requests = len(print_requests)
    if selected_status != 'all':
        print_requests = [item for item in print_requests if item.status == selected_status]

    # Keep the saved filenames private, but prepare a safe view link for each file.
    request_files = {}
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

    return render_template(
        'my_requests.html',
        print_requests=print_requests,
        status_counts=status_counts,
        selected_status=selected_status,
        total_requests=total_requests,
        request_files=request_files,
    )
