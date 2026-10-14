"""Pydantic models for the Salesforce Platform REST API.

Provides typed models for the generic SObject operations that are consistent
across all Salesforce SObject types:

- ``SObjectError`` — an individual error entry returned by Salesforce.
- ``SObjectCreateResult`` — the response body from a successful ``create()``
  or ``upsert()`` (HTTP 201 Created).
- ``SObjectPayload`` — base class for typed SObject request payloads. Subclass
  this to define field mappings from Python attribute names to Salesforce API
  field names using Pydantic's ``Field(serialization_alias=...)``.

Object-specific shapes (``get()`` responses, ``describe()`` metadata) differ
per SObject type and are intentionally left as ``dict[str, Any]``.

Example — defining a typed payload::

    from pydantic import Field
    from plynt.connectors.salesforce.models import SObjectPayload

    class AccountPayload(SObjectPayload):
        name: str = Field(serialization_alias="Name")
        phone: str | None = Field(None, serialization_alias="Phone")
        external_id: str | None = Field(None, serialization_alias="My_External_Id__c")

    payload = AccountPayload(name="ACME Corp", phone="+31201234567")
    svc.create(payload)  # sends {"Name": "ACME Corp", "Phone": "+31201234567"}

"""

from __future__ import annotations

from collections.abc import ItemsView, KeysView, ValuesView
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, RootModel

__all__ = [
    "AgentFeedbackRequest",
    "AgentMessageRequest",
    "AgentMessageResponse",
    "AgentSession",
    "AgentSessionEndAck",
    "AgentSessionStartRequest",
    "ChatCompletionResponse",
    "ChatMessage",
    "EmbeddingResponse",
    "FeedbackAck",
    "ModelsChatGenerationRequest",
    "ModelsEmbeddingRequest",
    "ModelsFeedbackRequest",
    "ModelsTextGenerationRequest",
    "SObjectCreateResult",
    "SObjectError",
    "SObjectPayload",
    "SalesforceApiUsage",
    "SalesforceApiVersion",
    "SalesforceGlobalDescribeResponse",
    "SalesforceLimit",
    "SalesforceLimitsResponse",
    "SalesforceQueryResponse",
    "SalesforceSObjectSummary",
    "SalesforceSearchRecord",
    "SalesforceSearchResponse",
    "TextGenerationResponse",
]


class SalesforceApiVersion(BaseModel):
    """A single Salesforce API version entry from ``GET /services/data/``.

    Salesforce returns a fixed-format list of all available API versions
    on the org. The ``version`` field contains the bare version string
    (e.g. ``"63.0"``), which can be used directly as the ``api_version``
    parameter on services and clients.

    Example::

        versions = utility.versions()
        latest = versions[-1]
        print(latest.label, latest.version)

    """

    label: str
    url: str
    version: str


class SalesforceLimit(BaseModel):
    """Single Salesforce organization limit entry.

    Attributes:
        max_value: Maximum allowed value for the limit.
        remaining: Remaining value for the current window.

    """

    model_config = ConfigDict(populate_by_name=True)

    max_value: int = Field(alias="Max")
    remaining: int = Field(alias="Remaining")


class SalesforceApiUsage(BaseModel):
    """Parsed API usage values from ``Sforce-Limit-Info`` response headers."""

    used: int
    limit: int


class SalesforceLimitsResponse(RootModel[dict[str, SalesforceLimit]]):
    """Typed response model for ``GET /limits`` payloads.

    Supports dict-like access by key, ``items()``, ``keys()``, and
    ``values()`` — no need to go through ``.root``.

    Example::

        limits = utility.limits()
        for name, limit in limits.items():
            print(name, limit.remaining, "/", limit.max_value)

        daily = limits["DailyApiRequests"]
        print(daily.remaining)

        # Plain-dict or JSON serialisation:
        data = limits.model_dump()        # {"DailyApiRequests": {"max_value": …}}
        json_str = limits.model_dump_json()  # '{"DailyApiRequests": {"max_value": …}}'

    """

    _api_usage: SalesforceApiUsage | None = PrivateAttr(default=None)

    def __getitem__(self, key: str) -> SalesforceLimit:
        """Return the limit entry for the given name."""
        return self.root[key]

    @property
    def api_usage(self) -> SalesforceApiUsage | None:
        """Return parsed ``api-usage`` header values when available."""
        return self._api_usage

    def set_api_usage(self, api_usage: SalesforceApiUsage | None) -> None:
        """Attach parsed ``api-usage`` header metadata to this response."""
        self._api_usage = api_usage

    def __len__(self) -> int:
        """Return the number of limit entries."""
        return len(self.root)

    def __contains__(self, key: object) -> bool:
        """Return ``True`` when ``key`` names a known limit entry."""
        return key in self.root

    def keys(self) -> KeysView[str]:
        """Return the limit names, mirroring ``dict.keys()``."""
        return self.root.keys()

    def values(self) -> ValuesView[SalesforceLimit]:
        """Return the ``SalesforceLimit`` entries, mirroring ``dict.values()``."""
        return self.root.values()

    def items(self) -> ItemsView[str, SalesforceLimit]:
        """Return ``(name, SalesforceLimit)`` pairs, mirroring ``dict.items()``."""
        return self.root.items()


class SalesforceQueryResponse(BaseModel):
    """Typed response model for a SOQL ``GET /query`` result.

    Attributes:
        total_size: Total number of records matched by the query.
        done: ``True`` when all records are included; ``False`` when
            Salesforce has paginated and a ``next_records_url`` is present.
        next_records_url: URL to fetch the next page of results, or ``None``
            when all records are already included (i.e. ``done`` is ``True``).
        records: List of matching records as raw dicts. Field names follow
            Salesforce API conventions (e.g. ``"Name"``, ``"Id"``).

    """

    model_config = ConfigDict(populate_by_name=True)

    total_size: int = Field(alias="totalSize")
    done: bool
    next_records_url: str | None = Field(None, alias="nextRecordsUrl")
    records: list[dict[str, Any]] = Field(default_factory=list)


class SalesforceSearchRecord(BaseModel):
    """A single record returned by a SOSL search.

    The ``attributes`` dict always contains ``type`` (SObject type name) and
    ``url`` (resource path).  Any additional fields requested via the SOSL
    ``RETURNING`` clause are captured as extra fields and accessible via
    ``__getitem__``.

    Example::

        response = utility.search(
            "FIND {Acme} IN NAME FIELDS RETURNING Account(Id, Name)"
        )
        for record in response.search_records:
            print(record.sobject_type, record.id, record["Name"])

    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    attributes: dict[str, str] = Field(default_factory=dict)
    id: str = Field("", alias="Id")

    @property
    def sobject_type(self) -> str:
        """SObject type of this record (e.g. ``"Account"``)."""
        attributes = self.attributes
        if isinstance(attributes, dict) and "type" in attributes:
            return attributes["type"]
        return ""

    def __getitem__(self, key: str) -> Any:
        """Return the field value for ``key``, checking ``Id`` first."""
        if key == "Id":
            return self.id
        extra = self.model_extra
        if isinstance(extra, dict) and key in extra:
            return extra[key]
        return None


class SalesforceSearchResponse(BaseModel):
    """Typed response model for a SOSL ``GET /search`` result.

    Attributes:
        search_records: List of matched records. Each record exposes ``id``,
            ``sobject_type``, and arbitrary extra fields from the
            ``RETURNING`` clause via ``record["FieldName"]``.

    Example::

        response = utility.search(
            "FIND {Inc} IN NAME FIELDS RETURNING Account(Id, Name)"
        )
        print(len(response.search_records))
        for record in response.search_records:
            print(record.sobject_type, record.id, record["Name"])

    """

    model_config = ConfigDict(populate_by_name=True)

    search_records: list[SalesforceSearchRecord] = Field(
        default_factory=list, alias="searchRecords"
    )


class ChatMessage(BaseModel):
    """Typed chat message payload used by Salesforce Models API calls."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    role: str
    content: str | list[dict[str, Any]]
    name: str | None = None


class ModelsChatGenerationRequest(BaseModel):
    """Typed request payload for chat generation."""

    model_config = ConfigDict(populate_by_name=True)

    messages: list[ChatMessage | dict[str, Any]]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    metadata: dict[str, str] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a request payload with provider-compatible message objects."""
        payload = self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude={"messages"},
        )
        payload["messages"] = [
            message.model_dump(mode="json", by_alias=True, exclude_none=True)
            if isinstance(message, ChatMessage)
            else message
            for message in self.messages
        ]
        return payload


class ModelsTextGenerationRequest(BaseModel):
    """Typed request payload for text generation."""

    model_config = ConfigDict(populate_by_name=True)

    prompt: str
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a request payload for the text-generation endpoint."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class ModelsEmbeddingRequest(BaseModel):
    """Typed request payload for embedding generation."""

    model_config = ConfigDict(populate_by_name=True)

    input_text: str | list[str] = Field(serialization_alias="input")
    model: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a request payload for the embeddings endpoint."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class ModelsFeedbackRequest(BaseModel):
    """Typed request payload for model inference feedback."""

    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(serialization_alias="requestId")
    rating: int
    comment: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a request payload for model feedback submission."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class AgentSessionStartRequest(BaseModel):
    """Typed request payload for starting an agent session."""

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(serialization_alias="agentId")
    context: dict[str, str] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a request payload for session creation."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class AgentMessageRequest(BaseModel):
    """Typed request payload for agent session messaging."""

    model_config = ConfigDict(populate_by_name=True)

    text: str
    metadata: dict[str, str] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a request payload for posting a session message."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class AgentFeedbackRequest(BaseModel):
    """Typed request payload for agent feedback submission."""

    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(serialization_alias="sessionId")
    rating: int
    message_id: str | None = Field(default=None, serialization_alias="messageId")
    comment: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a request payload for agent feedback submission."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class ChatCompletionResponse(BaseModel):
    """Typed response model for a model chat-generation call."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    model: str | None = None
    choices: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, int] | None = None


class TextGenerationResponse(BaseModel):
    """Typed response model for a model text-generation call."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    model: str | None = None
    text: str = ""


class EmbeddingResponse(BaseModel):
    """Typed response model for model embedding generation."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    model: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)


class FeedbackAck(BaseModel):
    """Typed acknowledgement model for feedback endpoints."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool = True
    request_id: str | None = Field(default=None, alias="requestId")


class AgentSession(BaseModel):
    """Typed model for an agent session creation response."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    session_id: str = Field(alias="sessionId")
    agent_id: str | None = Field(default=None, alias="agentId")
    status: str | None = None


class AgentMessageResponse(BaseModel):
    """Typed model for a synchronous agent message response."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    session_id: str = Field(alias="sessionId")
    message_id: str | None = Field(default=None, alias="messageId")
    output_text: str | None = Field(default=None, alias="outputText")


class AgentSessionEndAck(BaseModel):
    """Typed acknowledgement model for ending an agent session."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    session_id: str | None = Field(default=None, alias="sessionId")
    ended: bool = True


class SObjectError(BaseModel):
    """A single error entry in a Salesforce error response.

    Salesforce returns errors as a list of objects within the response body.
    Field names follow the Salesforce REST API conventions (``errorCode`` is
    camelCase in the wire format); this model exposes them with Python-friendly
    names.

    Attributes:
        message: Human-readable description of the error.
        error_code: Salesforce error code (e.g. ``"REQUIRED_FIELD_MISSING"``,
            ``"DUPLICATES_DETECTED"``).
        fields: List of field API names involved in the error. May be empty.

    """

    model_config = ConfigDict(populate_by_name=True)

    message: str
    error_code: str = Field(alias="errorCode")
    fields: list[str] = Field(default_factory=list)


class SObjectCreateResult(BaseModel):
    """Response body for a successful SObject create or upsert (HTTP 201).

    Returned by ``create()`` and by ``upsert()`` when a new record is created.
    When ``upsert()`` updates an existing record (HTTP 204), ``None`` is
    returned instead.

    Attributes:
        id: The Salesforce-assigned 18-character record ID of the created
            record.
        success: ``True`` when the operation succeeded.
        errors: List of error entries. Non-empty only when ``success`` is
            ``False``.

    """

    id: str
    success: bool
    errors: list[SObjectError] = Field(default_factory=list)


class SObjectPayload(BaseModel):
    """Base class for typed SObject request payloads.

    Provides automatic field-name translation from Python attribute names to
    Salesforce API field names via Pydantic's ``serialization_alias``. Fields
    with ``None`` values are excluded from the payload by default, so omitted
    optional fields are not sent to Salesforce.

    Subclass this and declare fields with ``Field(serialization_alias=...)``.
    Pass an instance directly to ``SalesforceObjectService.create()``,
    ``update()``, or ``upsert()`` — the service calls ``to_payload()``
    automatically.

    Example::

        from pydantic import Field
        from plynt.connectors.salesforce.models import SObjectPayload

        class ContactPayload(SObjectPayload):
            first_name: str = Field(serialization_alias="FirstName")
            last_name: str = Field(serialization_alias="LastName")
            email: str | None = Field(None, serialization_alias="Email")
            legacy_id: str | None = Field(None, serialization_alias="Legacy_Id__c")

        svc.create(ContactPayload(first_name="Ada", last_name="Lovelace"))
        # → POST body: {"FirstName": "Ada", "LastName": "Lovelace"}

    """

    model_config = ConfigDict(populate_by_name=True)

    def to_payload(self) -> dict[str, Any]:
        """Return the payload dict for the Salesforce REST API.

        Serializes the model using Salesforce field names (``serialization_alias``)
        and excludes any fields whose value is ``None``.

        """
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class SalesforceSObjectSummary(BaseModel):
    """Summary metadata for a single SObject type from ``GET /sobjects``.

    Each entry in the global describe response describes one Salesforce
    SObject type available on the org, including its capabilities (queryable,
    createable, etc.) and the API URLs for that object.

    Attributes:
        name: API name of the SObject (e.g. ``"Account"``, ``"Contact"``).
        label: Human-readable singular label (e.g. ``"Account"``).
        label_plural: Human-readable plural label (e.g. ``"Accounts"``).
        key_prefix: Three-character record ID prefix, or ``None`` when not
            applicable.
        queryable: Whether SOQL queries are supported.
        createable: Whether records can be created.
        updateable: Whether records can be updated.
        deletable: Whether records can be deleted.
        searchable: Whether SOSL searches are supported.
        custom: Whether this is a custom object (``__c`` suffix).
        urls: Map of URL type to resource path (e.g. ``"sobject"``,
            ``"describe"``, ``"rowTemplate"``).

    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    label: str
    label_plural: str = Field(alias="labelPlural")
    key_prefix: str | None = Field(None, alias="keyPrefix")
    activateable: bool = False
    bulk_deletable: bool = Field(False, alias="bulkDeletable")
    createable: bool = False
    custom: bool = False
    custom_setting: bool = Field(False, alias="customSetting")
    deep_cloneable: bool = Field(False, alias="deepCloneable")
    deletable: bool = False
    deprecated_and_hidden: bool = Field(False, alias="deprecatedAndHidden")
    feed_enabled: bool = Field(False, alias="feedEnabled")
    has_subtypes: bool = Field(False, alias="hasSubtypes")
    is_interface: bool = Field(False, alias="isInterface")
    is_subtype: bool = Field(False, alias="isSubtype")
    layoutable: bool = False
    mergeable: bool = False
    mru_enabled: bool = Field(False, alias="mruEnabled")
    queryable: bool = False
    replicateable: bool = False
    retrieveable: bool = False
    searchable: bool = False
    triggerable: bool = False
    undeletable: bool = False
    updateable: bool = False
    urls: dict[str, str] = Field(default_factory=dict)


class SalesforceGlobalDescribeResponse(BaseModel):
    """Typed response model for ``GET /sobjects`` (global describe).

    Returns the full catalog of SObject types available on the org, along
    with org-level metadata such as the default character encoding.

    Attributes:
        encoding: Character encoding used by the org (e.g. ``"UTF-8"``).
        max_batch_size: Maximum number of records per batch DML operation.
        sobjects: List of SObject type summaries, one per available object.

    Example::

        catalog = utility.objects()
        account = next(s for s in catalog.sobjects if s.name == "Account")
        print(account.label, account.queryable)

    """

    model_config = ConfigDict(populate_by_name=True)

    encoding: str = ""
    max_batch_size: int = Field(0, alias="maxBatchSize")
    sobjects: list[SalesforceSObjectSummary] = Field(default_factory=list)
