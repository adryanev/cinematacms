# Secure File Serving with X-Accel-Redirect

This implementation provides secure file serving for CinemaCMS using Django authentication/authorization combined with Nginx's X-Accel-Redirect for high-performance file delivery.

## Overview

The implementation ensures that all media file access goes through Django for permission checking, while still maintaining high performance through Nginx's efficient file serving capabilities.

**Development Mode Support**: The implementation automatically detects whether you're running in development (with `uv run manage.py runserver`) or production (with Nginx) and serves files accordingly.

## Components

### 1. Django View (`files/secure_media_views.py`)

#### `SecureMediaView`
- **Purpose**: Handles all `/media/` requests with proper authentication and authorization
- **Key Features**:
  - Path validation to prevent directory traversal attacks
  - Media object identification from file paths
  - Permission checking based on media visibility levels
  - **Dual serving modes**: X-Accel-Redirect (production) or direct Django serving (development)

#### Visibility Level Handling

| State | Access Rules |
|-------|-------------|
| `public` | Anyone can access |
| `unlisted` | Any authenticated user can access |
| `restricted` | Any authenticated user can access (password handled elsewhere) |
| `private` | Only owner, managers, or admins can access |

#### Special Cases
- **Public Media Files**: Bypass Django permission checks for certain file types:
  - Thumbnails (`/thumbnails/` paths) - as specified in requirements
  - User logos/avatars (`userlogos/` paths)
  - Site assets (logos, favicons, social media icons)
- **Encoded Files**: Support for multiple encoding profiles with proper media association
- **HLS/Streaming**: Support for HLS manifests and video segments

### 2. Settings Configuration

#### Production Settings (`cms/settings.py`)
```python
# X-Accel-Redirect settings for secure media serving
# Set to True when using Nginx with X-Accel-Redirect (production)
# Set to False when using Django development server
USE_X_ACCEL_REDIRECT = True
```

#### Development Settings (`cms/dev_settings.py`)
```python
# X-Accel-Redirect settings for secure media serving
# Set to False in development since Django runserver doesn't support X-Accel-Redirect
USE_X_ACCEL_REDIRECT = False
```

### 3. URL Configuration (`files/urls.py`)

```python
# Added route to handle all /media/ requests
re_path(r"^media/(?P<file_path>.+)$", secure_media_views.secure_media_file, name="secure_media")
```

- Captures all `/media/` requests before they reach static file serving
- Removed direct static file serving for media files in production

### 4. Nginx Configuration (`deploy/mediacms.io`)

#### Internal Locations
```nginx
# Internal locations for X-Accel-Redirect - not accessible externally
location /internal/media/original/ {
    internal;
    alias /home/cinemata/cinematacms/media_files/original/;
    # Performance optimizations...
}

location /internal/media/ {
    internal;
    alias /home/cinemata/cinematacms/media_files/;
    # Performance optimizations...
}
```

#### Key Features
- `internal` directive prevents direct external access
- Optimized for file serving with `sendfile`, `tcp_nopush`, `tcp_nodelay`
- Appropriate caching headers for media content
- Security headers (`X-Content-Type-Options`)

## Serving Modes

### Production Mode (`USE_X_ACCEL_REDIRECT = True`)
1. **Client requests**: `/media/original/user/admin/video.mp4`
2. **Django checks**: Authentication + media permissions
3. **Django responds**: `X-Accel-Redirect: /internal/media/original/user/admin/video.mp4`
4. **Nginx serves**: File efficiently using internal location
5. **Client receives**: High-performance file stream with proper headers

### Development Mode (`USE_X_ACCEL_REDIRECT = False`)
1. **Client requests**: `/media/original/user/admin/video.mp4`
2. **Django checks**: Authentication + media permissions
3. **Django serves**: File directly using `FileResponse`
4. **Client receives**: File served through Django with appropriate headers

## File Path Patterns Supported

### Original Media Files
```
/media/original/user/{username}/{uid}.{extension}
```
Example: `/media/original/user/admin/a6cae054eb734265aff6f8c943dff897.IMG_0438.MOV`

### Encoded Media Files
```
/media/encoded/{profile_id}/{username}/{uid}.{extension}
```
Example: `/media/encoded/7/admin/a6cae054eb734265aff6f8c943dff897.mp4`

### Public Media Files (No Permission Check)
```
/media/original/thumbnails/user/{username}/{filename}  # Thumbnails
/media/userlogos/{filename}                            # User avatars
/media/logos/{filename}                                # Site logos
/media/favicons/{filename}                             # Favicons
/media/social-media-icons/{filename}                   # Social media icons
```
Examples:
- `/media/original/thumbnails/user/admin/a6cae054eb734265aff6f8c943dff897.jpg`
- `/media/userlogos/user.jpg`

### HLS and Other Streaming Files
```
/media/hls/{media_uid}/{file}
/media/{various_paths_containing_uid}
```

## Security Features

### Path Validation
- Prevents directory traversal attacks (`../` sequences)
- Validates file path format and structure
- Blocks access to paths starting with `/`

### Authentication Integration
- Uses Django's built-in authentication system
- Supports both session and token-based authentication
- Integrates with existing MediaCMS user roles (editor, manager, admin)

### Authorization Logic
- Media owner always has access to their content
- Managers and editors have access to all content
- Public content accessible to everyone
- Private content restricted to authorized users only

## Performance Optimizations

### Production (Nginx + X-Accel-Redirect)
- **sendfile**: Efficient file transfer without copying to userspace
- **tcp_nopush/tcp_nodelay**: Optimized TCP settings for media streaming
- **Caching**: Long-term caching with proper cache headers
- **Compression**: Gzip enabled for applicable content types

### Development (Direct Django Serving)
- **FileResponse**: Efficient file serving through Django
- **Minimal Processing**: Quick permission check, then serve file
- **Appropriate Headers**: Proper content-type and cache headers

### Django Level (Both Modes)
- **Database Optimization**: Efficient queries with proper indexing
- **Caching**: Per-request caching with appropriate cache headers

## Installation & Configuration

### 1. Update Django Settings
Ensure your `urls.py` includes the new secure media routes:

```python
from files import secure_media_views

urlpatterns = [
    re_path(r"^media/(?P<file_path>.+)$", secure_media_views.secure_media_file, name="secure_media"),
    # ... other patterns
]
```

### 2. Configure Settings
#### For Production (with Nginx):
```python
# In cms/settings.py or cms/local_settings.py
USE_X_ACCEL_REDIRECT = True
```

#### For Development (with runserver):
```python
# In cms/dev_settings.py or for local development
USE_X_ACCEL_REDIRECT = False
```

### 3. Update Nginx Configuration (Production Only)
Replace direct media serving with internal locations:

```nginx
# Remove these old configurations:
# location /media/original { ... }
# location /media { ... }

# Add new internal locations:
location /internal/media/original/ {
    internal;
    alias /path/to/media_files/original/;
    # ... performance settings
}

location /internal/media/ {
    internal;
    alias /path/to/media_files/;
    # ... performance settings
}
```

### 4. Restart Services
```bash
# For production
sudo systemctl restart your-django-service
sudo nginx -t && sudo systemctl reload nginx

# For development
uv run manage.py runserver
# Files will be served directly by Django
```

## Testing

### Test Public Content (Development)
```bash
curl -I http://localhost:8000/media/original/user/username/public-file.mp4
# Should return 200 OK with file served directly by Django
```

### Test Public Content (Production)
```bash
curl -I http://your-domain/media/original/user/username/public-file.mp4
# Should return 200 OK with X-Accel-Redirect header
```

### Test Private Content (Unauthorized)
```bash
curl -I http://your-domain/media/original/user/username/private-file.mp4
# Should return 403 Forbidden
```

### Test Private Content (Authorized)
```bash
curl -I -H "Authorization: Token your-token" http://your-domain/media/original/user/username/private-file.mp4
# Should return 200 OK (X-Accel-Redirect in production, direct serving in development)
```

### Test Public Media Files Access
```bash
# Test thumbnails
curl -I http://your-domain/media/original/thumbnails/user/username/thumb.jpg
# Should return 200 OK (no Django permission check)

# Test user logos
curl -I http://your-domain/media/userlogos/user.jpg
# Should return 200 OK (no Django permission check)
```

## Development Workflow

### Running with Django Development Server
```bash
# Use development settings (USE_X_ACCEL_REDIRECT = False)
uv run manage.py runserver --settings=cms.dev_settings

# Media files will be served directly by Django
# No Nginx configuration needed
# Full authentication/authorization still applies
```

### Running in Production
```bash
# Use production settings (USE_X_ACCEL_REDIRECT = True)
# Requires Nginx with internal location configuration
# Files served efficiently via X-Accel-Redirect
```

## Troubleshooting

### Common Issues

1. **404 Not Found for valid files**
   - Check that URL patterns are correctly configured
   - Verify file paths match expected patterns
   - Ensure media object exists in database

2. **403 Forbidden for public content**
   - Verify media state is set to 'public'
   - Check Django authentication middleware
   - Review permission checking logic

3. **Files not loading in development**
   - Ensure `USE_X_ACCEL_REDIRECT = False` in development settings
   - Check that `MEDIA_ROOT` is correctly configured
   - Verify file permissions are readable by Django process

4. **Direct file access still working in production**
   - Ensure old Nginx locations are removed
   - Verify internal locations are marked as `internal`
   - Check Nginx configuration reload

5. **Poor performance in development**
   - This is expected - Django direct serving is slower than Nginx
   - For performance testing, use production environment
   - Consider using a local Nginx setup for performance testing

### Logging

Enable detailed logging in Django settings:

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'secure_media.log',
        },
    },
    'loggers': {
        'files.secure_media_views': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

## Benefits

1. **Security**: All file access controlled by Django authentication/authorization
2. **Performance**: High-speed file serving via Nginx X-Accel-Redirect in production
3. **Development Friendly**: Works seamlessly with Django runserver
4. **Scalability**: Minimal Django processing for file requests in production
5. **Flexibility**: Easy to modify access rules without touching Nginx config
6. **Compatibility**: Works with existing MediaCMS authentication system

## Future Enhancements

- **Bandwidth Limiting**: Per-user or per-file bandwidth controls
- **Access Logging**: Detailed audit trails for file access
- **CDN Integration**: Support for CDN with secure token generation
- **Range Requests**: Optimized for video seeking and partial downloads