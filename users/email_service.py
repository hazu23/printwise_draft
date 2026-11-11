"""SMTP delivery and secure account-link helpers for PrintWise."""

import hashlib
import smtplib
import ssl
from email.message import EmailMessage

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


class EmailDeliveryError(RuntimeError):
    """Raised when PrintWise cannot hand an email to the SMTP server."""


class EmailService:
    """Send plain-text email using the SMTP settings from the Flask app."""

    def __init__(self, app):
        self.host = app.config.get("SMTP_HOST", "")
        self.port = app.config.get("SMTP_PORT", 587)
        self.username = app.config.get("SMTP_USERNAME", "")
        self.password = app.config.get("SMTP_PASSWORD", "")
        self.sender = app.config.get("SMTP_FROM_EMAIL", "") or self.username
        self.use_tls = app.config.get("SMTP_USE_TLS", True)
        self.use_ssl = app.config.get("SMTP_USE_SSL", False)

    def is_configured(self):
        """Return True when the minimum SMTP settings are available."""
        return bool(self.host and self.port and self.sender)

    def send(self, recipient, subject, body):
        """Send one message or raise EmailDeliveryError when delivery fails."""
        if not self.is_configured():
            raise EmailDeliveryError("SMTP is not configured.")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.sender
        message["To"] = recipient
        message.set_content(body)

        try:
            context = ssl.create_default_context()
            if self.use_ssl:
                with smtplib.SMTP_SSL(
                    self.host, self.port, timeout=20, context=context
                ) as server:
                    self._login_and_send(server, message)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=20) as server:
                    server.ehlo()
                    if self.use_tls:
                        server.starttls(context=context)
                        server.ehlo()
                    self._login_and_send(server, message)
        except (OSError, smtplib.SMTPException) as error:
            raise EmailDeliveryError("The SMTP server could not send the email.") from error

    def _login_and_send(self, server, message):
        """Authenticate when credentials were supplied, then send the message."""
        if self.username:
            server.login(self.username, self.password)
        server.send_message(message)


class AccountTokenService:
    """Create and verify signed links without saving raw tokens in MySQL."""

    VERIFY_SALT = "printwise-email-verification"
    RESET_SALT = "printwise-password-reset"

    def __init__(self, secret_key):
        self.serializer = URLSafeTimedSerializer(secret_key)

    def create_verification_token(self, account):
        """Create a token tied to the account's current email address."""
        return self.serializer.dumps(
            {"account_id": account.id, "email": account.email},
            salt=self.VERIFY_SALT,
        )

    def read_verification_token(self, token, max_age):
        """Return verification data, or None for an invalid or expired token."""
        return self._read_token(token, self.VERIFY_SALT, max_age)

    def create_password_reset_token(self, account):
        """Create a token invalidated automatically after the password changes."""
        return self.serializer.dumps(
            {
                "account_id": account.id,
                "password_key": self._password_key(account.password_hash),
            },
            salt=self.RESET_SALT,
        )

    def read_password_reset_token(self, token, max_age):
        """Return reset data, or None for an invalid or expired token."""
        return self._read_token(token, self.RESET_SALT, max_age)

    def password_token_matches(self, account, token_data):
        """Return True when the reset token matches the current password hash."""
        return token_data.get("password_key") == self._password_key(
            account.password_hash
        )

    def _read_token(self, token, salt, max_age):
        try:
            data = self.serializer.loads(token, salt=salt, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _password_key(password_hash):
        return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:24]
