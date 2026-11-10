# VycePay → VyceScore: Data Push Integration Guide

Oct 10, 2026 · @Iftikhar

## Overview

This guide explains how the VycePay wallet sends transaction data to VyceScore. It is for VycePay backend and data engineers.

In this phase the integration runs **one way only**: VycePay pushes data in, and VyceScore uses it to build customers' credit profiles. VycePay does not retrieve scores from VyceScore in this phase. Score retrieval will be covered in a separate guide when the wallet starts offering loans.

| What flows | Mechanism | Freshness |
| --- | --- | --- |
| FT/IBFT transfers, P2P and bill payments, remittances, merchant payments | Kafka events | Real-time, within seconds of each transaction |
| The same transactions, full day | Daily batch extract | T-1, available before 01:30 UTC |

## Getting started

Before writing code, request the following from the VyceScore team for each environment (sandbox, staging, production). Store every secret in your secrets manager, never in source control or app bundles.

| Item | Used for | Notes |
| --- | --- | --- |
| Kafka bootstrap servers | Publishing real-time events | Hostnames and ports |
| Kafka SASL credentials | Authenticating the producer | Mechanism, username and password |
| PII hashing salt | Hashing national IDs and counterparty IDs in events | Shared secret; must match VyceScore's salt exactly |
| Batch delivery details | Daily T-1 data extract | File-drop location and credentials, or the network route for read-only views (see Daily batch extract) |

Recommended order of work:

1. Implement PII hashing and verify it against the test vectors the VyceScore team provides.
2. Publish test events to the sandbox Kafka topics and ask the VyceScore team to confirm receipt.
3. Set up the daily batch extract with the VyceScore data engineering team.
4. Complete the go-live checklist at the end of this guide.

## Security and PII hashing

All connections to VyceScore must be encrypted (TLS). Raw national IDs, phone numbers and names must never leave VycePay: not in Kafka events, batch files or database views. Hash IDs before sending:

1. Normalise the national ID: trim whitespace, convert to upper case.
2. Prepend the shared salt from the VyceScore team.
3. Take the SHA-256 digest and send it as 64 lower-case hex characters.

```python
import hashlib

def hash_national_id(national_id: str, salt: str) -> str:
    normalised = national_id.strip().upper()
    return hashlib.sha256(f"{salt}{normalised}".encode("utf-8")).hexdigest()
```

Apply the same function to counterparty IDs. A wrong salt or normalisation produces hashes that cannot be linked to the customer, and their transactions will not count towards their credit profile.

If credentials or the salt leak, contact the VyceScore team at once so they can be rotated.

## Sending real-time events (Kafka)

Publish one JSON event to Kafka for every completed wallet transaction, within seconds of completion. VyceScore uses these events for intraday activity signals and fraud alerts; the nightly batch remains the source of truth for credit profiles.

**Topics**

| Topic | Publish when |
| --- | --- |
| `vycepay.transactions.v1` | A fund transfer (FT), inter-bank transfer (IBFT), P2P or bill payment completes |
| `vycepay.remittances.v1` | An inbound or outbound cross-border remittance completes |
| `vycepay.merchant.v1` | A customer pays a merchant |

Connect with the bootstrap servers and SASL credentials from the VyceScore team, over TLS (`SASL_SSL`). Use the customer's `national_id_hash` as the message key so each customer's events stay in order on one partition.

**Event fields** (UTF-8 JSON, one object per message)

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `event_id` | string | Yes | Unique per event; reuse it on retries so duplicates can be dropped |
| `transaction_id` | string | Yes | VycePay transaction reference |
| `national_id_hash` | string | Yes | Salted SHA-256 of the wallet holder's national ID (see Security and PII hashing) |
| `transaction_type` | string | Yes | Same values as the daily batch: `FT`, `IBFT`, `BILL_PAY`, `MERCHANT`, `REMIT`, `CASH_IN`, `CASH_OUT` |
| `amount` | number | Yes | Transaction value in major units (e.g. 1500.50) |
| `currency` | string | Yes | ISO 4217 code, e.g. `KES`, `USD` |
| `timestamp` | string | Yes | ISO 8601 in UTC, e.g. `2026-10-10T08:15:30Z` |
| `counterparty_hash` | string | No | Salted SHA-256 of the other party's ID |
| `merchant_category_code` | string | Merchant events | 4-digit MCC |
| `is_cross_border` | boolean | No | `true` for international flows; defaults to `false` |
| `latitude` | number | No | Device or agent location at transaction time, decimal degrees |
| `longitude` | number | No | As above |

Send every required field explicitly. Missing fields are not rejected; they default to empty or zero values and silently distort the customer's profile. Location fields feed the Geographic Operational Stability (GOS) feature, so send them when the customer has granted location consent.

**Example**

```json
{
  "event_id": "evt_01HZX8K2M4",
  "transaction_id": "VP-TX-20261010-000123",
  "national_id_hash": "9f2c4a7e0b1d...64 hex chars",
  "transaction_type": "MERCHANT",
  "amount": 1500.50,
  "currency": "KES",
  "counterparty_hash": "3b8e1f6a92cd...64 hex chars",
  "merchant_category_code": "5411",
  "is_cross_border": false,
  "latitude": -1.2864,
  "longitude": 36.8172,
  "timestamp": "2026-10-10T08:15:30Z"
}
```

**Delivery rules**

- Configure the producer with `acks=all` and idempotence enabled; retry on failure with the same `event_id`.
- Publish only completed transactions. Report reversals as a new event referencing the original `transaction_id`, after agreeing the format with the VyceScore team.
- Adding a field is backward compatible. Renaming, removing or retyping a field needs a new topic version (`.v2`) agreed in advance.

## Daily batch extract (T-1)

The daily batch is **mandatory**: it is the data VyceScore builds credit profiles from. VycePay delivers one complete day of data (00:00:00–23:59:59 UTC) every night, ready by **01:30 UTC**, when VyceScore starts processing. Profiles are refreshed by about 03:00 UTC.

VycePay can deliver the data in one of two ways, agreed with the VyceScore data engineering team:

| Option | How it works | Recommended |
| --- | --- | --- |
| Nightly file drop | VycePay uploads files to a location the VyceScore team provides (SFTP or S3-compatible bucket) | Yes |
| Read-only database views | VycePay exposes read-only views on a replica; VyceScore queries one day at a time | Only if a file drop is not possible |

Both options use exactly the same datasets and columns, described below. VyceScore only reads; it never writes to VycePay systems.

### Datasets

| Dataset | One row per | File name / view name |
| --- | --- | --- |
| Transactions | Wallet transaction (all types, including remittances and merchant payments) | `transactions` / `vycescore_transactions` |
| Merchant daily summary | Merchant per day (only for customers who accept payments as merchants) | `merchant_daily` / `vycescore_merchant_daily` |

### Transactions: columns

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `transaction_id` | string | Yes | Unique within the day's file |
| `national_id_hash` | string | Yes | Wallet holder's national ID, hashed as in Security and PII hashing; 64 lower-case hex characters |
| `transaction_type` | string | Yes | One of `FT` (wallet-to-wallet / P2P), `IBFT` (to or from a bank), `BILL_PAY`, `MERCHANT`, `REMIT`, `CASH_IN`, `CASH_OUT` |
| `direction` | string | Yes | `CREDIT` (money in to the wallet holder) or `DEBIT` (money out) |
| `status` | string | Yes | `COMPLETED`, `PENDING`, `FAILED` or `REVERSED` |
| `amount` | decimal | Yes | Greater than 0, in major units (e.g. 1500.50), at most 50,000,000 |
| `currency` | string | Yes | ISO 4217: `KES`, `USD`, `EUR`, `GBP`, `UGX`, `TZS`, `RWF` or `ETB` |
| `timestamp` | timestamp | Yes | UTC, ISO 8601 (e.g. `2026-10-10T08:15:30Z`) |
| `is_cross_border` | integer | Yes | `1` for international flows, otherwise `0` |
| `counterparty_hash` | string | When known | Other party's ID, hashed the same way |
| `merchant_category_code` | string | `MERCHANT` rows | 4-digit MCC |
| `latitude` | decimal | No | Decimal degrees; only with location consent |
| `longitude` | decimal | No | As above |
| `source_country` | string | `REMIT` rows | ISO 3166-1 alpha-2 country the funds came from (e.g. `AE`) |
| `sender_relationship` | string | `REMIT` rows, if known | `FAMILY`, `BUSINESS` or `PERSONAL` |
| `original_transaction_id` | string | Reversals | The `transaction_id` being reversed |

### Merchant daily summary: columns

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `merchant_id` | string | Yes | VycePay merchant reference |
| `national_id_hash` | string | Yes | Hash of the merchant owner's national ID |
| `merchant_category_code` | string | Yes | 4-digit MCC |
| `business_date` | date | Yes | The UTC day summarised, `YYYY-MM-DD` |
| `transaction_count` | integer | Yes | Completed payments received that day |
| `transaction_value` | decimal | Yes | Total value of those payments, in `currency` |
| `currency` | string | Yes | ISO 4217 |

### File drop format

- **Format.** Apache Parquet with Snappy compression (preferred). If Parquet is not possible, UTF-8 CSV with a header row, comma separator, `"` quoting and gzip compression (`.csv.gz`). Column names exactly as above.
- **Layout.** One folder per day:

```text
vycepay/dt=2026-10-09/transactions.parquet
vycepay/dt=2026-10-09/merchant_daily.parquet
vycepay/dt=2026-10-09/_manifest.json
```

- **Manifest.** Upload `_manifest.json` last; VyceScore starts reading only once it exists. It lists every file with its row count and SHA-256 checksum:

```json
{
  "business_date": "2026-10-09",
  "generated_at": "2026-10-10T00:45:12Z",
  "files": [
    {"name": "transactions.parquet", "rows": 184233, "sha256": "5d41402abc4b2a76..."},
    {"name": "merchant_daily.parquet", "rows": 2310, "sha256": "7d793037a0760186..."}
  ]
}
```

- **Empty days.** Still deliver the folder and a manifest with `"rows": 0`, so VyceScore can tell a quiet day from a missing one.

### Read-only views (alternative)

Expose `vycescore_transactions` and `vycescore_merchant_daily` with exactly the columns above, already hashed: raw national IDs must not be visible to VyceScore. VyceScore selects one UTC day at a time by `timestamp` (or `business_date`). Provide a read-only database user, the connection details and an allow-listed network route through the VyceScore team.

### Rules for both options

- Include every transaction whose `timestamp` falls in the day, whatever its status.
- A status change after the day (for example a reversal) appears in the file for the day it happens, as a new row with its own `transaction_id` and `original_transaction_id` pointing to the original.
- Late or corrected data for an earlier day: re-deliver that day's folder in full with a new manifest, and tell the VyceScore team so they can reprocess it. Reprocessing overwrites the day.
- VyceScore compares delivered and loaded row counts and raises an alert when they differ by more than 0.1%.
- Schema changes (new, renamed or retyped columns): agree them with the VyceScore team at least 5 working days in advance. Adding an optional column is backward compatible; anything else needs a new agreed version.
- Planned outages: notify the VyceScore team at least 5 working days in advance.

## Compliance obligations

VycePay is the data controller for wallet data and must have a lawful basis, normally explicit consent, before sharing a customer's data with VyceScore.

- **Consent.** Capture consent in the wallet app for (a) sharing transaction data for credit scoring and (b) location data, separately. Store the consent record and timestamp. Stop sending events for customers who withdraw consent, and tell the VyceScore team so their data can be handled under the data-rights process.
- **Data minimisation.** Send only the fields in this guide. Never put names, phone numbers or raw national IDs in Kafka events, logs or analytics tools.
- **Encryption.** Use TLS for every Kafka and batch-extract connection.
- **Retention.** VyceScore keeps derived data for 10 years for regulatory reasons; raw transaction data is anonymised after feature extraction. Reflect this in the wallet's privacy notice.

## Testing and go-live

Build and test against the sandbox environment first. Sign-off on every item below is required before production credentials are issued.

- [ ] Production Kafka credentials, salt and batch-extract details received and stored in the secrets manager
- [ ] Hashing output matches the VyceScore team's test vectors
- [ ] Sample events published to all three topics; VyceScore confirms hashes match known test customers
- [ ] Producer retries tested; duplicate events carry the same `event_id`
- [ ] One full day's batch extract delivered and reconciled by the VyceScore data team
- [ ] Consent capture and withdrawal live in the wallet app
- [ ] No raw national IDs, phone numbers or credentials in VycePay logs
- [ ] Contacts for incidents named on both sides

**Support.** Contact the VyceScore team through the channel agreed at onboarding. Include the environment, the topic or batch date, the `event_id` where relevant, and the time in UTC. Never send raw national IDs or credentials in support messages.
