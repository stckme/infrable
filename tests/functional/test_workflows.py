from sh import infrable


def test_workflows():
    assert "[WORKFLOW] Deploy nginx files" in infrable.deploy.nginx("--help")
