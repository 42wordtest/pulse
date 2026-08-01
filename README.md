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

## Development checks

Run the test suite, linting, and type checking:

```bash
make pytest
make lint
make check
```
