server {
    listen 80;
    server_name cinemata.local

    gzip on;
    access_log /var/log/nginx/mediacms.io.access.log;

    error_log  /var/log/nginx/mediacms.io.error.log  warn;

#    # redirect to https if logged in
#    if ($http_cookie ~* "sessionid") {
#        rewrite  ^/(.*)$  https://cinemata.local/$1  permanent;
#    }

#    # redirect basic forms to https
#    location ~ (login|login_form|register|mail_password_form)$ {
#        rewrite  ^/(.*)$  https://cinemata.local/$1  permanent;
#    }

    location /static {
        alias /home/cinemata/cinematacms/static ;
    }

    # Internal locations for X-Accel-Redirect - not accessible externally
    location /internal/media/original/ {
        internal;
        alias /home/cinemata/cinematacms/media_files/original/;

        # Enable efficient file serving
        sendfile on;
        tcp_nopush on;
        tcp_nodelay on;

        # Cache settings for media files
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff;
    }

    location /internal/media/ {
        internal;
        alias /home/cinemata/cinematacms/media_files/;

        # Enable efficient file serving
        sendfile on;
        tcp_nopush on;
        tcp_nodelay on;

        # Cache settings for media files
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff;
    }

    # All media requests now go through Django for authentication
    # Django will use X-Accel-Redirect to serve files efficiently

    location / {
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range';
        add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range';

        include /etc/nginx/uwsgi_params;
        uwsgi_pass 127.0.0.1:9000;
    }
}

# Upload subdomain for file uploads
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

server {
    listen 443 ssl;
    server_name cinemata.local;

    ssl_certificate_key  /etc/letsencrypt/live/cinemata.local/privkey.pem;
    ssl_certificate  /etc/letsencrypt/live/cinemata.local/fullchain.pem;
    ssl_dhparam /etc/nginx/dhparams/dhparams.pem;

    ssl_protocols TLSv1.2 TLSv1.3; # Dropping SSLv3, ref: POODLE
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_ecdh_curve secp521r1:secp384r1;
    ssl_prefer_server_ciphers on;

    gzip on;
    access_log /var/log/nginx/mediacms.io.access.log;

    error_log  /var/log/nginx/mediacms.io.error.log  warn;

    location /static {
        alias /home/cinemata/cinematacms/static ;
    }

    # Internal locations for X-Accel-Redirect - not accessible externally
    location /internal/media/original/ {
        internal;
        alias /home/cinemata/cinematacms/media_files/original/;

        # Enable efficient file serving
        sendfile on;
        tcp_nopush on;
        tcp_nodelay on;

        # Cache settings for media files
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff;
    }

    location /internal/media/ {
        internal;
        alias /home/cinemata/cinematacms/media_files/;

        # Enable efficient file serving
        sendfile on;
        tcp_nopush on;
        tcp_nodelay on;

        # Cache settings for media files
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff;
    }

    # All media requests now go through Django for authentication
    # Django will use X-Accel-Redirect to serve files efficiently

    location / {
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range';
        add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range';

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

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_ecdh_curve secp521r1:secp384r1;
    ssl_prefer_server_ciphers on;

     # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;

    gzip on;
    access_log /var/log/nginx/uploads.cinemata.local.access.log;
    error_log  /var/log/nginx/uploads.cinemata.local.error.log warn;

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

    # Health check endpoint for monitoring
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
