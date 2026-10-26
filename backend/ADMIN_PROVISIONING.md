# Local administrator provisioning

Administrator creation is intentionally unavailable through public registration or an HTTP endpoint. Run the local command only from a trusted operator account on a machine allowed to reach the configured database.

## Environment setup

The script uses the existing `app.core.config.settings` configuration and `SessionLocal`. From `D:\Farmerlinkage\backend`, ensure `.env` is configured using the variable names in `.env.example`. Supply either `DATABASE_URL` or all of `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`. The command refuses to run if it would rely on the application's development defaults. Keep `.env` private and do not paste its values into terminals, tickets, or chat.

## Provision a separate administrator

In PowerShell, run:

```powershell
Set-Location D:\Farmerlinkage\backend
python .\provision_admin.py
```

Enter the new administrator's email, full name, and phone when prompted. Enter and confirm the password at the hidden prompts. The password must satisfy the existing registration rules (at least eight characters, including a letter and a digit, and no more than 72 UTF-8 bytes); the existing bcrypt hashing utility stores only its hash. The command validates the supplied identity, refuses an existing email or phone, and creates a new active `ADMIN` account in one transaction. It never changes an existing user. On success, sign in through the existing `/api/auth/login` endpoint and use that account's token for administrator-only APIs.

The script does not create a database, apply migrations, or print database configuration. Run it only after the existing schema has been migrated.
