# PasarGuard Telegram VPN Sales Bot

Production-oriented Aiogram 3 bot for selling PasarGuard-backed VPN/proxy services with wallet billing, admin controls, manual and crypto payments, referral cashback, and scheduled traffic charging.

## Features

- User menu: buy service, services, wallet, invite link, wallet charge, one-time 100MB/1 day test account, support.
- Service plans: Multi Smart and Multi Economy with admin-configurable per-GB pricing.
- Wallet rules: 50,000 Toman minimum only for new paid service creation; reactivation can happen with any positive wallet balance.
- Billing job: every 60 seconds (configurable with `TRAFFIC_SYNC_SECONDS`, minimum 10) reads PasarGuard usage, computes MB deltas, bills by MB, logs usage, warns on low balance, and disables services when the wallet reaches zero or becomes negative.
- Cleanup job: deletes wallet-disabled services after 48 hours only if the wallet is still zero/negative. Manually disabled services and customers whose top-up is awaiting reactivation are preserved.
- Payments: card-to-card receipts with admin approval, Plisio, NOWPayments, Telegram Stars.
- Admin panel sections: panel management, store/tariff settings, admin settings, payment settings, and user services.
- Panel management: add, view, edit, enable/disable, and delete PasarGuard panels from Telegram.
- Store settings: add, view, edit, enable/disable, and delete custom tariffs such as Multi Hoshmand or Multi Eghtesadi with per-GB prices.
- Admin settings: add, view, and remove Telegram admins from the Telegram panel. Environment admins remain protected by `.env`.
- User services: lookup user by numeric Telegram ID, view wallet/service counts, block fake users, broadcast to all users.
- Admin service management: view active/disabled services and disable, reactivate, or delete them from Telegram.
- Secure settings: provider API tokens are encrypted at rest with `SECRET_KEY`.

## Setup

1. Copy `.env.example` to `.env` and fill `BOT_TOKEN`, `SECRET_KEY`, and initial `ENV_ADMIN_IDS`.
2. Start PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
```

3. Run migrations:

```bash
alembic upgrade head
```

4. Start the bot:

```bash
docker compose up --build bot
```

## Admin Usage

- Open `/admin` in Telegram from an ID listed in `ENV_ADMIN_IDS` or the editable `admin_ids` setting.
- Settings are edited inside Telegram. Boolean payment settings accept `true` or `false`.
- Card info uses this format: `card_number | card holder`.
- Balance commands:

```text
/add_balance <telegram_id> <amount>
/remove_balance <telegram_id> <amount>
/user <telegram_id>
/service_disable <service_id>
```

## PasarGuard API

The client uses the public PasarGuard REST routes:

- `POST /api/admin/token`
- `POST /api/user`
- `GET /api/user/{username}`
- `PUT /api/user/{username}/disabled`
- `DELETE /api/user/{username}`
- `GET /api/user/{user_id}/subscription/{client_type}`

PasarGuard panel credentials are added from Telegram: `/admin` -> `Modiriate panelha` -> `Add PasarGuard panel`.

## Wallet lifecycle and verification

- Every eligible service for a customer is settled before deciding whether to disable all their active paid services. Test accounts are excluded.
- A negative wallet is debt: a top-up first covers the debt. Wallet-disabled services reactivate only once the balance is strictly positive. Manual/admin blocks are not cleared by top-ups.
- Failed disconnects/reactivations are retried by the billing scheduler even if no new traffic is reported. Telegram delivery failures do not roll back billing or deposits.
- Settlement uses one transaction and a PostgreSQL user-row lock per customer; wallet changes use atomic SQL updates. Payment approval locks its receipt to prevent duplicate credits.
- Traffic is rounded down to whole MiB, with the fractional remainder included on a later poll. The per-interval cost is rounded up to a whole Toman using 1024 MiB per GiB. Repeated polls at the same counter do not charge again.
- A backwards or invalid panel counter raises an error for reconciliation rather than silently writing zero or inventing a charge. Do not reset panel usage counters without reconciling the bot baseline.
- Disconnects are polling-based, not an instantaneous spending cap: the default detection delay is up to about a minute, plus panel/network processing. A panel outage can extend this delay.

Run isolated regression tests (no production panel calls or customer data):

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

The tests execute the production ORM/services against temporary in-memory SQLite and simulate panel/Telegram transport. They cover consumption, negative/zero balances, multiple services, top-ups, reactivation retries, counter resets, custom prices, cashback and cleanup. PostgreSQL locking and real device disconnect/reconnect require verification on the deployed server; SQLite tests do not prove those behaviors.
