"""Tests for how `infrable.infra` loads a project's `infra.py`.

Loading happens once at import time, so each scenario runs in a fresh
interpreter inside a scratch project directory.
"""

import json
import subprocess as sp
import sys
import textwrap

from infrable import errors

PROBE = """
import json
from infrable import infra
print(json.dumps({
    "hosts": sorted(infra.hosts),
    "services": sorted(infra.services),
    "switches": sorted(infra.switches),
    "typers": sorted(infra.typers),
    "metas": sorted(infra.metas),
    "host_groups": sorted(infra.host_groups),
    "by_ip": sorted(infra.by_ip),
    "by_fqdn": sorted(infra.by_fqdn),
}))
"""


def load(tmp_path, infra_py=None, probe=PROBE):
    if infra_py is not None:
        (tmp_path / "infra.py").write_text(textwrap.dedent(infra_py))
    return sp.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


def loaded(tmp_path, infra_py, probe=PROBE):
    result = load(tmp_path, infra_py, probe)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_missing_infra_py(tmp_path):
    result = load(tmp_path)

    assert result.returncode != 0
    assert errors.InfraDotPyNotFoundError.__name__ in result.stderr
    assert "infra.py: file not found" in result.stderr


def test_duplicate_ip(tmp_path):
    result = load(
        tmp_path,
        """
        from infrable import Host
        a = Host(ip="1.1.1.1")
        b = Host(ip="1.1.1.1")
        """,
    )

    assert result.returncode != 0
    assert "DuplicateIPError: Duplicate IP: 1.1.1.1" in result.stderr


def test_duplicate_fqdn(tmp_path):
    result = load(
        tmp_path,
        """
        from infrable import Host
        a = Host(ip="1.1.1.1", fqdn="a.example.com")
        b = Host(ip="1.1.1.2", fqdn="a.example.com")
        """,
    )

    assert result.returncode != 0
    assert "DuplicateFQDNError" in result.stderr
    assert "a.example.com" in result.stderr


def test_private_names_are_skipped(tmp_path):
    result = loaded(
        tmp_path,
        """
        from infrable import Host
        _private = Host(ip="1.1.1.1")
        public = Host(ip="1.1.1.2")
        """,
    )

    assert result["hosts"] == ["public"]


def test_everything_is_classified(tmp_path):
    result = loaded(
        tmp_path,
        """
        import typer
        from infrable import Host, Meta, Service, Switch

        host_typer = typer.Typer()
        host = Host(ip="1.1.1.1", fqdn="a.example.com", typer=host_typer)
        other = Host(ip="1.1.1.2")

        service_typer = typer.Typer()
        service = Service(host=host, port=80, typer=service_typer)
        plain_service = Service()

        switch_typer = typer.Typer()
        env = Switch({"dev", "prod"}, init="dev", typer=switch_typer)
        plain_switch = Switch({"x", "y"}, init="x")

        meta = Meta(a=1)
        meta_with_typer = Meta(typer=typer.Typer())

        bare_typer = typer.Typer()

        class Custom:
            typer = typer.Typer()

        custom = Custom()

        class NotATyper:
            typer = "nope"

        not_a_typer = NotATyper()

        group = [host, other]
        empty_list = []
        number = 1
        """,
    )

    assert result["hosts"] == ["host", "other"]
    assert result["services"] == ["plain_service", "service"]
    assert result["switches"] == ["env", "plain_switch"]
    assert result["metas"] == ["meta", "meta_with_typer"]
    assert result["host_groups"] == ["group"]
    assert result["by_ip"] == ["1.1.1.1", "1.1.1.2"]
    assert result["by_fqdn"] == ["a.example.com"]
    assert {"host", "service", "env", "bare_typer", "custom", "meta_with_typer"} <= set(
        result["typers"]
    )
    assert "meta" not in result["typers"]
    assert "not_a_typer" not in result["typers"]
    assert "plain_switch" not in result["typers"]


def test_item_types_include_base_classes(tmp_path):
    result = loaded(
        tmp_path,
        """
        from dataclasses import dataclass
        from infrable import Host

        @dataclass
        class MyHost(Host):
            pass

        mine = MyHost(ip="1.1.1.1")
        """,
        probe="""
import json
from infrable import Host, infra
from infra import MyHost
print(json.dumps({
    "own": sorted(infra.item_types[MyHost]),
    "base": sorted(infra.item_types[Host]),
    "hosts": sorted(infra.hosts),
}))
""",
    )

    assert result == {"own": ["mine"], "base": ["mine"], "hosts": ["mine"]}


LOOKUP_INFRA = """
from infrable import Host, Service
dev = Host(ip="1.1.1.1", fqdn="dev.example.com")
beta = Host(ip="1.1.1.2", fqdn="beta.example.com")
prod = Host(ip="1.1.1.3")
web = Service(host=dev, port=80)
orphan = Service(port=80)
group = [dev, beta]
"""

LOOKUP_PROBE = """
import json
from infrable import errors, infra

def names(hosts):
    return [h.ip for h in hosts]

out = {
    "get_by_name": infra.get_host("dev").ip,
    "get_by_fqdn": infra.get_host("beta.example.com").ip,
    "get_by_ip": infra.get_host("1.1.1.3").ip,
    "get_by_service": infra.get_host("web").ip,
    "get_orphan_service": infra.get_host("orphan"),
    "get_missing": infra.get_host("missing"),
    "all": names(infra.filtered_hosts()),
    "empty_only": names(infra.filtered_hosts(only=[])),
    "by_name": names(infra.filtered_hosts(only=["prod"])),
    "by_service": names(infra.filtered_hosts(only=["web"])),
    "by_group": names(infra.filtered_hosts(only=["group"])),
    "mixed": names(infra.filtered_hosts(only=["prod", "group", "beta.example.com"])),
}
try:
    infra.filtered_hosts(only=["nope"])
except errors.HostOrServiceNotFoundError as e:
    out["error"] = str(e)
print(json.dumps(out))
"""


def test_host_lookup_and_filtering(tmp_path):
    result = loaded(tmp_path, LOOKUP_INFRA, probe=LOOKUP_PROBE)

    assert result == {
        "get_by_name": "1.1.1.1",
        "get_by_fqdn": "1.1.1.2",
        "get_by_ip": "1.1.1.3",
        "get_by_service": "1.1.1.1",
        "get_orphan_service": None,
        "get_missing": None,
        # hosts load in alphabetical name order: beta, dev, prod
        "all": ["1.1.1.2", "1.1.1.1", "1.1.1.3"],
        "empty_only": ["1.1.1.2", "1.1.1.1", "1.1.1.3"],
        "by_name": ["1.1.1.3"],
        "by_service": ["1.1.1.1"],
        "by_group": ["1.1.1.1", "1.1.1.2"],
        "mixed": ["1.1.1.3", "1.1.1.1", "1.1.1.2", "1.1.1.2"],
        "error": "'nope: host or service not found'",
    }
