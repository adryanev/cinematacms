# Deploy the full observability stack

Use this runbook for a production deployment of the reference stack.

## Check the host

1. Record the deployed revision and the available capacity.

   ```bash
   git rev-parse HEAD
   df -h /
   free -h
   sudo du -sh /var/lib /var/log /home/cinemata
   ```

2. Keep at least 20 percent of the filesystem free after data storage is
   provisioned. Reduce retention or increase the volume if the host cannot
   keep that margin.

3. Confirm that the application, database, cache, workers, and Nginx are
   healthy before you start.

   ```bash
   sudo systemctl is-active \
     mediacms celery_long celery_short celery_whisper celery_beat celery_email nginx
   ```

4. Back up the application configuration, Nginx configuration, systemd units,
   Grafana provisioning files, and database outside the directories that the
   installer manages.

## Prepare access

1. Switch the application from starter observability to managed observability.
   Reuse the current deployment's domain and proxy settings if the script asks
   for them. This disables the starter Prometheus and collector so the full
   stack is the only metrics and OTLP path.

   ```bash
   sudo ./deploy/apply-release-config.sh --observability managed
   sudo ./restart_script.sh --no-pull
   ```

2. Disable Grafana anonymous access and self-registration.
3. Create a Grafana Viewer service account and token.
4. Copy the environment template to a root-readable location.

   ```bash
   sudo install -m 0600 deploy/observability/observability.env.example \
     /etc/cinematacms-observability.env
   sudoedit /etc/cinematacms-observability.env
   ```

5. Set the public health URL, retention periods, database credentials, Grafana
   token, incident-reference token, and alert receiver values. Do not commit
   this file.

## Install and verify

1. Run the installer.

   ```bash
   sudo deploy/observability/install.sh \
     --env /etc/cinematacms-observability.env
   ```

2. Confirm that all services are active.

   ```bash
   sudo systemctl is-active \
     victoriametrics victorialogs victoriatraces cinematacms-otelcol \
     postgres-exporter redis-exporter nginx-prometheus-exporter \
     celery-exporter alertmanager vmalert grafana-server \
     prometheus-node-exporter
   ```

3. Run the read-only verification.

   ```bash
   sudo deploy/observability/install.sh \
     --env /etc/cinematacms-observability.env \
     --verify-only
   ```

4. Open every provisioned Grafana dashboard through an authenticated session.
   Generate a request, find its log entry, open its trace, and test one alert
   route before you rely on the stack during an incident.

## Roll back

1. Stop the new observability services. Do not delete their data directories.
2. Restore the backed-up configuration and units.
3. Restart the previous application and telemetry path.
4. Confirm the public health endpoint, application services, disk usage, and
   earlier dashboards.
5. Keep deployment logs and the new data directories for the incident review.
