"""
Tests de procedencia y deteccion de actualizaciones del core (ADR-002).

Las tres propiedades que evitan que una celula se quede atras en silencio o
pise un cambio local:
  1. Sin procedencia registrada NO se reporta "al dia".
  2. La deriva bloquea el upgrade en vez de descartar lo local.
  3. Los pre-release solo aparecen en el canal dev.

Standalone: py tests/test_core_release.py
"""
import asyncio
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if "app.db" not in sys.modules:
    _db_stub = types.ModuleType("app.db")
    _db_stub.get_db = lambda: None
    sys.modules["app.db"] = _db_stub

from app.services import core_release as cr  # noqa: E402


class FakeCollection:
    def __init__(self, doc=None):
        self.doc = doc
        self.updates = []

    async def find_one(self, *a, **kw):
        return dict(self.doc) if self.doc else None

    async def update_one(self, query, update, **kw):
        self.updates.append(update)


class FakeDB:
    def __init__(self, config=None):
        self.system_config = FakeCollection(config)


def run(coro):
    return asyncio.run(coro)


CONFIG_WITH_PROVENANCE = {
    "_id": "main",
    "github_org": "ProyectosUniUAEH",
    "github_token": "tok",
    "core_release": {
        "version": "v1.0.0",
        "channel": "stable",
        "upstream_sha": "aaaaaaa",
        "components": {
            "kaanbal-api": {"repo_sha": "sha-api", "tag": "v1.0.0"},
            "kaanbal-console": {"repo_sha": "sha-console", "tag": "v1.0.0"},
            "kaanbal-agent": {"repo_sha": "sha-agent", "tag": "v1.0.0"},
        },
    },
}

RELEASES = [
    {"version": "v1.2.0", "name": "v1.2.0", "notes": "multi-dominio",
     "prerelease": False, "published_at": "2026-09-09", "url": "u"},
    {"version": "v1.1.0-rc1", "name": "rc", "notes": "",
     "prerelease": True, "published_at": "2026-09-05", "url": "u"},
    {"version": "v1.0.0", "name": "v1.0.0", "notes": "",
     "prerelease": False, "published_at": "2026-09-01", "url": "u"},
]


class ProvenanceTests(unittest.TestCase):
    def test_missing_provenance_is_reported_as_unknown(self):
        """Inventar una version haria que la celula se creyera al dia para siempre."""
        db = FakeDB({"_id": "main"})
        with mock.patch.object(cr, "get_db", return_value=db):
            got = run(cr.read_provenance())
        self.assertFalse(got["known"])
        self.assertEqual(got["version"], "unknown")
        self.assertIn("procedencia", got["reason"])

    def test_records_provenance(self):
        db = FakeDB({"_id": "main"})
        with mock.patch.object(cr, "get_db", return_value=db):
            run(cr.write_provenance(
                version="v1.2.0", upstream_sha="df8cb6e",
                components={"kaanbal-api": {"tag": "v1.2.0"}},
            ))
        written = db.system_config.updates[0]["$set"]["core_release"]
        self.assertEqual(written["version"], "v1.2.0")
        self.assertEqual(written["channel"], "stable")


class CheckUpdatesTests(unittest.TestCase):
    def _check(self, config, releases, drift):
        db = FakeDB(config)
        with mock.patch.object(cr, "get_db", return_value=db), \
             mock.patch.object(cr, "list_releases", new=mock.AsyncMock(return_value=releases)), \
             mock.patch.object(cr, "detect_drift", new=mock.AsyncMock(return_value=drift)):
            return run(cr.check_updates())

    def test_offers_update_when_behind(self):
        got = self._check(CONFIG_WITH_PROVENANCE, RELEASES, {"detectable": True, "any_custom": False})
        self.assertTrue(got["update_available"])
        self.assertEqual(got["latest"]["version"], "v1.2.0")

    def test_prereleases_hidden_on_stable_channel(self):
        """v1.1.0-rc1 no debe ofrecerse a una celula en stable."""
        got = self._check(CONFIG_WITH_PROVENANCE, RELEASES, {"detectable": True, "any_custom": False})
        versions = [r["version"] for r in got["pending_releases"]]
        self.assertNotIn("v1.1.0-rc1", versions)
        self.assertIn("v1.2.0", versions)

    def _check_dev(self, upstream):
        config = dict(CONFIG_WITH_PROVENANCE)
        config["core_release"] = {**CONFIG_WITH_PROVENANCE["core_release"], "channel": "dev"}
        db = FakeDB(config)
        with mock.patch.object(cr, "get_db", return_value=db), \
             mock.patch.object(cr, "upstream_commits", new=mock.AsyncMock(return_value=upstream)), \
             mock.patch.object(cr, "detect_drift", new=mock.AsyncMock(return_value={"any_custom": False})):
            return run(cr.check_updates())

    def test_dev_channel_offers_upgrade_for_engine_commits(self):
        """El flujo del autor: un commit al monorepo aparece como upgrade en su célula."""
        got = self._check_dev({"available": True, "head_sha": "bbbbbbbcafe", "ahead_by": 2,
                               "commits": [{"sha": "b"}, {"sha": "c"}],
                               "components": ["kaanbal-api"], "touches_engine": True})
        self.assertEqual(got["tracking"], "commits")
        self.assertTrue(got["update_available"])
        self.assertEqual(got["latest"]["version"], "dev-bbbbbbb")

    def test_dev_channel_ignores_commits_that_only_touch_docs(self):
        got = self._check_dev({"available": True, "head_sha": "ddddddd", "ahead_by": 1,
                               "commits": [{"sha": "d"}], "components": [], "touches_engine": False})
        self.assertFalse(got["update_available"])

    def test_dev_channel_without_github_does_not_claim_an_update(self):
        got = self._check_dev({"available": False, "reason": "Sin conexión con GitHub"})
        self.assertFalse(got["update_available"])

    def test_up_to_date_cell_gets_no_update(self):
        config = dict(CONFIG_WITH_PROVENANCE)
        config["core_release"] = {**CONFIG_WITH_PROVENANCE["core_release"], "version": "v1.2.0"}
        got = self._check(config, RELEASES, {"detectable": True, "any_custom": False})
        self.assertFalse(got["update_available"])

    def test_unknown_provenance_still_offers_latest(self):
        """Fijar la procedencia es justo lo que resuelve aplicar una release."""
        got = self._check({"_id": "main"}, RELEASES, {"detectable": False, "components": {}})
        self.assertTrue(got["update_available"])

    def test_drift_blocks_the_upgrade(self):
        """Un componente tuneado no debe pisarse en silencio."""
        drift = {"detectable": True, "any_custom": True,
                 "components": {"kaanbal-api": {"custom": True}}}
        got = self._check(CONFIG_WITH_PROVENANCE, RELEASES, drift)
        self.assertTrue(got["update_available"])
        self.assertTrue(got["blocked_by_drift"])


class ComponentMappingTests(unittest.TestCase):
    def test_maps_engine_paths_to_components(self):
        self.assertEqual(cr._component_of("SOFTWARE_FACTORY/kaanbal-api/app/main.py"), "kaanbal-api")
        self.assertEqual(cr._component_of("SOFTWARE_FACTORY/installer/server.py"), "installer")
        self.assertEqual(cr._component_of("SOFTWARE_FACTORY/infra-gitops/apps/x.yaml"), "infra-gitops")

    def test_docs_and_env_are_not_engine(self):
        for path in ("docs/adr/002.md", "README.md", ".gitignore", "SOFTWARE_FACTORY/BLUEPRINT.md"):
            self.assertIsNone(cr._component_of(path), path)


def _commit(sha, message):
    return {"sha": sha, "commit": {"message": message}}


class ForeignCommitsTests(unittest.TestCase):
    def test_interrupted_upgrade_is_not_drift(self):
        """El falso positivo de pam: el upgrade sincronizó y se cortó antes de
        registrar la procedencia. HEAD es un commit propio, no un cambio a mano."""
        commits = [
            _commit("13b139d", "upgrade: sync desde software-factory@3f4833a [skip ci]"),
            _commit("94595b1", "upgrade: sync desde software-factory@f86b784 [skip ci]"),
            _commit("dce46db", "bootstrap: kaanbal-api publicado por el instalador"),
        ]
        self.assertEqual(cr.foreign_commits(commits), [])

    def test_manual_commit_on_top_is_drift(self):
        commits = [
            _commit("aaa1111", "feat: tuneo local del deployer"),
            _commit("13b139d", "upgrade: sync desde software-factory@3f4833a"),
        ]
        foreign = cr.foreign_commits(commits)
        self.assertEqual([c["sha"] for c in foreign], ["aaa1111"])

    def test_history_without_kaanbal_commits_is_drift(self):
        foreign = cr.foreign_commits([_commit("zzz", "initial commit")])
        self.assertTrue(foreign)


class DriftTests(unittest.TestCase):
    def test_not_detectable_without_provenance(self):
        db = FakeDB({"_id": "main", "github_org": "org", "github_token": "t"})
        with mock.patch.object(cr, "get_db", return_value=db):
            got = run(cr.detect_drift())
        self.assertFalse(got["detectable"])

    def test_not_detectable_without_credentials(self):
        db = FakeDB({"_id": "main"})
        with mock.patch.object(cr, "get_db", return_value=db):
            got = run(cr.detect_drift())
        self.assertFalse(got["detectable"])


if __name__ == "__main__":
    unittest.main()
