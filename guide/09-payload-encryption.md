# 09 — Encrypting payloads (codec + gateway)

> **Goal of this step.** Encrypt every payload that crosses the Temporal
> boundary, so sensitive fields (bank identifiers, amounts) rest in Event
> History as ciphertext — then use a **codec server** behind the gateway
> to decrypt them on demand in the Web UI.

## At a glance

|                       |                                                                                                                                                                                                             |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Feature**           | `payload-encryption`                                                                                                                                                                                        |
| **Files touched**     | [`payments/main_worker.py`](../payments/main_worker.py), [`payments/api.py`](../payments/api.py) (uses [`shared/encryption.py`](../shared/encryption.py), [`codec/`](../codec/), [`gateway/`](../gateway/)) |
| **Temporal concepts** | `PayloadCodec`, data converters, the codec server, encryption at the boundary                                                                                                                               |
| **Docs**              | [Data encryption](https://docs.temporal.io/production-deployment/data-encryption)                                                                                                                           |
| **Builds on**         | step [02](02-durable-agents.md)                                                                                                                                                                             |

## Why this matters

A cross-border payment carries data you do not want sitting in plaintext
in Event History — BICs, amounts, beneficiary details. A **`PayloadCodec`**
sits at the very edge of serialization: the SDK calls `encode` on the way
out and `decode` on the way in, so payloads travel and rest as ciphertext.
The trade-off: the Web UI now shows ciphertext too — which is where the
**codec server** comes in. This is a headline production concern for the
workshop.

## Step 1 — Preview the change

```bash
make feature-diff NAME=payload-encryption
```

## Step 2 — Enable it

```bash
make feature-enable NAME=payload-encryption
```

> **Nothing else to configure for the demo.** When `CODEC_ENCRYPTION_KEY`
> and `CODEC_SERVER_AUTH_TOKEN` are unset, both the codec server and the
> gateway fall back to matching public, **insecure** built-in defaults
> (logging a warning), so decoding works out of the box. Set your own keys
> in `.env` only when you want to actually secure the setup.

## Step 3 — Read the code

**The codec itself** — [`shared/encryption.py`](../shared/encryption.py)
defines `EncryptionCodec`, a `PayloadCodec` that encrypts with **Fernet**
(AES-128-CBC + HMAC). Note two production-minded details in its `NOTE:`s:

- `encode` marks its output with an `encoding` metadata tag, and `decode`
  passes through anything *not* carrying that tag — so mixed
  plaintext/ciphertext histories decode gracefully.
- Fernet's crypto runs via `asyncio.to_thread` to keep the event loop
  responsive.

**Wiring it in** — the feature is a `REPLACE` in *two* processes, the
worker ([`payments/main_worker.py`](../payments/main_worker.py)) and the
API ([`payments/api.py`](../payments/api.py)). Both swap their
`Client.connect(...)` for one that passes an encrypting data converter:

```python
key = load_key()
if not key:
    raise RuntimeError("set CODEC_ENCRYPTION_KEY to enable payload encryption")
client = await Client.connect(
    TEMPORAL_ADDRESS,
    namespace=PAYMENTS_TEMPORAL_NAMESPACE,
    data_converter=build_data_converter(EncryptionCodec(key)),
    plugins=[PydanticAIPlugin()],
)
```

Read the `NOTE:` — the `PydanticAIPlugin` stays alongside the explicit
`data_converter` on purpose: the plugin only installs its own converter
when you do not pass one, and dropping it breaks `TemporalAgent` sandbox
validation at worker start-up.

**The codec server and the gateway** — the codec server
([`codec/`](../codec/)) is a small HTTP service that reuses the same key to
decrypt payloads on demand; the gateway ([`gateway/`](../gateway/)) routes
`/codec` to it. Both come up with the stack. The gateway is the single
published entry point (`http://localhost:8080`): it serves the Web UI at
`/` and the codec at `/codec`, so the UI's calls to `/codec` are
**same-origin** — no CORS — and the gateway **injects the bearer token**
so you never configure `--codec-auth`.

## Step 4 — Run and observe

Fire a correction:

```bash
make simulator
```

**Before wiring the UI to the codec:** open the coordinator in the Web UI
and inspect Event History — payloads now show as raw ciphertext.

![Encrypted (ciphertext) payloads in Event History before decoding](images/09-ciphertext.png)

**Decoded:** the dev server is already pointed at the codec through the
gateway (via its `--ui-codec-endpoint http://localhost:8080/codec` flag),
so the Web UI decrypts payloads for display automatically — the same
Event History now shows cleartext.

![The same payloads shown as cleartext after the codec decodes them](images/09-decoded.png)

**From the CLI**, point `temporal` at the codec through the gateway (no
`--codec-auth` needed — the gateway injects the token):

```bash
temporal workflow show \
  --workflow-id correction-<payment_id> \
  --namespace payments \
  --codec-endpoint http://localhost:8080/codec
```

> **Run the `temporal` CLI from the host, never a container** —
> `localhost:8080/codec` reaches the gateway only from the host.

## Step 5 — The production caveat

The reference codec server requires a bearer token, but with the insecure
defaults it is effectively an **unauthenticated decryption oracle** — the
[production-ready checklist](../production-ready-checklist.md) spells this
out: a codec server must be authenticated (mTLS or a bearer token) and
TLS-terminated, or anyone who can reach it can decrypt any payload. Set
`CODEC_ENCRYPTION_KEY` and `CODEC_SERVER_AUTH_TOKEN` to real values to
close that gap.

## Step 6 — Checkpoint

- [ ] Event History shows ciphertext with the feature on.
- [ ] The Web UI decodes payloads through the gateway `/codec` route.
- [ ] You can explain why the codec server must be authenticated in
      production.

## Revert

```bash
make feature-disable NAME=payload-encryption
```

---

Next: [10 — Durable state as an Entity Workflow](10-memory-workflow.md).
