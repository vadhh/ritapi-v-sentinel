# UI Development Workflow

This document explains how to develop the Ritapi V-Sentinel UI efficiently without the hassle of constant reloads or login prompts.

## Quick Start (The "Fast" Mode)

To start developing the UI with **Auto-Login** and **Instant Reloads**, follow these steps:

1.  **Navigate to the project:**
    ```bash
    cd projects/ritapi_django
    ```

2.  **Start the Django server:**
    ```bash
    # Uses the local venv and SQLite database
    ./venv/bin/python manage.py runserver
    ```

3.  **Start Hot Reload (In a new terminal):**
    ```bash
    npx browser-sync start --proxy "localhost:8000" --files "templates/**/*.html, static/**/*.css"
    ```

4.  **Open Browser:**
    Navigate to `http://localhost:3000`. You will be **automatically logged in** as the admin user.

---

## Features

### 1. Auto-Login (Dev Mode)
When `DJANGO_DEBUG=True`, the `DevAutoLoginMiddleware` automatically authenticates you as the first superuser in the database. 
- **No more login screens** during local development.
- **Permission checks** still work (you are treated as a superuser).
- **Logic Location:** `projects/ritapi_django/authentication/dev_middleware.py`

### 2. Hot Reloading
By using the BrowserSync proxy (`localhost:3000`), the browser will automatically refresh whenever you save:
- A Django Template (`.html`)
- A CSS file (`.css`)
- A JavaScript file (`.js`)

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'environ'"
Ensure you are using the virtual environment:
```bash
source venv/bin/activate
```

### "Database is locked"
If using the local SQLite database, ensure no other process is holding a heavy lock on `db.sqlite3`.

### Port Conflicts
- If `8000` is busy: `python manage.py runserver 8001` (Update BrowserSync proxy port accordingly).
- If `3000` is busy: BrowserSync will automatically try `3001`.

---

## Technical Details
- **Settings:** The middleware is injected into `MIDDLEWARE` in `settings.py` ONLY when `DEBUG` is true.
- **Database:** Local dev uses `sqlite3` via the `DATABASE_URL` in `.env`.
