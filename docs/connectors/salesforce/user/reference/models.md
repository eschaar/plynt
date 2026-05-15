# Models reference

Key response model classes returned by Salesforce services.

## Query models

### `SalesforceQueryResponse`

Returned by `SalesforceQueryService.query()` and `query_all()`.

| Attribute          | Type                   | Description                                                |
| ------------------ | ---------------------- | ---------------------------------------------------------- |
| `records`          | `list[dict[str, Any]]` | Record data from the current page                          |
| `total_size`       | `int`                  | Total number of matching records                           |
| `done`             | `bool`                 | `True` when all pages have been retrieved                  |
| `next_records_url` | `str \| None`          | Cursor URL for the next page; `None` when `done` is `True` |

### `SalesforceSearchResponse`

Returned by `SalesforceSearchService.search()`.

| Attribute        | Type                   | Description                                          |
| ---------------- | ---------------------- | ---------------------------------------------------- |
| `search_records` | `list[dict[str, Any]]` | Matched records with at minimum the `attributes` key |

## Observability models

### `SalesforceApiUsage`

Parsed from the `Sforce-Limit-Info` response header on every API call.

| Attribute | Type  | Description                                  |
| --------- | ----- | -------------------------------------------- |
| `used`    | `int` | API calls made in the current 24-hour window |
| `limit`   | `int` | Total API calls allowed by the org's plan    |

### `SalesforceLimitsResponse`

Returned by `SalesforceUtilityService.limits()` (from `GET /limits`).
Acts as a `Mapping[str, SalesforceLimitEntry]`.

Access individual limits by key:

```python
limits_resp = sf.utility().limits()
daily = limits_resp["DailyApiRequests"]
print(f"Daily API calls: {daily.remaining} / {daily.max_value}")
```

#### `SalesforceLimitEntry`

| Attribute   | Type  | Description                         |
| ----------- | ----- | ----------------------------------- |
| `remaining` | `int` | Remaining capacity                  |
| `max_value` | `int` | Maximum capacity (total allocation) |

#### Common limit keys

| Key                              | Description                       |
| -------------------------------- | --------------------------------- |
| `DailyApiRequests`               | Daily REST API request quota      |
| `DailyBulkV2QueryJobs`           | Daily Bulk V2 query job allowance |
| `DailyAsyncApexExecutions`       | Daily async Apex execution limit  |
| `DailyGenericStreamingApiEvents` | Daily Streaming API events        |

## Error models

### `SObjectError`

Returned as `SalesforceAPIError.errors`. See the [errors reference](errors.md)
for full details.

| Attribute    | Type        | Description                  |
| ------------ | ----------- | ---------------------------- |
| `error_code` | `str`       | Salesforce error code        |
| `message`    | `str`       | Human-readable error message |
| `fields`     | `list[str]` | Fields involved in the error |
