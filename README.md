# PasarGuard Telegram VPN Sales Bot

Production-oriented Aiogram 3 bot for selling PasarGuard-backed VPN/proxy services with wallet billing, admin controls, manual and crypto payments, referral cashback, and scheduled traffic charging.

## Features

- User menu: buy service, services, wallet, invite link, wallet charge, one-time 100MB/1 day test account, support.
- Service plans: Multi Smart and Multi Economy with admin-configurable per-GB pricing.
- Wallet rules: 50,000 Toman minimum only for new paid service creation; reactivation can happen with any positive wallet balance.
- Billing job: every 30 minutes reads PasarGuard usage, computes MB deltas, bills by MB, logs usage, warns on low balance, disables insufficient-balance services.
- Cleanup job: deletes services disabled for more than 48 hours.
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
