# Pulse

Pulse is a Python CLI for monitoring HTTP endpoints.

## Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Configuration

Create a `pulse.yaml` in the directory where you run the command. Start from
[`pulse.example.yaml`](pulse.example.yaml):

```yaml
checks:
  - name: example-site
    url: https://example.com
    expected_status: 200 # optional; defaults to 200
    timeout_seconds: 5 # optional; defaults to 5 seconds
```

Check names must be unique, URLs must use HTTP or HTTPS, and status codes must
be between 100 and 599.

## Usage

```bash
uv run pulse check
```

The command lists the configured endpoint checks. It reports a clear error and
exits non-zero when `pulse.yaml` is missing or invalid.
