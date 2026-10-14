# Salesforce Examples

Markdown snippets that demonstrate the Plynt Salesforce integration against a
real Salesforce org.

These scripts are not just auth demos. They run a small end-to-end flow over
the connector services:

1. API versions discovery (`utility.versions()`)
1. Org limits retrieval (`utility.limits()`)
1. SObject metadata read (`sobject.describe()`)
1. SOQL query (`query.query(...)`)
1. SOSL search (`utility.search(...)`)

## Snippets

| Script                  | OAuth2 flow                                | When to use                                                                 |
| ----------------------- | ------------------------------------------ | --------------------------------------------------------------------------- |
| `username_password.md`  | Resource Owner Password Credentials (ROPC) | Automation under a named user; orgs where Client Credentials is unavailable |
| `client_credentials.md` | Client Credentials                         | Machine-to-machine; requires ECA with a *Run As* user configured            |

> **Note:** `client_credentials.md` requires additional Salesforce setup. If
> you have not yet configured a *Run As* user on the External Client App, use
> `username_password.md` first.

## Prerequisites

1. Install required extras:

```bash
pip install "plynt[salesforce,httpx]"
```

1. Create or access a Salesforce External Client App with OAuth enabled.
1. Copy `examples/salesforce/example.env` to `.env` and set credentials.

______________________________________________________________________

## Quick start

```bash
cp examples/salesforce/example.env examples/salesforce/.env
# Fill in your credentials, then copy the snippet into your project.
# examples/salesforce/username_password.md
```

## Validation checklist

- Output includes `AVAILABLE API VERSIONS` with at least one version.
- Output includes `ORG LIMITS` with populated values.
- Output includes `ACCOUNT SOBJECT` metadata for `Account`.
- SOQL and SOSL sections return results or an empty set without auth errors.
- These sections print with real values when the connector path is healthy.

______________________________________________________________________

## Salesforce setup — External Client App (ECA)

Salesforce has replaced the legacy *Connected App* with the **External Client
App** (ECA). The steps below use the current ECA UI.

### Step 1 — Create an External Client App

1. Go to **Setup** → search for *External Client Apps* → open
   **External Client Apps**.

1. Click **New External Client App**.

1. Fill in the required fields:

   | Field                    | Value                             |
   | ------------------------ | --------------------------------- |
   | External Client App Name | `Plynt Integration` (or any name) |
   | API Name                 | auto-filled                       |
   | Contact Email            | your email address                |

1. Click **Next**.

### Step 2 — Configure OAuth settings

1. In the **OAuth** section, enable **Enable OAuth Settings**.
1. Set **Callback URL** to `https://login.salesforce.com/services/oauth2/success`
   (any valid HTTPS URL works; it is not called by the server-side flows).
1. Under **Selected OAuth Scopes**, add at minimum:
   - *Manage user data via APIs (api)*
   - *Perform requests at any time (refresh_token, offline_access)*
1. Enable **Enable Client Credentials Flow** if you intend to use
   `client_credentials.md`.
1. Optionally disable **Require Proof Key for Code Exchange (PKCE)** — not
   needed for server-side flows.
1. Click **Save**.

### Step 3 — Retrieve Consumer Key and Secret

1. Open the ECA you just created.
1. Under **OAuth Settings**, click **Consumer Key and Secret** (or
   **Manage Consumer Details** — the label varies by release).
1. Verify your identity if prompted.
1. Copy the **Consumer Key** → use as `SF_CLIENT_ID`.
1. Copy the **Consumer Secret** → use as `SF_CLIENT_SECRET`.

### Step 4 — Allow the Username/Password flow

The ROPC (username/password) flow must be explicitly enabled:

1. Open the ECA → click **Manage** (or **Edit Policies**).
1. Under **OAuth Policies**, set **Permitted Users** to
   *All users may self-authorize* (or restrict to a specific profile).
1. Set **IP Relaxation** to *Relax IP restrictions* if your server IP is not
   in the org's trusted IP ranges.
1. Click **Save**.

### Step 5 — Security token (if required)

Salesforce appends a security token to the password when the calling IP is
not in the org's trusted IP range.

- If you see `INVALID_LOGIN: Invalid username, password, security token` →
  you need the token.
- Reset it: **Setup** → top-right user menu →
  **My Personal Information** → **Reset My Security Token**.
- The token is emailed to the address on your user record.
- Set it as `SF_SECURITY_TOKEN` in `.env`. The library appends it to the
  password automatically.

### Step 6 (optional) — Configure Client Credentials flow

This step is only needed for `client_credentials.md`.

1. Open the ECA → click **Manage** → **Edit Policies**.
1. Under **Client Credentials Flow**, set **Run As** to the integration user
   you want API calls to run as.
1. Click **Save**.

> Without a *Run As* user, the token endpoint returns
> `"request not supported on this domain"`.

______________________________________________________________________

## Environment variables

Copy `example.env` to `.env` in this directory and fill in your values.
The `.env` file is never committed to git.

| Variable            | Required          | Description                                                                                                                  |
| ------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `SF_CLIENT_ID`      | yes               | Consumer Key from the External Client App                                                                                    |
| `SF_CLIENT_SECRET`  | yes               | Consumer Secret from the External Client App                                                                                 |
| `SF_TOKEN_URL`      | yes               | `https://login.salesforce.com/services/oauth2/token` (prod) or `https://test.salesforce.com/services/oauth2/token` (sandbox) |
| `SF_USERNAME`       | password flow     | Salesforce username (e.g. `user@example.com`)                                                                                |
| `SF_PASSWORD`       | password flow     | Salesforce password                                                                                                          |
| `SF_SECURITY_TOKEN` | if IP not trusted | Security token appended to password                                                                                          |
| `SF_API_VERSION`    | no                | REST API version, e.g. `62.0` (defaults to library default)                                                                  |

______________________________________________________________________

## Troubleshooting

### `INVALID_LOGIN` with username/password

- Verify username and password are correct.
- Add `SF_SECURITY_TOKEN` when your IP is not trusted.
- Check that the password flow is enabled in OAuth policies.

### `request not supported on this domain`

- This usually means Client Credentials is not fully configured.
- Verify the ECA has a `Run As` user for Client Credentials.

### Calls succeed but query returns no rows

- Confirm the integration user can read `Account` records.
- Try the same SOQL query in Salesforce Developer Console.
