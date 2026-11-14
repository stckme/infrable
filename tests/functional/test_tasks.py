from sh import infrable


def test_tasks():
    assert "[TASK] Reload nginx" in infrable.nginx.reload("--help")
