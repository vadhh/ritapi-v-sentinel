# Development Setup (Fast UI Mode)

This guide helps you set up a local development environment with **Auto-Login** and **Hot Reload** enabled.

## 1. Initial Setup

```bash
# Navigate to the Django project
cd projects/ritapi_django

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install browser-sync  # Optional: for hot reload
```

## 2. Environment Configuration

Create a `.env` file in `projects/ritapi_django/.env` with these settings to use a local SQLite database:

```ini
DJANGO_SECRET_KEY=dev-secret-key-123
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

## 3. Database Initialization

```bash
python manage.py migrate
python manage.py createsuperuser  # Create your dev admin account
```

## 4. Running the Dev Environment

### Terminal 1: Django Server
```bash
python manage.py runserver
```

### Terminal 2: Hot Reload (UI Development)
This will open `localhost:3000`. Any changes to templates or CSS will sync instantly without manual refresh.
```bash
npx browser-sync start --proxy "localhost:8000" --files "templates/**/*.html, static/**/*.css"
```

---
**Note:** The `DevAutoLoginMiddleware` is active when `DJANGO_DEBUG=True`. It will automatically log you in as the first superuser found in the database.
