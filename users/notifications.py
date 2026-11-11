"""Saved notifications shared by customers, staff members, and admins."""

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from users import db
from users.models import Account, Notification, PrintShop


notifications_bp = Blueprint("notifications", __name__)


def notify_account(account_id, title, message, link=None, notification_type="general"):
    """Queue one notification for an account in the current DB transaction."""
    if not account_id:
        return
    db.session.add(Notification(
        account_id=account_id,
        title=title[:120],
        message=message[:500],
        link=(link or "")[:255] or None,
        notification_type=notification_type[:30],
    ))


def notify_printshop_workers(printshop_id, title, message, link=None, notification_type="shop"):
    """Queue the same alert for every active staff member and admin of a shop."""
    shop = PrintShop.query.get(printshop_id)
    if shop is None:
        return

    recipient_ids = set()
    if shop.admin and shop.admin.account and shop.admin.account.is_active:
        recipient_ids.add(shop.admin.account_id)
    for staff_member in shop.staff_members:
        if staff_member.account and staff_member.account.is_active:
            recipient_ids.add(staff_member.account_id)

    for account_id in recipient_ids:
        notify_account(account_id, title, message, link, notification_type)


def register_notification_context(app):
    """Make the unread count and latest alerts available in the shared navbar."""
    @app.context_processor
    def notification_context():
        account_id = session.get("user_id")
        if not account_id:
            return {"nav_notifications": [], "unread_notification_count": 0}
        try:
            latest = Notification.query.filter_by(account_id=account_id).order_by(
                Notification.created_at.desc(), Notification.id.desc()
            ).limit(5).all()
            unread_count = Notification.query.filter_by(
                account_id=account_id, is_read=False
            ).count()
            return {
                "nav_notifications": latest,
                "unread_notification_count": unread_count,
            }
        except SQLAlchemyError:
            # The 500 error page must still render if the database itself fails.
            db.session.rollback()
            return {"nav_notifications": [], "unread_notification_count": 0}


def _require_account():
    account_id = session.get("user_id")
    if not account_id:
        return None, redirect(url_for("auth.login"))
    account = Account.query.get(account_id)
    if account is None:
        session.clear()
        return None, redirect(url_for("auth.login"))
    return account, None


@notifications_bp.route("/notifications")
def notification_page():
    """Show all notifications for the signed-in account."""
    account, login_redirect = _require_account()
    if login_redirect:
        return login_redirect
    items = Notification.query.filter_by(account_id=account.id).order_by(
        Notification.created_at.desc(), Notification.id.desc()
    ).all()
    return render_template("notifications.html", notifications=items)


@notifications_bp.route("/notifications/read-all", methods=("POST",))
def mark_all_read():
    """Mark all of the current user's notifications as read."""
    account, login_redirect = _require_account()
    if login_redirect:
        return login_redirect
    Notification.query.filter_by(account_id=account.id, is_read=False).update(
        {Notification.is_read: True}, synchronize_session=False
    )
    db.session.commit()
    return redirect(url_for("notifications.notification_page"))


@notifications_bp.route("/notifications/<int:notification_id>/read", methods=("POST",))
def mark_one_read(notification_id):
    """Mark one owned notification as read and optionally open its destination."""
    account, login_redirect = _require_account()
    if login_redirect:
        return login_redirect
    item = Notification.query.filter_by(
        id=notification_id, account_id=account.id
    ).first_or_404()
    item.is_read = True
    db.session.commit()
    destination = request.form.get("destination", "").strip()
    if destination and destination.startswith("/") and not destination.startswith("//"):
        return redirect(destination)
    return redirect(url_for("notifications.notification_page"))
