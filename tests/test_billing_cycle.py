"""Exercise real ORM transactions against an isolated in-memory database.

Only the panel and Telegram transports are simulated. No customer data is used.
SQLite does not validate PostgreSQL row/advisory locking behavior.
"""

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import BigInteger, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.db.models import Base, PaymentRequest, TrafficUsageLog, User, VpnService, WalletTransaction
from app.integrations.pasarguard import PasarGuardError
from app.jobs import billing
from app.services.payments import PaymentService


@compiles(BigInteger, "sqlite")
def sqlite_integer(element, compiler, **kwargs):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def sqlite_json(element, compiler, **kwargs):
    return "JSON"


class BillingCycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.bot = AsyncMock()
        self.panel = AsyncMock()
        self.usage = {"account1": 0, "account2": 0}

        async def total(username):
            value = self.usage[username]
            if isinstance(value, Exception):
                raise value
            return value

        self.panel.total_used_mb.side_effect = total
        self.catalog_patch = patch(
            "app.services.catalog.CatalogService.client_for_panel",
            AsyncMock(return_value=self.panel),
        )
        self.catalog_patch.start()
        self.resolve_patch = patch(
            "app.services.catalog.CatalogService.resolve_panel",
            AsyncMock(return_value=type("Panel", (), {"id": 1})()),
        )
        self.resolve_patch.start()
        self.session_patch = patch.object(billing, "SessionLocal", self.sessions)
        self.session_patch.start()
        async with self.sessions() as session:
            session.add(User(id=1, telegram_id=1001, wallet_balance_toman=20000))
            session.add(
                VpnService(
                    id=1,
                    user_id=1,
                    panel_id=1,
                    type="multi_smart",
                    status="active",
                    pasarguard_username="account1",
                    is_test=False,
                    last_traffic_mb=0,
                    total_billed_mb=0,
                )
            )
            await session.commit()

    async def asyncTearDown(self):
        self.session_patch.stop()
        self.resolve_patch.stop()
        self.catalog_patch.stop()
        await self.engine.dispose()

    async def change(self, model, key, **values):
        async with self.sessions() as session:
            row = await session.get(model, key)
            for name, value in values.items():
                setattr(row, name, value)
            await session.commit()

    async def state(self):
        async with self.sessions() as session:
            user = await session.get(User, 1)
            services = list(
                (await session.scalars(select(VpnService).order_by(VpnService.id))).all()
            )
            logs = list((await session.scalars(select(TrafficUsageLog))).all())
            txs = list((await session.scalars(select(WalletTransaction))).all())
            return user, services, logs, txs

    async def test_one_gib_costs_9000_and_repeated_sync_does_not_charge_twice(self):
        self.usage["account1"] = 1024
        await billing.sync_traffic_usage(self.bot)
        await billing.sync_traffic_usage(self.bot)
        user, services, logs, txs = await self.state()
        self.assertEqual(user.wallet_balance_toman, 11000)
        self.assertEqual(services[0].total_billed_mb, 1024)
        self.assertEqual(len(logs), 1)
        self.assertEqual([t.amount_toman for t in txs], [-9000])

    async def test_overdraft_disables_and_records_both_usage_and_wallet_transaction(self):
        await self.change(User, 1, wallet_balance_toman=500)
        self.usage["account1"] = 1024
        await billing.sync_traffic_usage(self.bot)
        user, services, logs, txs = await self.state()
        self.assertEqual(user.wallet_balance_toman, -8500)
        self.assertEqual(services[0].status, "disabled")
        self.assertEqual(services[0].disabled_reason, "wallet")
        self.panel.set_disabled.assert_awaited_with("account1", True)
        self.assertEqual(logs[0].cost_toman, -txs[0].amount_toman)

    async def test_exact_zero_disables(self):
        await self.change(User, 1, wallet_balance_toman=9000)
        self.usage["account1"] = 1024
        await billing.sync_traffic_usage(self.bot)
        user, services, _, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, 0)
        self.assertEqual(services[0].status, "disabled")

    async def test_existing_zero_balance_disables_even_without_new_usage(self):
        await self.change(User, 1, wallet_balance_toman=0)
        await billing.sync_traffic_usage(self.bot)
        _, services, _, _ = await self.state()
        self.assertEqual(services[0].status, "disabled")

    async def test_failed_disable_is_retried_without_charging_twice(self):
        await self.change(User, 1, wallet_balance_toman=500)
        self.usage["account1"] = 1024
        self.panel.set_disabled.side_effect = PasarGuardError("temporary outage")
        await billing.sync_traffic_usage(self.bot)
        self.panel.set_disabled.side_effect = None
        await billing.sync_traffic_usage(self.bot)
        user, services, logs, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, -8500)
        self.assertEqual(services[0].status, "disabled")
        self.assertEqual(len(logs), 1)
        self.assertEqual(self.panel.set_disabled.await_count, 2)

    async def test_telegram_failure_does_not_rollback_billing(self):
        await self.change(User, 1, wallet_balance_toman=500)
        self.usage["account1"] = 1024
        self.bot.send_message.side_effect = RuntimeError("Telegram unavailable")
        await billing.sync_traffic_usage(self.bot)
        user, services, logs, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, -8500)
        self.assertEqual(services[0].status, "disabled")
        self.assertEqual(len(logs), 1)

    async def test_multiple_services_are_all_charged_before_disable(self):
        await self.change(User, 1, wallet_balance_toman=500)
        async with self.sessions() as session:
            session.add(
                VpnService(
                    id=2,
                    user_id=1,
                    panel_id=1,
                    type="multi_smart",
                    status="active",
                    pasarguard_username="account2",
                    is_test=False,
                    last_traffic_mb=0,
                    total_billed_mb=0,
                )
            )
            await session.commit()
        self.usage.update(account1=1024, account2=2048)
        await billing.sync_traffic_usage(self.bot)
        user, services, logs, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, -26500)
        self.assertEqual(len(logs), 2)
        self.assertTrue(all(s.status == "disabled" for s in services))

    async def make_payment(self, amount):
        async with self.sessions() as session:
            payment = PaymentRequest(
                user_id=1, method="card", amount_toman=amount, status="waiting_receipt"
            )
            session.add(payment)
            await session.commit()
            return payment.id

    async def approve(self, payment_id):
        async with self.sessions() as session:
            payment = await session.get(PaymentRequest, payment_id)
            await PaymentService(session).approve(payment, bot=self.bot)
            await session.commit()

    async def test_partial_debt_payment_stays_disabled_then_positive_balance_reactivates(self):
        await self.change(User, 1, wallet_balance_toman=-8500)
        await self.change(
            VpnService,
            1,
            status="disabled",
            disabled_reason="wallet",
            disabled_at=datetime.now(UTC),
        )
        await self.approve(await self.make_payment(5000))
        user, services, _, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, -3500)
        self.assertEqual(services[0].status, "disabled")
        payment_id = await self.make_payment(10000)
        await self.approve(payment_id)
        await self.approve(payment_id)
        user, services, _, txs = await self.state()
        self.assertEqual(user.wallet_balance_toman, 6500)
        self.assertEqual(services[0].status, "active")
        self.assertIsNone(services[0].disabled_at)
        self.assertEqual(len(txs), 2)
        self.panel.set_disabled.assert_awaited_once_with("account1", False)

    async def test_clearing_debt_to_exact_zero_does_not_reactivate(self):
        await self.change(User, 1, wallet_balance_toman=-5000)
        await self.change(VpnService, 1, status="disabled", disabled_reason="wallet")
        await self.approve(await self.make_payment(5000))
        user, services, _, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, 0)
        self.assertEqual(services[0].status, "disabled")

    async def test_manual_disable_is_not_undone_by_topup(self):
        await self.change(VpnService, 1, status="disabled", disabled_reason="manual")
        await self.approve(await self.make_payment(10000))
        _, services, _, _ = await self.state()
        self.assertEqual(services[0].status, "disabled")
        self.panel.set_disabled.assert_not_awaited()

    async def test_blocked_user_is_not_reactivated_by_topup(self):
        await self.change(User, 1, is_blocked=True)
        await self.change(VpnService, 1, status="disabled", disabled_reason="wallet")
        await self.approve(await self.make_payment(10000))
        _, services, _, _ = await self.state()
        self.assertEqual(services[0].status, "disabled")

    async def test_failed_reactivation_is_retried_by_scheduler(self):
        await self.change(User, 1, wallet_balance_toman=-1000)
        await self.change(VpnService, 1, status="disabled", disabled_reason="wallet")
        self.panel.set_disabled.side_effect = PasarGuardError("temporary outage")
        await self.approve(await self.make_payment(10000))
        self.panel.set_disabled.side_effect = None
        await billing.sync_traffic_usage(self.bot)
        user, services, _, txs = await self.state()
        self.assertEqual(user.wallet_balance_toman, 9000)
        self.assertEqual(services[0].status, "active")
        self.assertEqual(len(txs), 1)

    async def test_tests_are_excluded_from_billing(self):
        await self.change(VpnService, 1, is_test=True)
        self.usage["account1"] = 1024
        await billing.sync_traffic_usage(self.bot)
        user, _, logs, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, 20000)
        self.assertEqual(logs, [])

    async def test_panel_outage_for_one_user_does_not_stop_other_users(self):
        async with self.sessions() as session:
            session.add(User(id=2, telegram_id=1002, wallet_balance_toman=20000))
            session.add(
                VpnService(
                    id=2,
                    user_id=2,
                    panel_id=1,
                    type="multi_smart",
                    status="active",
                    pasarguard_username="account2",
                    is_test=False,
                    last_traffic_mb=0,
                    total_billed_mb=0,
                )
            )
            await session.commit()
        self.usage.update(account1=PasarGuardError("outage"), account2=1024)
        await billing.sync_traffic_usage(self.bot)
        async with self.sessions() as session:
            self.assertEqual((await session.get(User, 2)).wallet_balance_toman, 11000)

    async def test_cleanup_only_deletes_old_wallet_disabled_services(self):
        await self.change(User, 1, wallet_balance_toman=0)
        await self.change(
            VpnService,
            1,
            status="disabled",
            disabled_reason="wallet",
            disabled_at=datetime.now(UTC) - timedelta(hours=49),
        )
        await billing.delete_stale_disabled_services(self.bot)
        _, services, _, _ = await self.state()
        self.assertEqual(services[0].status, "deleted")
        self.panel.delete_user.assert_awaited_once_with("account1")

    async def test_cleanup_preserves_manual_disable(self):
        await self.change(
            VpnService,
            1,
            status="disabled",
            disabled_reason="manual",
            disabled_at=datetime.now(UTC) - timedelta(hours=49),
        )
        await billing.delete_stale_disabled_services(self.bot)
        self.panel.delete_user.assert_not_awaited()

    async def test_cleanup_preserves_positive_wallet_when_reactivation_is_pending(self):
        await self.change(
            VpnService,
            1,
            status="disabled",
            disabled_reason="wallet",
            disabled_at=datetime.now(UTC) - timedelta(hours=49),
        )
        await billing.delete_stale_disabled_services(self.bot)
        self.panel.delete_user.assert_not_awaited()

    async def test_cleanup_preserves_recent_wallet_disable(self):
        await self.change(User, 1, wallet_balance_toman=0)
        await self.change(
            VpnService,
            1,
            status="disabled",
            disabled_reason="wallet",
            disabled_at=datetime.now(UTC) - timedelta(hours=1),
        )
        await billing.delete_stale_disabled_services(self.bot)
        self.panel.delete_user.assert_not_awaited()

    async def test_counter_reset_does_not_silently_discard_or_double_charge_usage(self):
        await self.change(VpnService, 1, last_traffic_mb=715, total_billed_mb=715)
        self.usage["account1"] = 10
        with self.assertLogs("app.jobs.billing", level="ERROR"):
            await billing.sync_traffic_usage(self.bot)
        user, services, logs, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, 20000)
        self.assertEqual(services[0].last_traffic_mb, 715)
        self.assertEqual(logs, [])

    async def test_consumption_reported_after_disconnect_is_still_billed(self):
        await self.change(User, 1, wallet_balance_toman=-1000)
        await self.change(
            VpnService,
            1,
            status="disabled",
            disabled_reason="wallet",
            last_traffic_mb=100,
            total_billed_mb=100,
        )
        self.usage["account1"] = 1124
        await billing.sync_traffic_usage(self.bot)
        user, services, logs, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, -10000)
        self.assertEqual(services[0].total_billed_mb, 1124)
        self.assertEqual(len(logs), 1)

    async def test_stale_wallet_snapshot_does_not_erase_another_credit(self):
        from app.db.models import TransactionKind
        from app.services.wallet import WalletService

        async with self.sessions() as first, self.sessions() as second:
            stale = await first.get(User, 1)
            fresh = await second.get(User, 1)
            await WalletService(second).add(fresh, 5000, TransactionKind.deposit, "topup")
            await second.commit()
            await WalletService(first).deduct(stale, 9000, "usage", allow_negative=True)
            await first.commit()
        user, _, _, txs = await self.state()
        self.assertEqual(user.wallet_balance_toman, 16000)
        self.assertEqual(sum(t.amount_toman for t in txs), -4000)

    async def test_topup_is_saved_even_when_reactivation_notification_fails(self):
        await self.change(User, 1, wallet_balance_toman=-1000)
        await self.change(VpnService, 1, status="disabled", disabled_reason="wallet")
        self.bot.send_message.side_effect = RuntimeError("blocked bot")
        await self.approve(await self.make_payment(10000))
        user, services, _, txs = await self.state()
        self.assertEqual(user.wallet_balance_toman, 9000)
        self.assertEqual(services[0].status, "active")
        self.assertEqual(len(txs), 1)

    async def test_rejected_payment_cannot_be_credited(self):
        payment_id = await self.make_payment(10000)
        await self.change(PaymentRequest, payment_id, status="rejected")
        with self.assertRaises(ValueError):
            await self.approve(payment_id)
        user, _, _, txs = await self.state()
        self.assertEqual(user.wallet_balance_toman, 20000)
        self.assertEqual(txs, [])

    async def test_later_handler_failure_does_not_undo_approved_deposit(self):
        payment_id = await self.make_payment(10000)
        async with self.sessions() as session:
            payment = await session.get(PaymentRequest, payment_id)
            await PaymentService(session).approve(payment, bot=self.bot)
            # Model a failed confirmation and the middleware rollback afterward.
            await session.rollback()
        user, _, _, txs = await self.state()
        self.assertEqual(user.wallet_balance_toman, 30000)
        self.assertEqual(len(txs), 1)

    async def test_full_consumption_debt_topup_reconnect_and_consume_again(self):
        await self.change(User, 1, wallet_balance_toman=500)
        self.usage["account1"] = 1024
        await billing.sync_traffic_usage(self.bot)
        await self.approve(await self.make_payment(10000))
        self.usage["account1"] = 1124
        await billing.sync_traffic_usage(self.bot)
        await billing.sync_traffic_usage(self.bot)
        user, services, logs, txs = await self.state()
        self.assertEqual(user.wallet_balance_toman, 1500 - billing.cost_for_mb(100, 9000))
        self.assertEqual(services[0].status, "active")
        self.assertEqual(services[0].total_billed_mb, 1124)
        self.assertEqual(len(logs), 2)
        self.assertEqual(sum(t.amount_toman for t in txs), user.wallet_balance_toman - 500)

    async def test_economy_rate_is_applied(self):
        await self.change(VpnService, 1, type="multi_economy")
        self.usage["account1"] = 1024
        await billing.sync_traffic_usage(self.bot)
        user, _, logs, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, 18000)
        self.assertEqual(logs[0].cost_toman, 2000)

    async def test_custom_plan_rate_overrides_default(self):
        from app.db.models import ProductPlan

        async with self.sessions() as session:
            session.add(ProductPlan(id=1, name="custom", price_per_gb_toman=12345, is_active=True))
            await session.commit()
        await self.change(VpnService, 1, plan_id=1)
        self.usage["account1"] = 1024
        await billing.sync_traffic_usage(self.bot)
        user, _, logs, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, 7655)
        self.assertEqual(logs[0].cost_toman, 12345)

    async def test_cashback_matches_traffic_charge_and_is_not_duplicated(self):
        from app.db.models import Setting

        async with self.sessions() as session:
            session.add(User(id=2, telegram_id=1002, wallet_balance_toman=0))
            session.add(Setting(key="referral_cashback_percent", value="10", encrypted=False))
            await session.commit()
        await self.change(User, 1, referred_by_id=2)
        self.usage["account1"] = 1024
        await billing.sync_traffic_usage(self.bot)
        await billing.sync_traffic_usage(self.bot)
        async with self.sessions() as session:
            inviter = await session.get(User, 2)
            self.assertEqual(inviter.wallet_balance_toman, 900)

    async def test_low_balance_warning_does_not_disable_positive_wallet(self):
        self.usage["account1"] = 1536
        await billing.sync_traffic_usage(self.bot)
        user, services, _, _ = await self.state()
        self.assertEqual(user.wallet_balance_toman, 6500)
        self.assertEqual(services[0].status, "active")
        self.assertTrue(
            any("کم است" in call.args[1] for call in self.bot.send_message.await_args_list)
        )

    async def test_failed_cutoff_is_counted_as_sync_failure(self):
        await self.change(User, 1, wallet_balance_toman=0)
        self.panel.set_disabled.side_effect = PasarGuardError("outage")
        with self.assertLogs("app.jobs.billing", level="INFO") as logs:
            await billing.sync_traffic_usage(self.bot)
        self.assertTrue(any("failed=1" in line for line in logs.output))
