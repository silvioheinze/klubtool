# Klubtool

A modern Django-based political group management system built with Docker, PostgreSQL, and Nginx.

## 🚀 Features

- **User Management**: Custom user model with authentication and authorization
- **Admin Interface**: Django admin with custom user management
- **Audit Logging**: Comprehensive audit trail for all user actions
- **Modern UI**: Bootstrap-based responsive design
- **Docker Support**: Complete containerization with Docker Compose
- **PostgreSQL Database**: Robust database backend
- **Nginx Reverse Proxy**: Production-ready web server configuration

## 🛠️ Tech Stack

- **Backend**: Django 6.0
- **Database**: PostgreSQL 17
- **Web Server**: Nginx 1.25
- **Containerization**: Docker & Docker Compose
- **Authentication**: django-allauth
- **Audit Logging**: django-auditlog
- **Frontend**: Bootstrap 5, Bootstrap Icons
- **Python**: 3.13

## 📋 Prerequisites

- Docker
- Docker Compose
- Git

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd klubtool
```

### 2. Set Up Environment Variables

Copy the example environment file and configure it:

```bash
cp env.example .env
```

#### Generating a Django Secret Key

To generate a secure Django secret key:
```bash
# Run this command to generate a secret key
docker compose exec app python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the generated key and replace `your-secret-key-here-change-this-in-production` in your `.env` file with the actual secret key.

### 3. Build and Start the Application

```bash
# Build and start all services
docker compose up --build -d

# Check service status
docker compose ps
```

### 4. Run Database Migrations

```bash
# Apply database migrations
docker compose exec app python manage.py migrate

# Collect static files
docker compose exec app python manage.py collectstatic --noinput
```

### 5. Create a Superuser (Optional)

```bash
docker compose exec app python manage.py createsuperuser
```

## 🏗️ Project Structure

```
klubtool/
├── app/                          # Django application
│   ├── main/                     # Main Django project
│   │   ├── settings.py          # Django settings
│   │   ├── urls.py              # Main URL configuration
│   │   ├── wsgi.py              # WSGI configuration
│   │   ├── asgi.py              # ASGI configuration
│   │   ├── enums.py             # Shared enumerations
│   │   └── logging_filters.py   # Logging configuration
│   ├── pages/                   # Pages app (home, calendar, documentation)
│   │   ├── views.py             # Page views
│   │   ├── urls.py              # Page URLs
│   │   ├── context_processors.py # Template context
│   │   └── models.py            # Page models
│   ├── user/                    # User management app
│   │   ├── models.py            # Custom user model
│   │   ├── views.py             # User views
│   │   ├── forms.py             # User forms
│   │   ├── urls.py              # User URLs
│   │   ├── adapters.py          # django-allauth adapters
│   │   └── middleware.py        # User middleware
│   ├── group/                   # Political group/party management
│   │   ├── models.py            # Groups, members, meetings
│   │   ├── views.py             # Group views
│   │   ├── forms.py             # Group forms
│   │   ├── urls.py              # Group URLs
│   │   └── templatetags/        # Group template tags
│   ├── district/                # District council/committee management
│   │   ├── models.py            # Districts, councils, committees, sessions
│   │   ├── views.py             # District views
│   │   ├── forms.py             # District forms
│   │   └── urls.py              # District URLs
│   ├── motion/                  # Motions and questions
│   │   ├── models.py            # Motions, votes, questions
│   │   ├── views.py             # Motion views
│   │   ├── forms.py             # Motion forms
│   │   ├── urls.py              # Motion URLs
│   │   ├── question_urls.py     # Question-specific URLs
│   │   └── templatetags/        # Motion template tags
│   ├── static/                  # Static files
│   │   ├── css/                 # CSS files (Bootstrap, custom-colors, base)
│   │   ├── js/                  # JavaScript files
│   │   ├── fonts/               # Font files
│   │   └── robots.txt           # Robots configuration
│   ├── templates/               # HTML templates
│   │   ├── _base.html           # Base template
│   │   ├── home.html            # Home page
│   │   ├── documentation.html  # Documentation page
│   │   ├── help.html            # Help page
│   │   ├── account/             # django-allauth templates
│   │   ├── group/               # Group app templates
│   │   ├── district/            # District app templates
│   │   ├── motion/              # Motion app templates
│   │   ├── pages/               # Pages app templates
│   │   └── user/                # User app templates
│   ├── locale/                  # Translations (i18n)
│   │   └── de/LC_MESSAGES/      # German translations
│   ├── media/                   # User-uploaded files
│   └── manage.py                # Django management script
├── .github/                     # GitHub configuration
│   └── workflows/               # GitHub Actions
│       ├── docker-build.yml     # Docker build workflow
│       └── test.yml             # Django test workflow
├── nginx/                       # Nginx configuration
│   ├── Dockerfile               # Nginx Dockerfile
│   └── nginx.conf               # Nginx configuration
├── docker-compose.yml           # Docker Compose configuration
├── docker-compose.prod.yml      # Production Docker Compose overrides
├── Dockerfile                   # Django application Dockerfile
├── requirements.txt             # Python dependencies
├── env.example                  # Environment variables example
└── README.md                    # This file
```

## 🔧 Configuration

### Database Commands

```bash
# Create a new migration
docker compose exec app python manage.py makemigrations

# Apply migrations
docker compose exec app python manage.py migrate

# Reset database (WARNING: This will delete all data)
docker compose down -v
docker compose up -d
```

### Importing Database Dump

To import a SQL dump file (e.g., `pgsql_klubtool_db_20251119-030000.sql.gz`) into the database:

**Option 1: Import into existing database (may show errors if tables already exist)**
```bash
gunzip -c pgsql_klubtool_db_20251119-030000.sql.gz | docker compose exec -T db psql -U klubtooluser -d klubtool
```

**Option 2: Fresh import (drops and recreates database - WARNING: This will delete all existing data)**
```bash
# Drop and recreate the database
docker compose exec db psql -U klubtooluser -d postgres -c "DROP DATABASE IF EXISTS klubtool;"
docker compose exec db psql -U klubtooluser -d postgres -c "CREATE DATABASE klubtool;"

# Import the dump
gunzip -c pgsql_klubtool_db_20251119-030000.sql.gz | docker compose exec -T db psql -U klubtooluser -d klubtool
```

**Note:** Replace `pgsql_klubtool_db_20251119-030000.sql.gz` with your actual dump filename.

### Translation Commands

The application supports internationalization (i18n) with Django's translation framework.

```bash
# Extract strings for all languages
docker compose exec app python manage.py makemessages -a

# Compile messages for all languages
docker compose exec app python manage.py compilemessages
```

**Translation Workflow:**

1. **Extract strings**: Run `makemessages` to scan the codebase for translatable strings (marked with `{% trans %}` or `gettext`)
2. **Edit translations**: Open `app/locale/<language>/LC_MESSAGES/django.po` and add/edit translations
3. **Compile messages**: Run `compilemessages` to generate `.mo` files that Django uses at runtime

**Note:** After editing `.po` files, you must run `compilemessages` for the changes to take effect.


## MCP (district events, motions, inquiries)

Klubtool exposes an MCP server at `/mcp/` so tools like Claude can list and manage **district events**, **motions (Anträge)**, and **inquiries (Anfragen)** with the same permissions as the web UI.

### 1. Create a token

1. Log in and open **Settings** (`/user/settings/`).
2. Under **MCP Access**, click **Create MCP token** (or **Reset MCP token**).
3. Copy the **MCP server URL** and **Bearer token** immediately — the raw token is shown only once.

### 2. Add in Claude

Use the **HTTPS** MCP server URL from Settings (for example `https://klub.neubauergruene.at/mcp/`) and the Bearer token.

#### Claude (claude.ai and Claude Desktop)

1. Open **Customize → Connectors → Add custom connector**.
2. Paste the MCP server URL.
3. Under **Request headers**, add `Authorization`.
4. Set the value to `Bearer YOUR_TOKEN_HERE` (include the word `Bearer` and a space).
5. Click **Add**. In a chat, open **+ → Connectors** and enable the connector.

Team/Enterprise owners add the connector under **Organization settings → Connectors → Add → Custom** (choose **Web** if asked). Members then connect it under **Customize → Connectors**.

If the Request headers field is not available, use Claude Code or the Desktop config below.

#### Claude Code

```bash
claude mcp add --transport http klubtool https://klub.neubauergruene.at/mcp/ \
  --header "Authorization: Bearer YOUR_TOKEN_HERE"
```

Or add `.mcp.json` in the project:

```json
{
  "mcpServers": {
    "klubtool": {
      "type": "http",
      "url": "https://klub.neubauergruene.at/mcp/",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

#### Claude Desktop config file

If you configure MCP via `claude_desktop_config.json` instead of Connectors, bridge the remote HTTPS server with `mcp-remote`:

```json
{
  "mcpServers": {
    "klubtool": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://klub.neubauergruene.at/mcp/",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

Restart Claude Desktop after saving. Config locations: macOS `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows `%APPDATA%\Claude\claude_desktop_config.json`.

For local development the app still listens on HTTP; Settings always shows `https://`. Use HTTPS in production, or `http://localhost/mcp/` (nginx) / `http://localhost:8000/mcp/` when talking to Django directly.

### 3. Available tools

| Tool | Description |
|------|-------------|
| `list_districts` | Districts you can access (`can_manage_events` flag) |
| `list_district_events` | Events for a district |
| `get_district_event` | Single event by id |
| `create_district_event` | Create event (district managers only) |
| `update_district_event` | Update event (managers only) |
| `delete_district_event` | Delete event (managers only) |
| `get_motion` | Single motion by id (view access) |
| `create_motion` | Create motion as draft (group members / `motion.create`) |
| `update_motion` | Update motion; omitted fields unchanged; status not editable |
| `get_inquiry` | Single inquiry by id (view access) |
| `create_inquiry` | Create inquiry as draft (group members / `motion.create`) |
| `update_inquiry` | Update inquiry; omitted fields unchanged; status not editable |

Example `create_district_event` arguments:

```json
{
  "district_id": 1,
  "title": "District assembly",
  "scheduled_date": "2026-09-15T18:00:00+02:00",
  "description": "Optional details",
  "external_link": "https://example.com"
}
```

Example `create_motion` arguments:

```json
{
  "title": "Motion title",
  "session_id": 42,
  "group_id": 3,
  "text": "Motion text",
  "rationale": "Why this motion",
  "motion_type": "general",
  "party_ids": [1],
  "tags": ["housing", "budget"]
}
```

`group_id` is optional when the user belongs to a group (defaults to the first accessible group). On create, motions are always saved as `draft` and do not accept `intervention_ids` (Wortmeldung); use `update_motion` with `intervention_ids` to set speakers after creation.

## 🛠️ Development

### District Development

```bash
# Start development environment
docker compose up -d

# View logs
docker compose logs -f app

# Run Django shell
docker compose exec app python manage.py shell

# Run tests
docker compose exec app python manage.py test
```

### Adding New Apps

1. Create the app: `docker compose exec app python manage.py startapp myapp`
2. Add to `INSTALLED_APPS` in `settings.py`
3. Create models, views, and URLs
4. Run migrations: `docker compose exec app python manage.py makemigrations myapp`

### Static Files

```bash
# Collect static files
docker compose exec app python manage.py collectstatic --noinput

# Find static files
docker compose exec app python manage.py findstatic css/bootstrap.min.css
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the European Union Public Licence v. 1.2 (EUPL-1.2) - see the [LICENSE](LICENSE) file for details.