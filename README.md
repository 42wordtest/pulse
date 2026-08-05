# Pulse

Pulse is a Python command-line tool for monitoring HTTP endpoints. It loads
endpoint checks from a YAML file, sends a GET request to each endpoint, reports
health and response latency, and stores every result in a local SQLite database.

## What it checks

For each configured endpoint, Pulse:

- sends an HTTP GET request;
- measures request latency;
- marks the endpoint healthy when its response matches the expected HTTP status;
- reports unexpected statuses, timeouts, and connection errors; and
- saves the result to `.pulse/pulse.db` for later analysis.

## Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/)

## Setup

Install the project and its dependencies:

```bash
uv sync
```

## Configure endpoint checks

Create a local `pulse.yaml` in the directory where you will run Pulse. The file
is git-ignored so it can contain environment-specific endpoints.

```yaml
checks:
  - name: example-site
    url: https://example.com
    expected_status: 200 # optional; defaults to 200
    timeout_seconds: 5 # optional; defaults to 5 seconds
```

You can copy the tracked example and edit its URLs:

```bash
cp pulse.example.yaml pulse.yaml
```

Each check needs a unique `name` and an HTTP or HTTPS `url`. The optional
`expected_status` must be between 100 and 599, and `timeout_seconds` must be
greater than zero.

## Run checks

Run all checks in `pulse.yaml`:

```bash
make pulse
```

Example output:

```text
HEALTHY example-site (123 ms) — Healthy: received expected HTTP 200.
```

Results are stored locally in `.pulse/pulse.db`. The database is created
automatically and is git-ignored.

## View availability

Availability is the percentage of recorded checks that were healthy within a
time window. By default, Pulse reports the last 24 hours:

```bash
make availability
```

Set `HOURS` to use a different window:

```bash
make availability HOURS=168
```

Example output:

```text
example-site: 99.2% (119/120 healthy)
```

No recorded checks are treated as unknown. Pulse prints a no-results message
rather than reporting 100% availability.

## Detect reliability regressions

Compare recent availability with an earlier baseline:

```bash
make regression
```

The default comparison is the last hour against the preceding seven days. Both
windows can be changed:

```bash
make regression RECENT_HOURS=2 BASELINE_HOURS=168
```

The baseline ends when the recent window begins, so the periods do not overlap.
For example, a two-hour recent window and 168-hour baseline compare:

```text
baseline: the 168 hours before the recent window
recent:   the last 2 hours
```

Pulse currently requires at least 10 recorded checks in both windows. It prints
`insufficient data` until enough history exists. A regression is reported when
recent availability drops by at least two percentage points from the baseline.

For meaningful availability and regression data, run `make pulse` at a regular
cadence, such as every five minutes with cron or another scheduler.

## Configure alerts and notifications

Alert rules evaluate stored availability and notify only when an alert opens or
recovers. This avoids sending the same alert every time a scheduler runs.

```yaml
alerts:
  - name: example-site-availability
    endpoint: example-site
    type: availability_below
    window_hours: 1
    min_samples: 10
    threshold_percent: 99.0
    notifications:
      - type: console
      - type: webhook
        url_env: PULSE_ALERT_WEBHOOK_URL
```

`endpoint` must reference a configured check. The first alert type is
`availability_below`: it opens when availability falls below
`threshold_percent` in the configured window.

Console notifications are printed by the command. Webhook URLs are read from
the named environment variable so secrets are not stored in `pulse.yaml`:

```bash
export PULSE_ALERT_WEBHOOK_URL="https://alerts.example.com/notify"
```

Evaluate alert rules and deliver any opening or recovery notifications:

```bash
make alerts
```

The command exits with status 1 while one or more alerts are active, which
makes it suitable for scheduled automation. A failed webhook delivery is shown
clearly and is retried on the next run.

## Development checks

Run the test suite, linting, and type checking:

```bash
make test
make check
make quality
```
