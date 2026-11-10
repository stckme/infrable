from enum import Enum

import typer

from infrable import infra

app = typer.Typer(no_args_is_help=True)


def _create_switch_command(switch):
    env_options = sorted(switch.options)
    EnvOptions = Enum("EnvOptions", {opt: opt for opt in env_options})

    def main(
        value: EnvOptions = typer.Argument(None),
        options: bool = False,
    ):
        if options:
            for opt in env_options:
                print(opt)
            return

        if value is None:
            if val := switch():
                print(val)
        else:
            switch.set(value.value)

    return main


for name, switch in infra.switches.items():
    help = f"Get or set the value of the {name} switch."
    cmd = _create_switch_command(switch)
    app.command(name=name, help=help)(cmd)
