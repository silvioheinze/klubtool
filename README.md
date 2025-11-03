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

- **Backend**: Django 5.2
- **Database**: PostgreSQL 15
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

Edit `.env` file with your configuration:

```env
# Database Configuration
POSTGRES_DB=klubtool
POSTGRES_USER=klubtooluser
POSTGRES_PASSWORD=klubtoolpassword
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Django Configuration
DJANGO_SECRET_KEY=your-secret-key-here-change-this-in-production
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Time Zone
TIME_ZONE=Europe/Vienna

# API Configuration
API_URL=http://localhost:8000/api/
```

#### Generating a Django Secret Key

To generate a secure Django secret key, you can use one of these methods:

**Method 1: Using Django's built-in function**
```bash
# Run this command to generate a secret key
docker compose exec app python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Method 2: Using Python directly**
```bash
# Generate a secret key using Python
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

**Method 3: Using Django's shell**
```bash
# Start Django shell and generate key
docker compose exec app python manage.py shell
# Then run: from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())
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

### 6. Access the Application

- **Main Application**: http://localhost
- **Admin Interface**: http://localhost/admin/
- **User Management**: http://localhost/user/

## 🏗️ Project Structure

```
klubtool/
├── app/                          # Django application
│   ├── main/                     # Main Django project
│   │   ├── settings.py          # Django settings
│   │   ├── urls.py              # Main URL configuration
│   │   └── wsgi.py              # WSGI configuration
│   ├── pages/                   # Pages app
│   │   ├── views.py             # Page views
│   │   └── urls.py              # Page URLs
│   ├── user/                    # User management app
│   │   ├── models.py            # Custom user model
│   │   ├── views.py             # User views
│   │   ├── forms.py             # User forms
│   │   └── urls.py              # User URLs
│   ├── static/                  # Static files
│   │   ├── css/                 # CSS files
│   │   ├── js/                  # JavaScript files
│   │   └── img/                 # Images
│   ├── templates/               # HTML templates
│   │   ├── _base.html          # Base template
│   │   ├── home.html           # Home page
│   │   ├── documentation.html  # Documentation page
│   │   └── help.html           # Help page
│   └── manage.py               # Django management script
├── nginx/                       # Nginx configuration
│   ├── Dockerfile              # Nginx Dockerfile
│   └── nginx.conf              # Nginx configuration
├── docker compose.yml          # Docker Compose configuration
├── Dockerfile                  # Django application Dockerfile
├── requirements.txt            # Python dependencies
├── env.example                 # Environment variables example
└── README.md                   # This file
```

## 🔧 Configuration

### Django Settings

The main Django settings are in `app/main/settings.py`. Key configurations include:

- **Database**: PostgreSQL with environment variable configuration
- **Static Files**: Configured for production with Nginx
- **Authentication**: django-allauth integration
- **Audit Logging**: django-auditlog for comprehensive logging
- **Internationalization**: Multi-language support

### Docker Configuration

- **Django App**: Python 3.13 with all dependencies
- **PostgreSQL**: Database with health checks
- **Nginx**: Reverse proxy with static file serving

## 🗄️ Database

The application uses PostgreSQL with the following features:

- **Custom User Model**: Extended user model with audit logging
- **Audit Trail**: All user actions are logged
- **Migrations**: Database schema versioning

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

## 👥 User Management

### Custom User Model

The application uses a custom user model (`CustomUser`) that extends Django's `AbstractUser` with:

- Email-based authentication
- Audit logging integration
- Custom admin interface

### User Features

- **Registration**: User signup with email verification
- **Authentication**: Login/logout functionality
- **Profile Management**: User settings and profile editing
- **Admin Interface**: Superuser management of all users

## 🔒 Security

### Authentication

- **django-allauth**: Comprehensive authentication system
- **Email Verification**: Required email verification for new accounts
- **Rate Limiting**: Login attempt rate limiting
- **CSRF Protection**: Built-in CSRF protection

### Audit Logging

- **django-auditlog**: Tracks all user actions
- **Comprehensive Logging**: User creation, modification, deletion
- **Admin Interface**: View audit logs in Django admin

## 🎨 Frontend

### Design System

- **Bootstrap 5**: Modern, responsive design framework
- **Bootstrap Icons**: Comprehensive icon library
- **Custom CSS**: Application-specific styling

### Templates

- **Base Template**: Consistent layout across all pages
- **Responsive Design**: Mobile-first approach
- **Internationalization**: Multi-language support ready

## 🎨 Color Palette

The application uses a custom color palette that overrides Bootstrap's default colors throughout the interface.

### Primary Colors

| Color | Hex Code | Usage | Bootstrap Class |
|-------|----------|-------|-----------------|
| **Dark Green** | `#5e833c` | Primary actions, main branding, focus states | `.btn-primary`, `.text-primary`, `.bg-primary` |
| **Light Green** | `#7da130` | Success states, positive actions, navbar background | `.btn-success`, `.text-success`, `.bg-success` |
| **Yellow** | `#f7f157` | Warnings, attention-grabbing elements | `.btn-warning`, `.text-warning`, `.bg-warning` |
| **Pink/Magenta** | `#ce2c77` | Errors, destructive actions, danger states | `.btn-danger`, `.text-danger`, `.bg-danger` |

### Color Implementation

The custom color palette is implemented through:

- **CSS Custom Properties**: Defined in `:root` selector for consistent theming
- **Bootstrap Overrides**: All Bootstrap color classes are overridden with custom values
- **Component Styling**: Buttons, alerts, badges, forms, and navigation use the custom palette
- **Accessibility**: Proper contrast ratios maintained for readability

### CSS Files

- **`custom-colors.css`**: Main color override file
- **`base.css`**: Additional styling and color demo classes
- **Loading Order**: Bootstrap → Custom Colors → Base CSS

### Testing

The color palette is thoroughly tested with 23 comprehensive test cases covering:

- ✅ File existence and structure
- ✅ Color value validation
- ✅ Bootstrap component overrides
- ✅ Template integration
- ✅ CSS variable definitions
- ✅ RGBA transparency effects
- ✅ Important declarations for proper override

### Usage Examples

```html
<!-- Primary button with custom dark green -->
<button class="btn btn-primary">Primary Action</button>

<!-- Success alert with custom light green -->
<div class="alert alert-success">Success message</div>

<!-- Warning badge with custom yellow -->
<span class="badge bg-warning">Warning</span>

<!-- Danger text with custom pink -->
<p class="text-danger">Error message</p>
```

## 🚀 Deployment

### Production Deployment

1. **Environment Variables**: Update `.env` with production values
2. **Security**: Change `DJANGO_SECRET_KEY` and disable `DEBUG`
3. **Database**: Configure production PostgreSQL instance
4. **Static Files**: Ensure static files are collected
5. **SSL**: Configure SSL certificates for HTTPS

### Environment Variables

```env
# Production Settings
DEBUG=False
DJANGO_SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com

# Database (if using external database)
POSTGRES_HOST=your-database-host
POSTGRES_PASSWORD=your-secure-password
```

## 🛠️ Development

### Local Development

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

## 📝 API Documentation

The application includes a basic API structure. API endpoints are configured in the main URL configuration.

### API Configuration

- **Base URL**: Configured via `API_URL` setting
- **Authentication**: Token-based authentication (can be extended)
- **Documentation**: Available at `/documentation/`

## 🐛 Troubleshooting

### Common Issues

1. **Static Files Not Loading**
   ```bash
   # Rebuild containers and collect static files
   docker compose down
   docker compose up --build -d
   docker compose exec app python manage.py collectstatic --noinput
   ```

2. **Database Connection Issues**
   ```bash
   # Check database health
   docker compose ps
   docker compose logs db
   ```

3. **Permission Issues**
   ```bash
   # Fix file permissions
   sudo chown -R $USER:$USER .
   ```

### Logs

```bash
# View all logs
docker compose logs

# View specific service logs
docker compose logs app
docker compose logs nginx
docker compose logs db
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:

1. Check the [documentation](http://localhost/documentation/)
2. Review the [help section](http://localhost/help/)
3. Open an issue on GitHub

## 🔄 Updates

To update the application:

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose down
docker compose up --build -d

# Run migrations
docker compose exec app python manage.py migrate
```