from dataclasses import replace

from infrable import Host, Meta, Service


def test_host_str_prefers_fqdn():
    assert str(Host(ip="1.1.1.1", fqdn="a.example.com")) == "root@a.example.com"
    assert str(Host(ip="1.1.1.1", admin="bob")) == "bob@1.1.1.1"


def test_host_remote_command():
    cmd = Host(ip="1.1.1.1").remote()
    assert str(cmd).endswith("ssh root@1.1.1.1 -o StrictHostKeyChecking=no")


def test_host_remote_login_override():
    cmd = Host(ip="1.1.1.1", admin="root").remote("bob")
    assert "bob@1.1.1.1" in str(cmd)
    assert "root@" not in str(cmd)


def test_host_remote_ssh_key():
    cmd = Host(ip="1.1.1.1", admin_ssh_key="/keys/id").remote()
    assert str(cmd).endswith("-o StrictHostKeyChecking=no -i /keys/id")


def test_host_format():
    host = Host(ip="1.1.1.1", fqdn="a.example.com")
    assert host.format("web", "{name},{ip},{fqdn},{admin}") == (
        "web,1.1.1.1,a.example.com,root"
    )
    # missing values render as empty strings
    assert Host(ip="1.1.1.1").format("web", "{name}|{fqdn}|") == "web||"


def test_host_equality_hash_and_order():
    a = Host(ip="1.1.1.1")
    assert a == Host(ip="1.1.1.1")
    assert a != Host(ip="1.1.1.2")
    assert len({a, Host(ip="1.1.1.1"), Host(ip="1.1.1.2")}) == 2
    assert a < Host(ip="1.1.1.2")
    assert replace(a, admin="bob") != a


def test_host_meta_is_hashable():
    a = Host(ip="1.1.1.1", meta=Meta(role="web"))
    assert a.meta.role == "web"
    assert hash(a) == hash(Host(ip="1.1.1.1", meta=Meta(role="web")))


def test_meta_hash_ignores_insertion_order():
    assert hash(Meta(a=1, b=2)) == hash(Meta(b=2, a=1))
    assert hash(Meta(a=1)) != hash(Meta(a=2))


def test_service_str():
    host = Host(ip="1.1.1.1", fqdn="a.example.com")
    assert str(Service(host=host, port=80)) == "root@a.example.com:80"
    assert str(Service()) == ":"


def test_service_format():
    host = Host(ip="1.1.1.1")
    svc = Service(host=host, port=80)
    assert svc.format("web", "{name},{host.ip},{port}") == "web,1.1.1.1,80"
    assert Service().format("web", "{name}:{port}") == "web:"
