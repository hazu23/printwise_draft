"""Small application-wide security helpers."""

import secrets
from hmac import compare_digest

from flask import abort, g, request, session


SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS', 'TRACE'}


def csrf_token():
    """Return one unpredictable CSRF token for the current browser session."""
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def init_csrf(app):
    """Protect every state-changing request with a session CSRF token."""
    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def protect_csrf():
        if request.method in SAFE_METHODS:
            return None
        expected = session.get('_csrf_token')
        supplied = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        if not expected or not supplied or not compare_digest(expected, supplied):
            abort(400, description='The security token is missing or expired. Please try again.')
        return None


def init_browser_security(app, production=False):
    """Add a per-request CSP nonce and defensive browser headers."""
    app.jinja_env.globals['csp_nonce'] = lambda: g.get('csp_nonce', '')

    @app.before_request
    def create_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(18)

    @app.after_request
    def add_security_headers(response):
        nonce = g.get('csp_nonce', '')
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            f"script-src 'self' https://cdn.jsdelivr.net 'nonce-{nonce}'; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if session.get('user_id'):
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['Pragma'] = 'no-cache'
        if production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
