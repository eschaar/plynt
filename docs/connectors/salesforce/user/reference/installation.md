# Salesforce installation

Install the connector with:

```bash
pip install "plynt[salesforce]"
```

The extra includes HTTP transport, typed models, signing, and Avro decoding. Its
runtime floors include `pydantic>=2.14.1`, `cryptography>=50.0.2`,
`PyJWT>=2.15.1,<3`, and `fastavro>=1.13.1,<2`.

## Experimental CDC

```bash
pip install "plynt[grpc,salesforce]"
```

The vendored Pub/Sub messages require `grpcio>=1.85.0,<2` and
`protobuf>=7.35.1,<8`. Resolve those versions together and run
`python -m pip check` after upgrading. Code generation does not run during
installation or import.

These minima are tested independently of the development generator under
[ADR-0031](../../../../architecture/adr/0031-experimental-release-installation-contract.md).
The development generator is pinned to `grpcio-tools==1.85.0`; its routine
refresh gates are documented in
[ADR-0044](../../../../architecture/adr/0044-grpc-toolchain-upgrade-policy.md).

CDC is async-only and still requires validation against a real organization,
including authentication, schema handling, replay cursor fidelity, and
long-running operation. Passing installed-wheel tests is not a production
readiness claim.

See [Deploy CDC](../how-to/deploy-cdc.md) for operational requirements and
[generic installation](../../../../user/reference/installation.md) for Python
support and development commands.
