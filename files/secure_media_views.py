import os
import re
import mimetypes
import logging
from urllib.parse import unquote
from wsgiref.util import FileWrapper

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseForbidden, StreamingHttpResponse, FileResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.views import View

from .models import Media, Encoding
from .methods import is_mediacms_editor, is_mediacms_manager

logger = logging.getLogger(__name__)


class SecureMediaView(View):
    """
    Secure media file serving using X-Accel-Redirect.

    Handles authentication and authorization for different media visibility levels:
    - public: Anyone can access
    - unlisted: Any authenticated user can access
    - restricted: Authenticated users with valid password (or owner/editor/manager)
    - private: Only owner, managers, or admins can access
    """

    @method_decorator(cache_control(max_age=3600, private=True))
    def get(self, request, file_path):
        # Decode URL-encoded file path
        file_path = unquote(file_path)

        # Debug logging
        logger.debug(f"Secure media request for: {file_path}")

        # Security: Prevent path traversal attacks
        if '..' in file_path or file_path.startswith('/'):
            logger.warning(f"Path traversal attempt: {file_path}")
            raise Http404("Invalid file path")

        # Skip permission checks for certain file types that don't require media authentication
        if self._is_public_media_file(file_path):
            logger.debug(f"Serving public media file: {file_path}")
            return self._serve_file_direct(file_path)

        # Determine media object and check permissions
        media = self._get_media_from_path(file_path)
        if not media:
            logger.warning(f"Media not found for path: {file_path}")
            raise Http404("Media not found")

        logger.debug(f"Found media: {media.friendly_token} (state: {media.state})")

        # Check access permissions
        if not self._check_access_permission(request, media):
            logger.warning(f"Access denied for media: {media.friendly_token} (user: {request.user})")
            return HttpResponseForbidden("Access denied")

        # Serve file using X-Accel-Redirect or direct serving based on settings
        return self._serve_file(file_path)

    def _get_media_from_path(self, file_path):
        """
        Extract media object from file path.

        Handles multiple file path patterns:
        - original/user/{username}/{uid}.{filename}
        - encoded/{profile_id}/{username}/{uid}.{filename}
        - HLS and other paths containing UIDs
        """
        media = None

        # Pattern for original media files: original/user/{username}/{uid}.{filename}
        original_pattern = r'original/user/([^/]+)/([a-f0-9]{32})\.(.+)$'
        match = re.search(original_pattern, file_path)
        if match:
            username, uid_str, filename = match.groups()
            logger.debug(f"Original file pattern matched: username={username}, uid={uid_str}")
            media = Media.objects.filter(
                uid=uid_str,
                user__username=username
            ).first()
            if media:
                logger.debug(f"Found media from original pattern: {media.friendly_token}")
                return media

        # Pattern for encoded files: encoded/{profile_id}/{username}/{uid}.{filename}
        if not media:
            encoded_pattern = r'encoded/(\d+)/([^/]+)/([a-f0-9]{32})\.(.+)$'
            match = re.search(encoded_pattern, file_path)
            if match:
                profile_id, username, uid_str, filename = match.groups()
                logger.debug(f"Encoded file pattern matched: profile_id={profile_id}, username={username}, uid={uid_str}")
                encoding = Encoding.objects.filter(
                    media__uid=uid_str,
                    media__user__username=username,
                    profile_id=profile_id
                ).select_related('media').first()
                if encoding:
                    media = encoding.media
                    logger.debug(f"Found media from encoded pattern: {media.friendly_token}")
                    return media

        # Pattern for other files like HLS, sprites, etc. - try to extract uid
        if not media:
            uid_pattern = r'([a-f0-9]{32})'
            match = re.search(uid_pattern, file_path)
            if match:
                uid_str = match.group(1)
                logger.debug(f"Generic UID pattern matched: uid={uid_str}")
                media = Media.objects.filter(uid=uid_str).first()
                if media:
                    logger.debug(f"Found media from generic pattern: {media.friendly_token}")

        if not media:
            logger.debug(f"No media found for path: {file_path}")

        return media

    def _is_public_media_file(self, file_path):
        """
        Check if this is a file type that should be served without media authentication.

        These include:
        - Thumbnails (as specified in requirements)
        - User logos/avatars
        - Other static media assets that aren't actual media content
        """
        public_paths = [
            '/thumbnails/',     # Media thumbnails
            'userlogos/',       # User profile images/avatars
            'logos/',           # Site logos
            'favicons/',        # Site favicons
            'social-media-icons/',  # Social media icons
        ]

        return any(path in file_path for path in public_paths)

    def _check_access_permission(self, request, media):
        """
        Check if user has permission to access the media based on its state.
        """
        user = request.user

        # Public media - anyone can access
        if media.state == 'public':
            return True

        # Private media - only owner, managers, or admins
        if media.state == 'private':
            if user.is_authenticated and (
                user == media.user or
                is_mediacms_editor(user) or
                is_mediacms_manager(user)
            ):
                return True
            return False

        # Unlisted media - any authenticated user
        if media.state == 'unlisted':
            return user.is_authenticated

                # Restricted media - requires authentication AND password verification
        if media.state == 'restricted':
            if not user.is_authenticated:
                logger.debug(f"Restricted media access denied: user not authenticated")
                return False

            # Owner, editors, and managers can access without password
            if (user == media.user or
                is_mediacms_editor(user) or
                is_mediacms_manager(user)):
                logger.debug(f"Restricted media access granted: user has elevated permissions")
                return True

            # For other authenticated users, check password from session or query param
            # Check for password in session (set by view_media template)
            session_password = request.session.get(f'media_password_{media.friendly_token}')
            if session_password and session_password == media.password:
                logger.debug(f"Restricted media access granted: valid session password")
                return True

            # Check for password in query parameter (for API access)
            query_password = request.GET.get('password')
            if query_password and query_password == media.password:
                logger.debug(f"Restricted media access granted: valid query password")
                return True

            # No valid password provided
            logger.debug(f"Restricted media access denied: no valid password provided")
            return False

        return False

    def _serve_file(self, file_path):
        """
        Serve file using either X-Accel-Redirect or direct serving based on settings.
        """
        if getattr(settings, 'USE_X_ACCEL_REDIRECT', True):
            return self._serve_file_via_xaccel(file_path)
        else:
            return self._serve_file_direct_django(file_path)

    def _serve_file_via_xaccel(self, file_path):
        """
        Serve file using X-Accel-Redirect for high-performance delivery.
        """
        # Determine internal nginx location based on file path
        if file_path.startswith('original/'):
            internal_path = f'/internal/media/original/{file_path[9:]}'  # Remove 'original/' prefix
        else:
            internal_path = f'/internal/media/{file_path}'

        # Create response with X-Accel-Redirect header
        response = HttpResponse()
        response['X-Accel-Redirect'] = internal_path
        response['X-Accel-Buffering'] = 'yes'

        # Set appropriate content type if possible
        file_ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.pdf': 'application/pdf',
            '.vtt': 'text/vtt',
            '.m3u8': 'application/x-mpegURL',
            '.ts': 'video/MP2T'
        }

        if file_ext in content_types:
            response['Content-Type'] = content_types[file_ext]

        return response

    def _serve_file_direct_django(self, file_path):
        """
        Serve file directly through Django (for development without Nginx).
        """
        # Build full file path
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        logger.debug(f"Attempting to serve file directly: {full_path}")

        # Check if file exists
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            logger.warning(f"File not found: {full_path}")
            raise Http404("File not found")

        # Get content type
        content_type, _ = mimetypes.guess_type(full_path)
        if content_type is None:
            content_type = 'application/octet-stream'

        logger.debug(f"Serving file with content-type: {content_type}")

        # Open and serve file
        try:
            response = FileResponse(
                open(full_path, 'rb'),
                content_type=content_type,
                as_attachment=False
            )

            # Set cache headers
            response['Cache-Control'] = 'private, max-age=3600'
            response['X-Content-Type-Options'] = 'nosniff'

            # Add CORS headers for video files
            if content_type.startswith('video/'):
                response['Access-Control-Allow-Origin'] = '*'
                response['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Range'

            return response
        except IOError as e:
            logger.error(f"Error reading file {full_path}: {e}")
            raise Http404("File could not be read")

    def _serve_file_direct(self, file_path):
        """
        Serve file directly for thumbnails (bypassing Django permission checks).
        """
        return self._serve_file(file_path)


@require_GET
def secure_media_file(request, file_path):
    """
    Function-based view wrapper for SecureMediaView.
    """
    view = SecureMediaView()
    return view.get(request, file_path)