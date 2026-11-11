"""Safe cleanup helpers for private request uploads and payment receipts."""

import os
from datetime import datetime, timedelta

import click

from users import db
from users.models import PrintRequest


def _remove_private_file(instance_path, relative_path, expected_folder):
    """Delete one file only when it resolves inside the expected private folder."""
    if not relative_path or not isinstance(relative_path, str):
        return False
    normalized = relative_path.replace('\\', '/').lstrip('/')
    expected_prefix = f'{expected_folder}/'
    if not normalized.startswith(expected_prefix):
        return False

    allowed_root = os.path.realpath(os.path.join(instance_path, expected_folder))
    candidate = os.path.realpath(os.path.join(instance_path, normalized))
    try:
        if os.path.commonpath([allowed_root, candidate]) != allowed_root:
            return False
    except ValueError:
        return False
    if not os.path.isfile(candidate):
        return False
    os.remove(candidate)
    return True


def cleanup_request_files(print_request, instance_path, include_receipt=True):
    """Remove request attachments and optionally its older payment receipt."""
    removed = 0
    for path in print_request.uploaded_file_paths():
        removed += int(_remove_private_file(instance_path, path, 'request_uploads'))
    print_request.file_paths = []

    if include_receipt and print_request.payment_receipt_path:
        removed += int(_remove_private_file(
            instance_path, print_request.payment_receipt_path, 'payment_receipts'
        ))
        print_request.payment_receipt_path = None
    return removed


def register_cleanup_command(app):
    """Register a preview-first command for cleaning old terminal requests."""
    @app.cli.command('cleanup-files')
    @click.option('--days', default=90, show_default=True, type=click.IntRange(min=1))
    @click.option('--confirm', is_flag=True, help='Actually delete the listed files.')
    def cleanup_files(days, confirm):
        """Clean files for completed, declined, or cancelled old requests."""
        cutoff = datetime.now() - timedelta(days=days)
        requests = PrintRequest.query.filter(
            PrintRequest.status.in_({'completed', 'declined', 'cancelled'}),
            PrintRequest.created_at < cutoff,
        ).all()
        file_count = sum(
            len(item.uploaded_file_paths()) + int(bool(item.payment_receipt_path))
            for item in requests
        )
        click.echo(
            f'Found {len(requests)} eligible request(s) with up to {file_count} file(s).'
        )
        if not confirm:
            click.echo('Preview only. Run again with --confirm to delete these files.')
            return
        removed = sum(cleanup_request_files(item, app.instance_path, include_receipt=True) for item in requests)
        db.session.commit()
        click.echo(f'Removed {removed} private file(s). Request records were preserved.')
