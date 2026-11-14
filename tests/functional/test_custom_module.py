from sh import infrable


def test_custom_module():
    assert "[WORKFLOW] Provision Ubuntu host" in infrable.cloud(
        "provision-ubuntu-host", "--help"
    )
