"""
Tests de multi-dominio (domain_service + contexto de dominio del deployer).

Cubren las tres propiedades que hacen que un segundo dominio funcione y no
rompa el primero:
  1. La resolucion cae en cascada app -> default -> instalador.
  2. Provisionar un dominio AGREGA reglas al tunel; jamas pisa las existentes.
  3. El conteo de apps del dominio default incluye las apps sin domain_id.

Standalone: py tests/test_domain_service.py
"""
import asyncio
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# app.db arrastra motor (driver de Mongo), que no es dependencia de pruebas:
# el resto de la suite tambien corre sin el. get_db se mockea en cada test.
if "app.db" not in sys.modules:
    _db_stub = types.ModuleType("app.db")
    _db_stub.get_db = lambda: None
    sys.modules["app.db"] = _db_stub

# bson viaja con pymongo, que tampoco es dependencia de pruebas. El stub basta:
# lo unico que necesitan estos tests es que un id valido no haga match con los
# documentos falsos, que es justo el caso del dominio borrado.
if "bson" not in sys.modules:
    _bson_stub = types.ModuleType("bson")
    _bson_stub.ObjectId = lambda value: f"oid:{value}"
    _errors_stub = types.ModuleType("bson.errors")

    class _InvalidId(Exception):
        pass

    _bson_stub.errors = _errors_stub
    _errors_stub.InvalidId = _InvalidId
    sys.modules["bson"] = _bson_stub
    sys.modules["bson.errors"] = _errors_stub

from app.services import domain_service as ds  # noqa: E402


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.updates = []

    async def find_one(self, query, *a, **kw):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    async def update_one(self, query, update, *a, **kw):
        self.updates.append((query, update))

    async def count_documents(self, query):
        self.last_count_query = query
        return len(self.docs)


class FakeDB:
    def __init__(self, domains=None, system_config=None, apps=None):
        self.domains = FakeCollection(domains)
        self.system_config = FakeCollection(system_config)
        self.apps = FakeCollection(apps)


def run(coro):
    return asyncio.run(coro)


CONFIG = [{
    "_id": "main",
    "domain": "instalacion.com",
    "cloudflare_zone_id": "zone-default",
    "cloudflare_tunnel_id": "tunnel-1",
    "cloudflare_token": "tok",
    "cloudflare_account_id": "acct",
}]


class ResolveTests(unittest.TestCase):
    def test_falls_back_to_system_config_when_no_domains(self):
        """Instalacion anterior a multi-dominio: la coleccion `domains` esta vacia."""
        db = FakeDB(domains=[], system_config=CONFIG)
        with mock.patch.object(ds, "get_db", return_value=db):
            got = run(ds.resolve_for_app({"name": "app"}))
        self.assertEqual(got["fqdn"], "instalacion.com")
        self.assertEqual(got["source"], "system_config")

    def test_app_without_domain_id_uses_default_domain(self):
        db = FakeDB(
            domains=[{"_id": "d1", "fqdn": "default.com", "is_default": True}],
            system_config=CONFIG,
        )
        with mock.patch.object(ds, "get_db", return_value=db):
            got = run(ds.resolve_for_app({"name": "app"}))
        self.assertEqual(got["fqdn"], "default.com")
        self.assertEqual(got["source"], "default")

    def test_missing_domain_falls_back_instead_of_deploying_to_nothing(self):
        """Una app que apunta a un dominio borrado cae al default, no explota."""
        db = FakeDB(
            domains=[{"_id": "d1", "fqdn": "default.com", "is_default": True}],
            system_config=CONFIG,
        )
        with mock.patch.object(ds, "get_db", return_value=db):
            got = run(ds.resolve_for_app({"name": "app", "domain_id": "507f1f77bcf86cd799439011"}))
        self.assertEqual(got["fqdn"], "default.com")


class CountAppsTests(unittest.TestCase):
    def test_default_domain_counts_apps_without_domain_id(self):
        """Borrar el default sin contar las apps legacy las dejaria huerfanas."""
        db = FakeDB(apps=[])
        with mock.patch.object(ds, "get_db", return_value=db):
            run(ds.count_apps_using("d1", is_default=True))
        clauses = db.apps.last_count_query["$or"]
        self.assertIn({"domain_id": None}, clauses)
        self.assertIn({"domain_id": {"$exists": False}}, clauses)

    def test_non_default_domain_counts_only_explicit_references(self):
        db = FakeDB(apps=[])
        with mock.patch.object(ds, "get_db", return_value=db):
            run(ds.count_apps_using("d2", is_default=False))
        self.assertEqual(db.apps.last_count_query, {"domain_id": "d2"})


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeClient:
    """Cliente httpx de mentira que registra los PUT al tunel."""

    def __init__(self, tunnel_ingress):
        self.tunnel_ingress = tunnel_ingress
        self.put_bodies = []
        self.posted = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kw):
        if "configurations" in url:
            return FakeResponse({"result": {"config": {"ingress": self.tunnel_ingress}}})
        if "dns_records" in url:
            return FakeResponse({"result": []})
        return FakeResponse({"result": []})

    async def put(self, url, **kw):
        self.put_bodies.append(kw.get("json"))
        return FakeResponse({"result": {}})

    async def post(self, url, **kw):
        self.posted.append(kw.get("json"))
        return FakeResponse({"result": {}})

    async def delete(self, url, **kw):
        return FakeResponse({"result": {}})


class ProvisionTests(unittest.TestCase):
    def _provision(self, existing_ingress):
        db = FakeDB(system_config=CONFIG)
        client = FakeClient(existing_ingress)
        with mock.patch.object(ds, "get_db", return_value=db), \
             mock.patch.object(ds.httpx, "AsyncClient", return_value=client):
            run(ds.provision("nuevo.com", zone_id="zone-nuevo", tunnel_id="tunnel-1"))
        return client

    def test_preserves_existing_domain_rules(self):
        """El bug que este test cierra: un PUT ciego borraria el dominio que ya sirve."""
        existing = [
            {"hostname": "argocd.instalacion.com", "service": "https://argocd"},
            {"hostname": "*.instalacion.com", "service": ds.TRAEFIK_SERVICE},
            {"service": "http_status:404"},
        ]
        client = self._provision(existing)
        ingress = client.put_bodies[0]["config"]["ingress"]
        hostnames = [r.get("hostname") for r in ingress]
        self.assertIn("argocd.instalacion.com", hostnames)
        self.assertIn("*.instalacion.com", hostnames)
        self.assertIn("*.nuevo.com", hostnames)
        self.assertIn("nuevo.com", hostnames)

    def test_catch_all_stays_last(self):
        """Cloudflare rechaza la config si la regla sin hostname no va al final."""
        existing = [
            {"hostname": "*.instalacion.com", "service": ds.TRAEFIK_SERVICE},
            {"service": "http_status:404"},
        ]
        client = self._provision(existing)
        ingress = client.put_bodies[0]["config"]["ingress"]
        self.assertIsNone(ingress[-1].get("hostname"))
        self.assertEqual(ingress[-1]["service"], "http_status:404")
        for rule in ingress[:-1]:
            self.assertIsNotNone(rule.get("hostname"))

    def test_is_idempotent(self):
        """Re-provisionar un dominio ya cableado no reescribe las reglas del tunel."""
        existing = [
            {"hostname": "*.nuevo.com", "service": ds.TRAEFIK_SERVICE},
            {"hostname": "nuevo.com", "service": ds.TRAEFIK_SERVICE},
            {"service": "http_status:404"},
        ]
        client = self._provision(existing)
        tunnel_puts = [b for b in client.put_bodies if "config" in (b or {})]
        self.assertEqual(tunnel_puts, [])


class VerifyTests(unittest.TestCase):
    def test_reports_missing_credentials_without_calling_cloudflare(self):
        db = FakeDB(system_config=[{"_id": "main", "domain": "x.com"}])
        with mock.patch.object(ds, "get_db", return_value=db):
            report = run(ds.verify("nuevo.com"))
        self.assertFalse(report["ok"])
        self.assertEqual(report["checks"][0]["id"], "credentials")
        self.assertEqual(report["checks"][0]["status"], "fail")

    def test_pending_zone_is_blocking_and_names_the_nameservers(self):
        db = FakeDB(system_config=CONFIG)
        client = FakeClient([])

        async def fake_get(url, **kw):
            if "/zones?" in url:
                return FakeResponse({"result": [{
                    "id": "zone-nuevo",
                    "status": "pending",
                    "account": {"id": "acct"},
                    "name_servers": ["ns1.cloudflare.com", "ns2.cloudflare.com"],
                }]})
            return FakeResponse({"result": {}})

        client.get = fake_get
        with mock.patch.object(ds, "get_db", return_value=db), \
             mock.patch.object(ds.httpx, "AsyncClient", return_value=client):
            report = run(ds.verify("nuevo.com", tunnel_id="tunnel-1"))

        self.assertFalse(report["ok"])
        zone_check = next(c for c in report["checks"] if c["id"] == "zone")
        self.assertEqual(zone_check["status"], "fail")
        self.assertIn("ns1.cloudflare.com", zone_check["detail"])


if __name__ == "__main__":
    unittest.main()
