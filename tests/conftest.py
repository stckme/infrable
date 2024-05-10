from sh import infrable


def pytest_configure(config):
    infrable.init()
    infrable.env.dev()
