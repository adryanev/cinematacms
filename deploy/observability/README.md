# Full observability reference stack

This installer deploys the CinemataCMS reference stack for metrics, logs,
traces, dashboards, and alerts on one Ubuntu host.

It installs VictoriaMetrics, VictoriaLogs, VictoriaTraces, the OpenTelemetry
Collector, node exporter, PostgreSQL, Redis, Nginx, and Celery exporters,
vmalert, and Alertmanager. Grafana must already be installed and configured
with anonymous access and public account registration disabled.

The installer uses only loopback listeners. Publish Grafana through an HTTPS
reverse proxy. Do not expose storage APIs, exporters, Alertmanager, or the
OTLP receiver to the public internet.

## Before you install

1. Install CinemataCMS and configure Grafana with the starter installer.
2. Switch the application from the starter collector to managed observability.
   This stops the local Prometheus and collector services so that they cannot
   duplicate metrics or compete for the OTLP receiver. Reuse the deployed
   domain and proxy settings when prompted, then restart the application.

   ```bash
   sudo ./deploy/apply-release-config.sh --observability managed
   sudo ./restart_script.sh --no-pull
   ```

3. Confirm that the server has enough free disk space for the configured data
   retention. Keep at least 20 percent free after installation.
4. Create a Grafana Viewer service-account token for the installer's read-back
   checks.
5. Create a root-readable environment file from the template. Set real values
   for the Grafana token, incident-reference token, PostgreSQL monitor password,
   and alert receiver before you continue.

```bash
sudo install -m 0600 deploy/observability/observability.env.example \
  /etc/cinematacms-observability.env
sudoedit /etc/cinematacms-observability.env
```

## Install

Run the installer from the CinemataCMS checkout:

```bash
sudo deploy/observability/install.sh \
  --env /etc/cinematacms-observability.env
```

The installer verifies downloaded archives with SHA-256, validates its
configuration, provisions Grafana data sources and dashboards, and performs
metric, log, trace, alert, and correlation read-back checks.

To verify an existing installation without changing it, run:

```bash
sudo deploy/observability/install.sh \
  --env /etc/cinematacms-observability.env \
  --verify-only
```

## What the installer provisions

- An application and host metrics dashboard.
- A dashboard with separate running-log views for each service.
- Trace and incident-search dashboards with log-to-trace links.
- Alert rules for application, queue, scheduled-job, dependency, storage, and
  telemetry failures.
- Log processing that allowlists useful attributes, redacts common secrets and
  email addresses, and limits log messages to 2 KiB.

VictoriaTraces is a preview product. Evaluate its current support status before
using it as the production trace store. The application remains backend-neutral
and can export OTLP traces to another compatible backend.

## Security and recovery

Keep the supplied environment file at mode `0600`. Do not commit it. Keep
Grafana accounts limited to authorized operators.

Before a production rollout, back up the application configuration, Nginx
configuration, systemd units, Grafana provisioning files, and database. If the
installation fails, stop the new observability services, restore those files,
restart the earlier telemetry path, and retain the new data directories until
you complete the failure review.
