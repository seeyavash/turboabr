import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientConnectionError

from app.core.config import Settings
from app.integrations.pasarguard import CachedToken, PasarGuardClient, PasarGuardError
from app.jobs.scheduler import build_scheduler
from app.services.catalog import CatalogService


class PanelContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_mb_conversion_and_explicit_zero_do_not_switch_counter(self):
        client = PasarGuardClient()
        client.get_user = AsyncMock(
            return_value={"used_traffic": 750440319, "lifetime_used_traffic": 750440319}
        )
        self.assertEqual(await client.total_used_mb("test"), 715)
        client.get_user.return_value = {"used_traffic": 0, "lifetime_used_traffic": 999999999}
        self.assertEqual(await client.total_used_mb("test"), 0)

    async def test_missing_or_invalid_counter_is_an_error_not_zero_usage(self):
        client = PasarGuardClient()
        client.get_user = AsyncMock()
        for data in ({}, {"used_traffic": -1}, {"used_traffic": "invalid"}, {"used_traffic": True}):
            with self.subTest(data=data):
                client.get_user.return_value = data
                with self.assertRaises(PasarGuardError):
                    await client.total_used_mb("test")

    async def test_disable_and_enable_use_explicit_idempotent_flag(self):
        client = PasarGuardClient()
        client._request = AsyncMock(return_value={"status": "disabled"})
        await client.set_disabled("test", True)
        client._request.assert_awaited_with(
            "PUT", "/api/user/test/disabled", json={"disabled": True}
        )
        client._request.return_value = {"status": "active"}
        await client.set_disabled("test", False)
        client._request.assert_awaited_with(
            "PUT", "/api/user/test/disabled", json={"disabled": False}
        )

    async def test_network_failure_is_normalized_for_retry(self):
        client = PasarGuardClient(base_url="https://test.invalid")
        client.token = AsyncMock(return_value="test-token")
        context = MagicMock()
        context.__aenter__ = AsyncMock(side_effect=ClientConnectionError("offline"))
        with (
            patch("app.integrations.pasarguard.ClientSession", return_value=context),
            self.assertRaises(PasarGuardError),
        ):
            await client.get_user("test")

    async def test_expired_token_is_refreshed_once(self):
        client = PasarGuardClient(base_url="https://test.invalid", username="test")
        client._token_cache[client.cache_key] = CachedToken(
            "old", datetime.now(UTC) + timedelta(hours=1)
        )
        responses = []
        for status, data in [
            (401, {}),
            (200, {"access_token": "new"}),
            (200, {"used_traffic": 123}),
        ]:
            response = MagicMock(status=status, headers={"content-type": "application/json"})
            response.text = AsyncMock(return_value="{}")
            response.json = AsyncMock(return_value=data)
            response.__aenter__ = AsyncMock(return_value=response)
            response.__aexit__ = AsyncMock(return_value=False)
            responses.append(response)
        http = MagicMock()
        http.request.side_effect = responses
        http.__aenter__ = AsyncMock(return_value=http)
        http.__aexit__ = AsyncMock(return_value=False)
        with patch("app.integrations.pasarguard.ClientSession", return_value=http):
            self.assertEqual(await client.get_user("test"), {"used_traffic": 123})
        self.assertEqual(http.request.call_count, 3)
        self.assertEqual(client._token_cache[client.cache_key].value, "new")
        client._token_cache.clear()

    async def test_ambiguous_legacy_panel_is_not_selected_arbitrarily(self):
        catalog = CatalogService(AsyncMock())
        catalog.active_panels = AsyncMock(
            return_value=[SimpleNamespace(id=1), SimpleNamespace(id=2)]
        )
        with self.assertRaises(PasarGuardError):
            await catalog.resolve_panel(None)
        catalog.active_panels.return_value = [SimpleNamespace(id=1)]
        self.assertEqual((await catalog.resolve_panel(None)).id, 1)

    async def test_missing_explicit_panel_is_not_reassigned(self):
        session = AsyncMock()
        session.get.return_value = None
        catalog = CatalogService(session)
        with self.assertRaises(PasarGuardError):
            await catalog.resolve_panel(99)

    async def test_scheduler_checks_credit_every_minute_without_overlapping_itself(self):
        scheduler = build_scheduler(AsyncMock())
        job = scheduler.get_job("traffic-sync")
        self.assertEqual(job.trigger.interval.total_seconds(), 60)
        self.assertEqual(job.max_instances, 1)

    async def test_admin_id_configuration_accepts_empty_csv_and_json(self):
        for raw, expected in [("", []), ("1,2", [1, 2]), ("[1,2]", [1, 2])]:
            with self.subTest(raw=raw), patch.dict("os.environ", ENV_ADMIN_IDS=raw):
                self.assertEqual(Settings(_env_file=None).env_admin_ids, expected)
