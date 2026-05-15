# Use the Agentforce API

`SalesforceAgentService` wraps the Salesforce Agent API (Agentforce).
It manages agent sessions, sends messages, handles streaming responses,
and submits feedback.

## Prerequisites

A configured `SalesforceAPIFacade` with a client that has access to the
Agentforce API endpoints:

```python
from plynth.connectors.salesforce.facade import SalesforceAPIFacade

sf = SalesforceAPIFacade(client)
agent = sf.agent()
```

You need the **agent ID** from your Salesforce org — find it in Setup
under *Agents*.

______________________________________________________________________

## Start a session

A session represents a conversation with an agent. Start one before
sending messages:

```python
session = agent.start_session("0XxXX0000000001AAA")
print(session.session_id)
```

Pass optional context key-value pairs to provide the agent with initial
context:

```python
session = agent.start_session(
    "0XxXX0000000001AAA",
    context={"account_id": "001Dn000001abcDIAQ", "locale": "nl"},
)
```

`AgentSession` fields:

| Field        | Type  | Description                                           |
| ------------ | ----- | ----------------------------------------------------- |
| `session_id` | `str` | ID used in all subsequent calls for this conversation |

______________________________________________________________________

## Send a message

```python
response = agent.send_message(session.session_id, "What is the status of my order?")

for item in response.messages:
    if item.type == "Text":
        print(item.value)
```

Pass optional metadata to attach caller context:

```python
response = agent.send_message(
    session.session_id,
    "Show me open cases",
    metadata={"user_id": "005Dn000001xyz"},
)
```

`AgentMessageResponse` fields:

| Field      | Type   | Description                                      |
| ---------- | ------ | ------------------------------------------------ |
| `messages` | `list` | Agent reply messages (text, actions, references) |
| `is_final` | `bool` | `True` when the agent has finished responding    |

______________________________________________________________________

## Stream a response

For user-facing applications that need incremental output, use
`send_message_streaming()`. It returns a `StreamingResponse` that you
iterate:

```python
stream = agent.send_message_streaming(session.session_id, "Summarise account Acme")
for chunk in stream:
    print(chunk, end="", flush=True)
```

In async code, `send_message_streaming()` returns an `AsyncStreamingResponse`:

```python
stream = await agent.send_message_streaming(session.session_id, "Hello")
async for chunk in stream:
    print(chunk, end="", flush=True)
```

______________________________________________________________________

## End a session

Always end the session when the conversation is complete to release
Salesforce resources:

```python
ack = agent.end_session(session.session_id)
print(ack.success)
```

Use a `try/finally` block to guarantee cleanup:

```python
session = agent.start_session(agent_id)
try:
    response = agent.send_message(session.session_id, "Hello")
    # ... handle response ...
finally:
    agent.end_session(session.session_id)
```

______________________________________________________________________

## Submit feedback

Rate an agent response to improve future behaviour:

```python
agent.submit_feedback(
    session_id=session.session_id,
    rating=5,                           # 1–5
    message_id=response.messages[0].id, # optional — tie to a specific message
    comment="Very helpful answer",      # optional
)
```

______________________________________________________________________

## Async

```python
from plynth.connectors.salesforce.facade import AsyncSalesforceAPIFacade

sf = AsyncSalesforceAPIFacade(async_client)
agent = sf.agent()

session = await agent.start_session(agent_id)
try:
    response = await agent.send_message(session.session_id, "Hello")
finally:
    await agent.end_session(session.session_id)
```

______________________________________________________________________

## See also

- [Use the Models API](use-models-api.md) — Einstein chat completions and
  embeddings without a session
- [Handle Salesforce errors](handle-errors.md)
- [Services reference](../reference/services.md)
