def pytest_configure(config):
    from infrable import init

    init.init()

    from infrable import infra

    infra.switches["env"].set("dev")
