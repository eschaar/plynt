# Services reference

`SalesforceAPIFacade` (and its async sibling `AsyncSalesforceAPIFacade`)
are the main entry points. Each method returns a dedicated service object
that wraps a group of related Salesforce REST API endpoints.

## Accessing services

```python
from plynt.connectors.salesforce.client import SalesforceAPIClient
from plynt.connectors.salesforce.facade import SalesforceAPIFacade

client = SalesforceAPIClient(auth=auth, transport=transport)
sf = SalesforceAPIFacade(client)

# Then call a service method:
result = sf.query().query("SELECT Id FROM Account LIMIT 1")
```

All service methods accept optional `api_version` and `renderer` keyword
arguments that override the connector defaults.

## Service methods

| Method                  | Returns                           | Description                            |
| ----------------------- | --------------------------------- | -------------------------------------- |
| `sf.sobject(name)`      | `SalesforceObjectService`         | CRUD + describe for a named SObject    |
| `sf.query()`            | `SalesforceQueryService`          | SOQL query, query_all, pagination      |
| `sf.object_query(name)` | `SalesforceObjectQueryService`    | Object-scoped SOQL with helper methods |
| `sf.search()`           | `SalesforceSearchService`         | SOSL full-text search                  |
| `sf.bulk()`             | `SalesforceBulkService`           | Bulk API 2.0 ingest and query jobs     |
| `sf.composite()`        | `SalesforceCompositeService`      | Composite and batch requests           |
| `sf.apex_rest()`        | `SalesforceApexRestService`       | Custom Apex REST endpoints             |
| `sf.metadata()`         | `SalesforceMetadataService`       | Metadata API deploy/retrieve           |
| `sf.identity_access()`  | `SalesforceIdentityAccessService` | Identity and access primitives         |
| `sf.models()`           | `SalesforceModelsService`         | Salesforce Models (Einstein) API       |
| `sf.agent()`            | `SalesforceAgentService`          | Salesforce Agentforce API              |
| `sf.utility()`          | `SalesforceUtilityService`        | Org limits, API version discovery      |
| `sf.lookup(kind)`       | `SyncLookupService`               | Named record lookup strategies         |

## Service method reference

### `SalesforceObjectService` (`sf.sobject(name)`)

| Method               | Parameters                                   | Returns                       | Description                                              |
| -------------------- | -------------------------------------------- | ----------------------------- | -------------------------------------------------------- |
| `get`                | `record_id, fields=None`                     | `dict`                        | Fetch a record by Salesforce ID; optionally limit fields |
| `get_by_external_id` | `external_id_field, external_id_value`       | `dict`                        | Fetch a record by custom external ID field               |
| `create`             | `data`                                       | `SObjectCreateResult`         | Create a new record; returns `id` and `success`          |
| `update`             | `record_id, data`                            | `None`                        | PATCH — update specified fields only                     |
| `upsert`             | `external_id_field, external_id_value, data` | `SObjectCreateResult \| None` | Insert or update by external ID; `None` on update        |
| `delete`             | `record_id`                                  | `None`                        | Delete a record                                          |
| `describe`           | `()`                                         | `dict`                        | Full SObject metadata — fields, picklists, relationships |
| `metadata`           | `()`                                         | `dict`                        | Basic metadata and URLs for this SObject type            |
| `describe_layout`    | `record_id`                                  | `dict`                        | Record layout description for a specific layout ID       |
| `deleted`            | `start: datetime, end: datetime`             | `dict`                        | IDs soft-deleted in the given time window                |
| `updated`            | `start: datetime, end: datetime`             | `dict`                        | IDs updated in the given time window                     |

See [Create, update, and delete SObject records](../how-to/sobject-crud.md).

______________________________________________________________________

### `SalesforceQueryService` (`sf.query()`)

| Method               | Parameters                                  | Returns                             | Description                       |
| -------------------- | ------------------------------------------- | ----------------------------------- | --------------------------------- |
| `query`              | `soql, *, include_deleted=False`            | `SalesforceQueryResponse`           | Execute SOQL; returns first page  |
| `query_more`         | `next_records_url`                          | `SalesforceQueryResponse`           | Follow a pagination cursor URL    |
| `query_more_from_id` | `next_records_id, *, include_deleted=False` | `SalesforceQueryResponse`           | Follow a pagination cursor ID     |
| `query_all_iter`     | `soql, *, include_deleted=False`            | `Iterator[SalesforceQueryResponse]` | Lazy iterator over all pages      |
| `query_all`          | `soql, *, include_deleted=False`            | `list[dict]`                        | Materialise all pages into a list |

______________________________________________________________________

### `SalesforceObjectQueryService` (`sf.object_query(name)`)

Object-scoped SOQL with keyword-argument query composition. Builds
`SELECT` statements for one SObject type without writing raw SOQL.

| Method                | Key parameters                                            | Returns                             | Description                          |
| --------------------- | --------------------------------------------------------- | ----------------------------------- | ------------------------------------ |
| `query`               | `fields, where, order_by, limit, offset, include_deleted` | `SalesforceQueryResponse`           | Build and execute a SOQL SELECT      |
| `query_more`          | `next_records_url`                                        | `SalesforceQueryResponse`           | Follow pagination cursor             |
| `query_more_from_id`  | `next_records_id, include_deleted`                        | `SalesforceQueryResponse`           | Follow pagination cursor ID          |
| `query_updated_since` | `since: datetime, fields, timestamp_field, where, …`      | `SalesforceQueryResponse`           | Query records modified after `since` |
| `query_all_iter`      | `fields, where, order_by, limit, offset, include_deleted` | `Iterator[SalesforceQueryResponse]` | Lazy iterator over all pages         |
| `query_all`           | `fields, where, order_by, limit, offset, include_deleted` | `list[dict]`                        | Materialise all pages into a list    |

See [Query records with SOQL](../how-to/query-records.md).

______________________________________________________________________

### `SalesforceSearchService` (`sf.search()`)

| Method         | Parameters         | Returns                    | Description                              |
| -------------- | ------------------ | -------------------------- | ---------------------------------------- |
| `search`       | `sosl: str`        | `SalesforceSearchResponse` | Execute a full SOSL search string        |
| `quick_search` | `search_text: str` | `SalesforceSearchResponse` | Wrap term in `FIND {term} IN ALL FIELDS` |

See [Search with SOSL](../how-to/search.md).

______________________________________________________________________

### `SalesforceBulkService` (`sf.bulk()`)

High-level methods handle the full job lifecycle. Low-level primitives give
fine-grained control.

**High-level:**

| Method   | Parameters                                                              | Returns            | Description                                |
| -------- | ----------------------------------------------------------------------- | ------------------ | ------------------------------------------ |
| `ingest` | `sobject, operation, records, *, external_id_field=None, max_wait=None` | `BulkIngestResult` | Create job, upload, wait, return results   |
| `query`  | `soql, *, include_deleted=False, max_wait=None`                         | `list[dict]`       | Create query job, wait, return all records |

**Low-level:**

| Method               | Parameters                                      | Returns            | Description                              |
| -------------------- | ----------------------------------------------- | ------------------ | ---------------------------------------- |
| `create_ingest_job`  | `sobject, operation, *, external_id_field=None` | `BulkJobInfo`      | Create a new ingest job                  |
| `create_query_job`   | `soql, *, include_deleted=False`                | `BulkJobInfo`      | Create a new query job                   |
| `upload_records`     | `job_id, records, *, content_url=None`          | `None`             | Upload a batch of records to an open job |
| `close_job`          | `job_id`                                        | `BulkJobInfo`      | Close job and signal upload complete     |
| `abort_job`          | `job_id, *, is_query`                           | `BulkJobInfo`      | Abort a running job                      |
| `delete_job`         | `job_id, *, is_query`                           | `None`             | Delete a job                             |
| `wait_for_job`       | `job_id, *, is_query, max_wait=None`            | `BulkJobInfo`      | Poll until terminal state                |
| `get_ingest_results` | `job_id`                                        | `BulkIngestResult` | Fetch successful/failed/unprocessed rows |
| `get_query_results`  | `job_id`                                        | `list[dict]`       | Fetch query job results                  |
| `get_job`            | `job_id, *, is_query`                           | `BulkJobInfo`      | Fetch current job status                 |

`BulkOperation` values: `insert`, `update`, `upsert`, `delete`,
`hard_delete`, `query`, `query_all`.

See [Run Bulk API operations](../how-to/bulk.md).

______________________________________________________________________

### `SalesforceCompositeService` (`sf.composite()`)

| Method      | Parameters                                                  | Returns                  | Description                                     |
| ----------- | ----------------------------------------------------------- | ------------------------ | ----------------------------------------------- |
| `composite` | `requests, *, all_or_none=False, collate_subrequests=False` | `CompositeResponse`      | Up to 25 dependent sub-requests in one call     |
| `batch`     | `requests, *, halt_on_error=False`                          | `CompositeBatchResponse` | Up to 25 independent sub-requests in one call   |
| `tree`      | `object_name, records, *, all_or_none=False`                | `CompositeTreeResponse`  | Bulk insert up to 200 records with parent-child |

See [Use composite and batch requests](../how-to/use-composite.md).

______________________________________________________________________

### `SalesforceAgentService` (`sf.agent()`)

| Method                   | Parameters                                             | Returns                | Description                         |
| ------------------------ | ------------------------------------------------------ | ---------------------- | ----------------------------------- |
| `start_session`          | `agent_id, *, context=None`                            | `AgentSession`         | Begin a new agent conversation      |
| `send_message`           | `session_id, text, *, metadata=None`                   | `AgentMessageResponse` | Send a message and receive a reply  |
| `send_message_streaming` | `session_id, text, *, metadata=None`                   | `StreamingResponse`    | Send a message with streaming reply |
| `end_session`            | `session_id`                                           | `AgentSessionEndAck`   | Terminate the session               |
| `submit_feedback`        | `session_id, rating, *, message_id=None, comment=None` | `FeedbackAck`          | Rate an agent response              |

See [Use the Agentforce API](../how-to/use-agent-api.md).

______________________________________________________________________

### `SalesforceModelsService` (`sf.models()`)

| Method                | Parameters                                                                                | Returns                                       | Description                                               |
| --------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------- | --------------------------------------------------------- |
| `generate_chat`       | `messages, *, model=None, temperature=None, max_tokens=None, stream=False, metadata=None` | `ChatCompletionResponse \| StreamingResponse` | Chat completion; `stream=True` returns streaming response |
| `generate_text`       | `prompt, *, model=None, temperature=None, max_tokens=None`                                | `TextGenerationResponse`                      | Single-turn text completion                               |
| `generate_embeddings` | `input_text, *, model=None`                                                               | `EmbeddingResponse`                           | Vector embeddings for one or more inputs                  |
| `submit_feedback`     | `request_id, rating, *, comment=None`                                                     | `FeedbackAck`                                 | Rate a model response                                     |

See [Use the Salesforce Models API](../how-to/use-models-api.md).

______________________________________________________________________

### `SalesforceApexRestService` (`sf.apex_rest()`)

| Method    | Parameters                                                      | Returns | Description                        |
| --------- | --------------------------------------------------------------- | ------- | ---------------------------------- |
| `execute` | `action, *, method="GET", data=None, params=None, headers=None` | `Any`   | Call any custom Apex REST endpoint |

```python
result = sf.apex_rest().execute(
    "MyApexClass/action",
    method="POST",
    data={"key": "value"},
)
```

______________________________________________________________________

### `SalesforceIdentityAccessService` (`sf.identity_access()`)

| Method                                  | Parameters                                                                               | Returns               | Description                                |
| --------------------------------------- | ---------------------------------------------------------------------------------------- | --------------------- | ------------------------------------------ |
| `get_user`                              | `user_id, *, fields=None`                                                                | `dict`                | Fetch a single user record                 |
| `list_users`                            | `*, username=None, email=None, is_active=None, profile_id=None, fields=None, limit=None` | `list[dict]`          | Search for users by filter criteria        |
| `list_permission_set_assignments`       | `user_id, *, permission_set_id=None, fields=None`                                        | `list[dict]`          | List permission set assignments for a user |
| `assign_permission_set`                 | `user_id, permission_set_id`                                                             | `SObjectCreateResult` | Assign a permission set                    |
| `revoke_permission_set`                 | `assignment_id`                                                                          | `None`                | Remove a permission set assignment         |
| `list_permission_set_group_assignments` | `user_id, *, permission_set_group_id=None, fields=None`                                  | `list[dict]`          | List permission set group assignments      |
| `assign_permission_set_group`           | `user_id, permission_set_group_id`                                                       | `SObjectCreateResult` | Assign a permission set group              |
| `revoke_permission_set_group`           | `assignment_id`                                                                          | `None`                | Remove a permission set group assignment   |
| `set_user_active`                       | `user_id, is_active: bool`                                                               | `None`                | Activate or deactivate a user              |

______________________________________________________________________

### `SalesforceUtilityService` (`sf.utility()`)

| Method       | Returns                    | Description                            |
| ------------ | -------------------------- | -------------------------------------- |
| `limits()`   | `SalesforceLimitsResponse` | Org API limits and current consumption |
| `versions()` | `list[dict]`               | All API versions available on this org |

______________________________________________________________________

### `SalesforceLookupService` (`sf.lookup(kind)`)

Pre-built lookup services for common internal object types. Create via the
factory:

```python
from plynt.connectors.salesforce.lookup.types import LookupType

user_svc = sf.lookup(LookupType.USER)
```

| `LookupType`  | Service class                       | Description                              |
| ------------- | ----------------------------------- | ---------------------------------------- |
| `USER`        | `SalesforceUserLookupService`       | Look up users by username or email       |
| `PROFILE`     | `SalesforceProfileLookupService`    | Look up profiles by name                 |
| `QUEUE`       | `SalesforceQueueLookupService`      | Look up queues by name or developer name |
| `PRICEBOOK`   | `SalesforcePricebookLookupService`  | Look up price books by name              |
| `RECORD_TYPE` | `SalesforceRecordTypeLookupService` | Look up record types for a given SObject |

______________________________________________________________________

## Async variants

Every sync service has an `Async` counterpart. Swap `SalesforceAPIFacade`
for `AsyncSalesforceAPIFacade` and `await` every method call:

| Sync                              | Async                                  |
| --------------------------------- | -------------------------------------- |
| `SalesforceAPIFacade`             | `AsyncSalesforceAPIFacade`             |
| `SalesforceObjectService`         | `AsyncSalesforceObjectService`         |
| `SalesforceQueryService`          | `AsyncSalesforceQueryService`          |
| `SalesforceObjectQueryService`    | `AsyncSalesforceObjectQueryService`    |
| `SalesforceSearchService`         | `AsyncSalesforceSearchService`         |
| `SalesforceBulkService`           | `AsyncSalesforceBulkService`           |
| `SalesforceCompositeService`      | `AsyncSalesforceCompositeService`      |
| `SalesforceAgentService`          | `AsyncSalesforceAgentService`          |
| `SalesforceModelsService`         | `AsyncSalesforceModelsService`         |
| `SalesforceApexRestService`       | `AsyncSalesforceApexRestService`       |
| `SalesforceIdentityAccessService` | `AsyncSalesforceIdentityAccessService` |
| `SalesforceUtilityService`        | `AsyncSalesforceUtilityService`        |

Use `AsyncSalesforceAPIFacade` with `AsyncSalesforceAPIClient` and
`HttpxAsyncTransport`.
