"""Small helpers shared by staff and admin printshop pages."""

import os
import uuid

from flask import abort, session
from werkzeug.utils import secure_filename

from users.models import Account


ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}


def signed_in_shop_worker():
    """Return the signed-in staff/admin account or reject another role."""
    if not session.get('user_id'):
        return None
    account = Account.query.get(session['user_id'])
    if account is None or not account.is_shop_worker():
        abort(403)
    return account


def account_printshop(account):
    """Return the first printshop connected to a staff/admin account."""
    shops = account.accessible_printshops()
    return shops[0] if shops else None


def save_image(upload, folder, path_prefix):
    """Validate and save one JPG or PNG, then return its relative path."""
    safe_name = secure_filename(upload.filename)
    extension = os.path.splitext(safe_name)[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    os.makedirs(folder, exist_ok=True)
    stored_name = f'{uuid.uuid4().hex}_{safe_name}'
    upload.save(os.path.join(folder, stored_name))
    return f'{path_prefix}/{stored_name}'
