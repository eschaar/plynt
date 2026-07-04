# Installation and extras

Plynth uses optional extras to keep the core dependency surface minimal.
Install only what your integration needs.

## Extras

| Extra                | Installs                          | Use when                             |
| -------------------- | --------------------------------- | ------------------------------------ |
| `plynth[httpx]`      | `httpx2`                          | You need the built-in HTTP transport |
| `plynth[salesforce]` | `httpx2`, `PyJWT`, `cryptography` | Salesforce connector                 |
| `plynth[oauth]`      | OAuth2 helpers                    | Custom OAuth2 flows                  |

## Install examples

```bash
# Salesforce only
pip install "plynth[salesforce]"

# Multiple extras
pip install "plynth[salesforce,oauth]"

# Core only (bring your own transport)
pip install plynth
```

## Development install

```bash
pip install "plynth[dev]"
```

Includes test dependencies, type stubs, linting, and build tools.
