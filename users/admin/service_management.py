"""Admin pages for managing the services offered by a printshop."""

from copy import deepcopy

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from users import db
from users.models import Account, PrintRequest, PrintShopServices
from users.shop_helpers import account_printshop
from users.customer.print_requests import _request_options_for


admin_services_bp = Blueprint('admin_services', __name__, url_prefix='/admin/services')
ALLOWED_CATEGORIES = {'service', 'product'}


def _admin_shop():
    """Return the signed-in admin's printshop."""
    if not session.get('user_id'):
        return None
    account = Account.query.get(session['user_id'])
    if account is None or not account.has_role('admin'):
        abort(403)
    return account_printshop(account)


def _service_values():
    """Clean the common service fields from an admin form."""
    return (
        request.form.get('name', '').strip(),
        request.form.get('category', '').strip().lower(),
        request.form.get('description', '').strip(),
    )


def _service_error(name, category, description):
    if not name:
        return 'Enter a service or product name.'
    if len(name) > 120:
        return 'The service name must be 120 characters or fewer.'
    if category not in ALLOWED_CATEGORIES:
        return 'Choose Service or Product as the category.'
    if len(description) > 1000:
        return 'The description must be 1,000 characters or fewer.'
    return None


@admin_services_bp.route('/')
def services():
    shop = _admin_shop()
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    offerings = sorted(shop.offerings, key=lambda item: item.name.lower()) if shop else []
    option_configs = {}
    for offering in offerings:
        saved = offering.options if isinstance(offering.options, dict) else {}
        option_configs[offering.id] = (
            deepcopy(saved) if saved.get('managed_options')
            else _request_options_for(offering)
        )
    return render_template(
        'admin/services.html', shop=shop, offerings=offerings,
        option_configs=option_configs,
    )


@admin_services_bp.route('/new', methods=('POST',))
def create_service():
    shop = _admin_shop()
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    if shop is None:
        flash('No printshop is connected to this admin account.', 'error')
        return redirect(url_for('admin_services.services'))

    name, category, description = _service_values()
    error = _service_error(name, category, description)
    duplicate = next(
        (item for item in shop.offerings if item.name.casefold() == name.casefold()),
        None,
    ) if name else None
    if error:
        flash(error, 'error')
    elif duplicate:
        flash('A service or product with that name already exists.', 'error')
    else:
        db.session.add(PrintShopServices(
            printshop_id=shop.id,
            name=name,
            category=category,
            description=description or None,
            options={},
            is_active=True,
        ))
        db.session.commit()
        flash('Service or product added.', 'success')
    return redirect(url_for('admin_services.services'))


def _owned_service(shop, service_id):
    """Find a service only when it belongs to this admin's printshop."""
    if shop is None:
        abort(404)
    return PrintShopServices.query.filter_by(
        id=service_id, printshop_id=shop.id,
    ).first_or_404()


@admin_services_bp.route('/<int:service_id>/edit', methods=('POST',))
def edit_service(service_id):
    shop = _admin_shop()
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    offering = _owned_service(shop, service_id)
    name, category, description = _service_values()
    error = _service_error(name, category, description)
    duplicate = next(
        (
            item for item in shop.offerings
            if item.id != offering.id and item.name.casefold() == name.casefold()
        ),
        None,
    ) if name else None
    if error:
        flash(error, 'error')
    elif duplicate:
        flash('Another service or product already uses that name.', 'error')
    else:
        offering.name = name
        offering.category = category
        offering.description = description or None
        db.session.commit()
        flash('Service or product updated.', 'success')
    return redirect(url_for('admin_services.services'))


@admin_services_bp.route('/<int:service_id>/toggle', methods=('POST',))
def toggle_service(service_id):
    shop = _admin_shop()
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    offering = _owned_service(shop, service_id)
    offering.is_active = not offering.is_active
    db.session.commit()
    state = 'activated' if offering.is_active else 'deactivated'
    flash(f'{offering.name} has been {state}.', 'success')
    return redirect(url_for('admin_services.services'))


@admin_services_bp.route('/<int:service_id>/delete', methods=('POST',))
def delete_service(service_id):
    """Permanently delete an unused service and its saved option JSON."""
    shop = _admin_shop()
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    offering = _owned_service(shop, service_id)

    # Request rows point to their service. Deleting a used service would make
    # historical requests and receipts unreadable, so it must be deactivated.
    request_count = PrintRequest.query.filter_by(service_id=offering.id).count()
    if request_count:
        flash(
            f'{offering.name} cannot be permanently deleted because it is used by '
            f'{request_count} print request(s). Deactivate it instead.',
            'error',
        )
        return redirect(url_for('admin_services.services'))

    service_name = offering.name
    db.session.delete(offering)
    db.session.commit()
    flash(f'{service_name} and all of its saved options were permanently deleted.', 'success')
    return redirect(url_for('admin_services.services'))


@admin_services_bp.route('/<int:service_id>/options', methods=('POST',))
def edit_options(service_id):
    """Add, rename, enable, or disable a service's selectable choices."""
    shop = _admin_shop()
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    offering = _owned_service(shop, service_id)
    saved = offering.options if isinstance(offering.options, dict) else {}
    config = deepcopy(saved) if saved.get('managed_options') else _request_options_for(offering)
    fields = config.get('fields', [])
    if not isinstance(fields, list):
        fields = []

    for field in fields:
        key = field.get('key', '')
        choices = field.get('choices')
        if not key or not isinstance(choices, list):
            continue
        updated_choices = []
        for index, choice in enumerate(choices):
            old_value = choice if isinstance(choice, str) else choice.get('value', '')
            old_label = old_value if isinstance(choice, str) else choice.get('label', old_value)
            value = request.form.get(f'choice_{key}_{index}_value', old_value).strip()[:100]
            label = request.form.get(f'choice_{key}_{index}_label', old_label).strip()[:150]
            if value:
                updated_choices.append({
                    'value': value,
                    'label': label or value,
                    'enabled': request.form.get(f'choice_{key}_{index}_enabled') == '1',
                })
        new_values = request.form.get(f'choice_{key}_new', '')
        for new_value in new_values.splitlines():
            clean_value = new_value.strip()[:100]
            if clean_value and all(item['value'].casefold() != clean_value.casefold() for item in updated_choices):
                updated_choices.append({'value': clean_value, 'label': clean_value, 'enabled': True})
        if field.get('required') and not any(item['enabled'] for item in updated_choices):
            flash(f"Keep at least one {field.get('label', 'option').lower()} enabled.", 'error')
            return redirect(url_for('admin_services.services'))
        field['choices'] = updated_choices

    config['managed_options'] = True
    config['fields'] = fields
    offering.options = config
    db.session.commit()
    flash('Service options updated.', 'success')
    return redirect(url_for('admin_services.services'))
