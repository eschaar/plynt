# Vendored Salesforce Pub/Sub API proto

This directory holds an upstream-sourced schema and generated Python files.
Do not hand-edit the `.proto` or generated `.py` files. `README.md` and
`SOURCE.md` document the tooling and provenance and are maintained separately.

| File                     | Update method                       |
| ------------------------ | ----------------------------------- |
| `pubsub_api.proto`       | Copy a reviewed upstream source     |
| `pubsub_api_pb2.py`      | `make salesforce-cdc-proto-generate` |
| `pubsub_api_pb2_grpc.py` | `make salesforce-cdc-proto-generate` |

The schema is copied verbatim from upstream; see `SOURCE.md`. Both Python
files are generated from that schema.

Install the development extra to use the pinned `grpcio-tools==1.83.1`
generator. Consumers of the installed package do not need that tool.
Run `make salesforce-cdc-proto-verify` to compare regeneration in a temporary
directory with committed output without modifying it.

If the proto needs to change, retrieve it from a reviewed upstream commit,
verify the checksum, update `SOURCE.md`, and run the generation and
verification targets. Review the source and both generated files together.
There is no automated upstream-update target.
