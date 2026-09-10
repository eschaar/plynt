# Vendored Salesforce Pub/Sub API proto

This directory holds vendored, upstream-sourced files. Nothing in here is
hand-written or hand-edited.

| File                     | Origin                                           | Regenerate by                        |
| ------------------------ | ------------------------------------------------ | ------------------------------------ |
| `pubsub_api.proto`       | Copied verbatim from upstream (see SOURCE below) | `make salesforce-cdc-proto-update`   |
| `pubsub_api_pb2.py`      | Generated from `pubsub_api.proto`                | `make salesforce-cdc-proto-generate` |
| `pubsub_api_pb2_grpc.py` | Generated from `pubsub_api.proto`                | `make salesforce-cdc-proto-generate` |

Do not hand-edit any file in this directory. If the proto needs to change,
update `SOURCE.md` with the new upstream commit and re-run the Makefile
targets above so the `.proto` and generated `.py` files stay in sync and
reviewable as a single diff.
