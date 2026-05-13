# Plynth

Plynth is a modular, framework-agnostic Python library for building external
API clients and services.

Plynth focuses on a stable integration foundation:

- framework-agnostic design
- sync and async support from one codebase
- explicit configuration and minimal hidden behavior
- typed settings and reusable middleware patterns

## Installation

```bash
pip install plynth
```

Optional extras:

```bash
pip install "plynth[httpx]"
pip install "plynth[salesforce]"
```

## Project Status

Current public release line:

- `0.1.0`: clean core foundation
- `0.2.0`: Salesforce connector baseline

## Documentation

- [README](https://github.com/eschaar/plynth/blob/main/README.md)
- [Changelog](https://github.com/eschaar/plynth/blob/main/CHANGELOG.md)
- [Architecture ADRs](https://github.com/eschaar/plynth/tree/main/docs/architecture/adr)
- [Salesforce connector docs](https://github.com/eschaar/plynth/tree/main/docs/connectors/salesforce)

## License

MIT
