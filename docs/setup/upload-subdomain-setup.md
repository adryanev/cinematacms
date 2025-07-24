# Upload Subdomain Configuration for CinemataCMS

This document explains how the upload subdomain (e.g., `uploads.cinemata.org`) is configured to handle file uploads through the `/fu/` endpoint in CinemataCMS.

## Overview

The upload subdomain has been configured to:
- Handle all file upload operations through the `/fu/` endpoint
- Redirect all other requests to the main domain
- Support both HTTP and HTTPS with proper SSL configurations
- Allow large file uploads up to 800MB (4GB in production)
- Support cross-origin requests with custom CORS middleware
- Work across multiple environments (development, staging, production)

## Architecture

The upload subdomain system uses a multi-environment approach with:
- **Main domains**: `dev.cinemata.org`, `cinemata.org`, `stage.cinemata.org`
- **Upload domains**: `dev-uploads.cinemata.org`, `uploads.cinemata.org`, `stage-uploads.cinemata.org`
- **Local development**: `cinemata.local` and `uploads.cinemata.local`

## Configuration Components

### 1. Django Settings

The system uses environment-specific domain configurations instead of single variables:

#### Main Settings (`cms/settings.py`)
```python
import os

# Domain Configuration
MAIN_DOMAINS = [
    "https://dev.cinemata.org",
    "https://cinemata.org",
    "https://stage.cinemata.org",
]
UPLOAD_DOMAINS = [
    "https://dev-uploads.cinemata.org",
    "https://uploads.cinemata.org",
    "https://stage-uploads.cinemata.org",
]

# Dynamic hostname extraction
ALL_DOMAINS_HOSTNAMES = [
    url.replace("https://", "").replace("http://", "")
    for url in MAIN_DOMAINS + UPLOAD_DOMAINS
]

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    *ALL_DOMAINS_HOSTNAMES,
]

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = MAIN_DOMAINS + UPLOAD_DOMAINS

# Cookie Settings for Cross-Domain Support
SESSION_COOKIE_DOMAIN = ".cinemata.org"
CSRF_COOKIE_DOMAIN = ".cinemata.org"
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True

# Upload subdomain configuration (fallback)
UPLOAD_SUBDOMAIN = os.getenv('UPLOAD_SUBDOMAIN', 'uploads.cinemata.org')
```

#### Development Settings (`cms/dev_settings.py`)
```python
import os

# Development-specific domains
MAIN_DOMAINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://dev.cinemata.org",
]

UPLOAD_DOMAINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://dev-uploads.cinemata.org",
]

# Localhost cookie settings
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None

# X-Accel-Redirect disabled for development
USE_X_ACCEL_REDIRECT = False
```

#### Docker/Local Settings (`deploy/docker/local_settings.py`)
```python
import os
import re

# Extract domain from FRONTEND_HOST
FRONTEND_DOMAIN = re.sub(r'^https?://', '', FRONTEND_HOST)

# Dynamic configuration based on environment
UPLOAD_SUBDOMAIN = os.getenv('UPLOAD_SUBDOMAIN', 'localhost')

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    FRONTEND_DOMAIN,
    UPLOAD_SUBDOMAIN,
    f'.{FRONTEND_DOMAIN}' if '.' in FRONTEND_DOMAIN else FRONTEND_DOMAIN,
]

# Dynamic CSRF origins
CSRF_TRUSTED_ORIGINS = [
    f"http://{FRONTEND_DOMAIN}",
    f"https://{FRONTEND_DOMAIN}",
    f"http://{UPLOAD_SUBDOMAIN}",
    f"https://{UPLOAD_SUBDOMAIN}",
]
```

### 2. Custom CORS Middleware

The system includes a custom `UploadCorsMiddleware` (`uploader/middleware.py`) that handles CORS for upload endpoints:

```python
class UploadCorsMiddleware(MiddlewareMixin):
    def _add_cors_headers(self, request, response):
        origin = request.META.get('HTTP_ORIGIN', '')

        # Get allowed origins from settings
        main_domains = getattr(settings, 'MAIN_DOMAINS', [])
        upload_domains = getattr(settings, 'UPLOAD_DOMAINS', [])
        allowed_origins = main_domains + upload_domains

        if origin in allowed_origins:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'

        # Set other CORS headers
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = (
            'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,'
            'Content-Type,Range,X-CSRFToken,Authorization'
        )
```

### 3. Frontend Configuration

The frontend uses dynamic template variables instead of hardcoded URLs:

#### Context Processor (`files/context_processors.py`)
```python
def stuff(request):
    ret = {}
    if request.is_secure():
        ret["FRONTEND_HOST"] = settings.SSL_FRONTEND_HOST
        ret["UPLOAD_HOST"] = f"https://{settings.UPLOAD_SUBDOMAIN}"
    else:
        ret["FRONTEND_HOST"] = settings.FRONTEND_HOST
        ret["UPLOAD_HOST"] = f"http://{settings.UPLOAD_SUBDOMAIN}"
    # ... other context variables
    return ret
```

#### FineUploader Configuration (`templates/cms/add-media.html`)
```javascript
var default_concurrent_chunked_uploader = new qq.FineUploader({
    debug: false,
    element: document.querySelector('.media-uploader'),
    request: {
        endpoint: '{{UPLOAD_HOST}}{% url 'uploader:upload' %}',
        customHeaders: {
            'X-CSRFToken': getCSRFToken('csrftoken')
        },
        withCredentials: true
    },
    cors: {
        expected: true,
        sendCredentials: true
    },
    chunking: {
        enabled: true,
        concurrent: { enabled: true },
        success: {
            endpoint: '{{UPLOAD_HOST}}{% url 'uploader:upload' %}?done',
        },
    },
    validation: {
        itemLimit: {{UPLOAD_MAX_FILES_NUMBER}},
        sizeLimit: {{UPLOAD_MAX_SIZE}}, // 4GB default
    },
});
```

### 4. Nginx Configuration

#### Production Configuration (`deploy/mediacms.io`)
```nginx
# Upload subdomain for file uploads (HTTP)
server {
    listen 80;
    server_name uploads.cinemata.local;

    gzip on;
    access_log /var/log/nginx/upload.cinemata.local.access.log;
    error_log  /var/log/nginx/upload.cinemata.local.error.log warn;

    # Redirect all non-upload requests to main domain
    location / {
        return 301 http://cinemata.local$request_uri;
    }

    # Handle file upload endpoint with dynamic CORS
    location /fu/ {
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,X-CSRFToken';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,X-CSRFToken' always;
        add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;

        include /etc/nginx/uwsgi_params;
        uwsgi_pass 127.0.0.1:9000;
    }
}

# Upload subdomain for file uploads (HTTPS)
server {
    listen 443 ssl;
    server_name uploads.cinemata.local;

    ssl_certificate_key  /etc/letsencrypt/live/cinemata.local/privkey.pem;
    ssl_certificate  /etc/letsencrypt/live/cinemata.local/fullchain.pem;
    ssl_dhparam /etc/nginx/dhparams/dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;

    # Redirect all non-upload requests to main domain
    location / {
        return 301 https://cinemata.local$request_uri;
    }

    # Handle file upload endpoint
    location /fu/ {
        proxy_request_buffering off;
        include /etc/nginx/uwsgi_params;
        uwsgi_pass 127.0.0.1:9000;
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }

    # Block all other paths on upload subdomain
    location ~ ^/(?!fu/|health) {
        return 301 https://cinemata.local$request_uri;
    }
}
```

#### Development Configuration (`deploy/dev-cinemata.conf`)
```nginx
# Upload subdomain (HTTPS) - Development environment
server {
    listen 443 ssl http2;
    server_name dev-uploads.cinemata.org;

    ssl_certificate /etc/letsencrypt/live/dev.cinemata.org-0001/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dev.cinemata.org-0001/privkey.pem;

    # File upload endpoint - CORS handled by Django middleware
    location /fu/ {
        proxy_request_buffering off;
        include /etc/nginx/uwsgi_params;
        uwsgi_pass 127.0.0.1:9000;
    }

    # Health check endpoint for monitoring
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }

    # Block all other paths on upload subdomain
    location ~ ^/(?!fu/|health) {
        return 301 https://dev.cinemata.org$request_uri;
    }
}
```

## Installation and Setup

### 1. Environment Configuration

The installation script (`install.sh`) automatically configures the upload subdomain:

```bash
# Set during installation
UPLOAD_SUBDOMAIN='upload.localhost'  # Default for local development

# Update nginx configuration
sed -i "s/cinemata\.local/$FRONTEND_HOST/g" deploy/mediacms.io
sed -i "s/upload\.cinemata\.local/$UPLOAD_SUBDOMAIN/g" deploy/mediacms.io
```

### 2. Environment Variables

Configure different subdomains for different environments:

```bash
# Development
export UPLOAD_SUBDOMAIN="dev-uploads.cinemata.org"

# Staging
export UPLOAD_SUBDOMAIN="stage-uploads.cinemata.org"

# Production
export UPLOAD_SUBDOMAIN="uploads.cinemata.org"

# Local development
export UPLOAD_SUBDOMAIN="uploads.cinemata.local"
```

### 3. DNS Configuration

Add DNS records for all environments:

```
# Production
uploads.cinemata.org        A    <production-server-ip>

# Development
dev-uploads.cinemata.org    A    <dev-server-ip>

# Staging
stage-uploads.cinemata.org  A    <staging-server-ip>

# Local development (add to /etc/hosts)
127.0.0.1    cinemata.local uploads.cinemata.local
```

### 4. SSL Certificate Setup

For production environments, ensure SSL certificates cover all subdomains:

```bash
# Let's Encrypt with multiple domains
certbot certonly --nginx \
  -d cinemata.org \
  -d uploads.cinemata.org \
  -d dev.cinemata.org \
  -d dev-uploads.cinemata.org \
  -d stage.cinemata.org \
  -d stage-uploads.cinemata.org
```

## Environment-Specific Configuration

### Development Environment
- **Main**: `http://localhost:8000` or `https://dev.cinemata.org`
- **Upload**: `http://localhost:8000` or `https://dev-uploads.cinemata.org`
- **Features**: Django development server, CORS allows localhost, no X-Accel-Redirect

### Staging Environment
- **Main**: `https://stage.cinemata.org`
- **Upload**: `https://stage-uploads.cinemata.org`
- **Features**: Production-like setup for testing

### Production Environment
- **Main**: `https://cinemata.org`
- **Upload**: `https://uploads.cinemata.org`
- **Features**: Full security headers, X-Accel-Redirect enabled, strict CORS

## Security Features

1. **Cross-Domain Authentication**: Uses `.cinemata.org` cookie domain for session sharing
2. **CSRF Protection**: Trusted origins include both main and upload domains
3. **CORS Middleware**: Custom middleware handles cross-origin requests securely
4. **SSL Security**: HSTS headers and secure cookie settings
5. **Content Security**: Upload size limits and file type restrictions

## URL Structure

### Main Site URLs
- **Production**: `https://cinemata.org/`
- **Development**: `https://dev.cinemata.org/`
- **Staging**: `https://stage.cinemata.org/`

### Upload Endpoint URLs
- **Production**: `https://uploads.cinemata.org/fu/upload/`
- **Development**: `https://dev-uploads.cinemata.org/fu/upload/`
- **Staging**: `https://stage-uploads.cinemata.org/fu/upload/`

### Local Development URLs
- **Main**: `http://cinemata.local/`
- **Upload**: `http://uploads.cinemata.local/fu/upload/`

## Troubleshooting

### CSRF Token Issues
1. Verify `CSRF_TRUSTED_ORIGINS` includes both main and upload domains
2. Check that cookies are being sent with `withCredentials: true`
3. Ensure cookie domain settings allow cross-subdomain sharing

### CORS Issues
1. Check `UploadCorsMiddleware` is properly configured in `MIDDLEWARE`
2. Verify origin headers are being sent correctly
3. Test with browser developer tools network tab

### Upload Size Limits
Adjust limits in multiple places:
```python
# Django settings
UPLOAD_MAX_SIZE = 800 * 1024 * 1000 * 5  # 4GB

# Nginx configuration
client_max_body_size 4G;
```

### SSL Certificate Issues
1. Ensure certificates cover all subdomains
2. Check certificate renewal includes new subdomains
3. Verify nginx SSL configuration is correct

### Performance Issues
1. Enable gzip compression in nginx
2. Use `proxy_request_buffering off` for large uploads
3. Consider CDN for upload endpoints in high-traffic scenarios

## Migration from Old Configuration

If upgrading from an older version:

1. **Update Django settings**: Replace single domain variables with `MAIN_DOMAINS`/`UPLOAD_DOMAINS` lists
2. **Add CORS middleware**: Ensure `UploadCorsMiddleware` is in `MIDDLEWARE` settings
3. **Update nginx config**: Use the new nginx configuration templates
4. **Update frontend**: Ensure templates use `{{UPLOAD_HOST}}` variable
5. **Test cross-domain**: Verify uploads work across different domains

## Monitoring and Logging

### Nginx Logs
- Upload access: `/var/log/nginx/uploads.cinemata.org.access.log`
- Upload errors: `/var/log/nginx/uploads.cinemata.org.error.log`

### Health Check Endpoint
- URL: `https://uploads.cinemata.org/health`
- Response: `200 OK` with `healthy` text

### Django Logging
Configure upload-specific logging in Django settings:
```python
LOGGING = {
    'loggers': {
        'uploader.middleware': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```