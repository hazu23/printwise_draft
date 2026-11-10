import os
import uuid

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from users import db
from users.models import PrintRequest, PrintShop

# This blueprint contains the print request form and confirmation page.
request_bp = Blueprint('request_bp', __name__, template_folder='templates')

ALLOWED_PRINT_FILE_EXTENSIONS = {'.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'}
REQUEST_HIDDEN_SERVICE_NAMES = {
    'photocopy', 'photocopy/xerox', 'print/xerox', 'lamination', 'laminate',
    'photo develop', 'photo frame', 'sintra board', 'co2 laser cutting',
}


def _request_options_for(service):
    """Build the choices shown for the selected print service."""
    service_name = service.name.strip().lower()
    service_description = service.description or ''

    if service_name == 'sticker paper printing':
        return {
            'description': service_description or 'A4 sticker paper printing.',
            'fields': [
                {
                    'key': 'paper_size',
                    'label': 'Paper size',
                    'type': 'select',
                    'required': True,
                    'choices': [{'value': 'A4', 'label': 'A4 (8.3 × 11.7 in)'}],
                },
            ],
        }

    if service_name == 'id picture':
        return {
            'description': service_description or 'ID picture - prints on photo paper.',
            'quantity_label': 'Number of packages',
            'fields': [
                {
                    'key': 'package',
                    'label': 'Package',
                    'type': 'select',
                    'required': True,
                    'choices': [
                        {'value': 'Package 1', 'label': 'Package 1: 6 pcs 2×2'},
                        {'value': 'Package 2', 'label': 'Package 2: 12 pcs 1×1'},
                        {'value': 'Package 3', 'label': 'Package 3: 4 pcs 2×2 and 6 pcs 1×1'},
                        {'value': 'Package 4', 'label': 'Package 4: 6 pcs passport size'},
                    ],
                },
                {
                    'key': 'finish',
                    'label': 'Finish',
                    'type': 'select',
                    'required': False,
                    'choices': ['No finish', 'Cut'],
                },
            ],
        }

    # Document and photo prints share color and finish choices. Their paper
    # sizes differ by service, and DPS has a shorter list for document prints.
    if service_name in {'document printing', 'photo printing'}:
        if service_name == 'photo printing':
            paper_sizes = [
                {'value': 'A4', 'label': 'A4 (8.3 × 11.7 in)'},
                {'value': 'Long bondpaper', 'label': 'Long bondpaper (8.5 × 13 in)'},
            ]
        elif service.printshop.name.strip().casefold() == "dan's printing services":
            paper_sizes = [
                {'value': 'A4', 'label': 'A4 (8.3 × 11.7 in)'},
                {'value': 'Short bondpaper', 'label': 'Short bondpaper (8.5 × 11 in)'},
                {'value': 'Long bondpaper', 'label': 'Long bondpaper (8.5 × 13 in)'},
            ]
        else:
            paper_sizes = [
                {'value': 'A3', 'label': 'A3 (11.7 × 16.5 in)'},
                {'value': 'A4', 'label': 'A4 (8.3 × 11.7 in)'},
                {'value': 'A5', 'label': 'A5 (5.8 × 8.3 in)'},
                {'value': 'Short bondpaper', 'label': 'Short bondpaper (8.5 × 11 in)'},
                {'value': 'Long bondpaper', 'label': 'Long bondpaper (8.5 × 13 in)'},
                {'value': 'Legal', 'label': 'Legal (8.5 × 14 in)'},
                {'value': '4 × 6 in', 'label': 'Photo 4 × 6 in'},
                {'value': '5 × 7 in', 'label': 'Photo 5 × 7 in'},
                {'value': '8 × 10 in', 'label': 'Photo 8 × 10 in'},
            ]

        return {
            'description': service_description or 'Specify the paper size, print color, and finish for your files.',
            'fields': [
                {
                    'key': 'paper_size',
                    'label': 'Paper size',
                    'type': 'select',
                    'required': True,
                    'choices': paper_sizes,
                },
                {
                    'key': 'print_color',
                    'label': 'Print color',
                    'type': 'select',
                    'required': True,
                    'choices': ['Black and white', 'Color'],
                },
                {
                    'key': 'finish',
                    'label': 'Finish',
                    'type': 'select',
                    'required': False,
                    'choices': ['No finish', 'Lamination'],
                },
            ],
        }

    options = service.options if isinstance(service.options, dict) else {}
    if options.get('fields'):
        return options

    return {
        'description': service_description or 'Tell the printshop the options or specifications you need.',
        'fields': [{
            'key': 'specifications',
            'label': 'Options or specifications',
            'type': 'text',
            'required': True,
            'placeholder': 'Enter the details for this service',
        }],
    }


@request_bp.route('/printshops/<int:shop_id>/request', methods=('GET', 'POST'))
def new_print_request(shop_id):
    # Only logged-in customers can send print requests.
    if session.get('user_role') != 'customer':
        flash('Please log in as a customer to request a print.', 'error')
        return redirect(url_for('auth.login'))

    shop = PrintShop.query.get_or_404(shop_id)
    all_services = shop.active_services()
    # These are not request types: lamination is selected as a finish instead.
    services = [
        service for service in all_services
        if service.can_be_requested(REQUEST_HIDDEN_SERVICE_NAMES)
    ]

    selected_service_id = request.values.get('service_id', type=int)
    selected_options = {}

    def show_form():
        # Give JavaScript each service's configured choices so the form can
        # display the right paper, color, or finish fields after selection.
        service_options = {
            str(service.id): _request_options_for(service)
            for service in services
        }
        return render_template(
            'request_form.html',
            shop=shop,
            services=services,
            selected_service_id=selected_service_id,
            selected_options=selected_options,
            service_options=service_options,
        )

    if request.method == 'GET':
        return show_form()

    service = next(
        (item for item in services if item.id == request.form.get('service_id', type=int)),
        None,
    )
    if service is None:
        flash('Choose a service offered by this printshop.', 'error')
        return show_form()

    selected_service_id = service.id
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

    # Read only the option fields configured for the selected service.
    service_config = _request_options_for(service)
    option_fields = service_config.get('fields', [])
    for field in option_fields:
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

    uploaded_files = [
        file for file in request.files.getlist('print_files')
        if file and file.filename
    ]
    if not uploaded_files:
        flash('Attach at least one file before sending your request.', 'error')
        return show_form()

    safe_files = []
    for uploaded_file in uploaded_files:
        safe_filename = secure_filename(uploaded_file.filename)
        extension = os.path.splitext(safe_filename)[1].lower()
        if extension not in ALLOWED_PRINT_FILE_EXTENSIONS:
            flash('Each attachment must be a PDF, Word document, JPG, or PNG file.', 'error')
            return show_form()
        safe_files.append((uploaded_file, safe_filename))

    # Keep customer documents in Flask's private instance folder, not in
    # the public static directory. Multiple attachments are saved separately.
    upload_folder = os.path.join(current_app.instance_path, 'request_uploads')
    os.makedirs(upload_folder, exist_ok=True)
    saved_file_paths = []
    for uploaded_file, safe_filename in safe_files:
        stored_filename = f'{uuid.uuid4().hex}_{safe_filename}'
        uploaded_file.save(os.path.join(upload_folder, stored_filename))
        saved_file_paths.append(f'request_uploads/{stored_filename}')

    print_request = PrintRequest(
        customer_account_id=session['user_id'],
        printshop_id=shop.id,
        service_id=service.id,
        quantity=quantity,
        selected_options=selected_options,
        file_paths=saved_file_paths,
        notes=notes or None,
    )
    db.session.add(print_request)
    db.session.commit()

    return redirect(url_for('request_bp.request_confirmation', request_id=print_request.id))


@request_bp.route('/requests/<int:request_id>/confirmation')
def request_confirmation(request_id):
    # Customers can only view the confirmation for their own request.
    if session.get('user_role') != 'customer':
        flash('Please log in to view your request.', 'error')
        return redirect(url_for('auth.login'))

    print_request = PrintRequest.query.get_or_404(request_id)
    if not print_request.belongs_to_customer(session['user_id']):
        abort(404)
    return render_template('request_submitted.html', print_request=print_request)


@request_bp.route('/myrequests/<int:request_id>/files/<int:file_index>')
def view_uploaded_file(request_id, file_index):
    # Customers can only open files attached to their own print requests.
    if 'user_id' not in session:
        flash('Please log in to view your uploaded file.', 'error')
        return redirect(url_for('auth.login'))
    if session.get('user_role') != 'customer':
        abort(403)

    print_request = PrintRequest.query.get_or_404(request_id)
    if not print_request.belongs_to_customer(session['user_id']):
        abort(404)
    file_paths = print_request.uploaded_file_paths()

    if file_index < 0 or file_index >= len(file_paths):
        abort(404)

    # Resolve only the saved filename inside the private upload folder.
    filename = os.path.basename(file_paths[file_index].replace('\\', '/'))
    upload_folder = os.path.join(current_app.instance_path, 'request_uploads')
    return send_from_directory(upload_folder, filename, as_attachment=False)
