# PrintWise SMTP setup

PrintWise sends real email for new-account verification and password recovery.
Credentials are read from environment variables and must not be written into
the Python files.

## Gmail example on PowerShell

Use a Google App Password, not the normal password for the Gmail account.

```powershell
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "your-address@gmail.com"
$env:SMTP_PASSWORD = "your-16-character-app-password"
$env:SMTP_FROM_EMAIL = "your-address@gmail.com"
$env:SMTP_USE_TLS = "true"
$env:SMTP_USE_SSL = "false"
$env:PUBLIC_BASE_URL = "http://127.0.0.1:5000"
flask run
```

For a deployed website, set `PUBLIC_BASE_URL` to the public HTTPS address,
such as `https://printwise.example.com`. Configure these values in the hosting
provider's secret or environment settings instead of committing them to Git.

Verification links expire after 24 hours. Password reset links expire after
one hour and become invalid as soon as the password changes.
