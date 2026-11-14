import pytest

from infrable import errors


@pytest.mark.parametrize(
    "error, base, message",
    [
        (errors.FQDNMustNotBeEmptyError(), ValueError, "FQDN must not be empty"),
        (
            errors.MissingMetadataError("a.j2"),
            ValueError,
            "missing metadata in template: a.j2",
        ),
        (
            errors.InvalidDestinationError("x:/y"),
            ValueError,
            "invalid destination: x:/y",
        ),
        (
            errors.InfraDotPyNotFoundError("infra"),
            ImportError,
            "infra.py: file not found",
        ),
        (
            errors.HostOrServiceNotFoundError("foo"),
            KeyError,
            "foo: host or service not found",
        ),
        (
            errors.SwitchValueError("p", value="x", options=["a", "b"]),
            ValueError,
            "Invalid value x for switch p. Options are: a, b",
        ),
        (
            errors.SwitchCaseError("p", options=["a", "b"], cases={"c": 1, "d": 2}),
            ValueError,
            "p: cases are incompatible with the options."
            " Options are: a, b, Cases are: c, d",
        ),
        (
            errors.SwitchError("p", val="x", cases={"a": 1, "b": 2}),
            ValueError,
            "p: switch value is set to x, but no case matched. Cases are: a, b",
        ),
        (
            errors.InvalidHostError("ip", "a b"),
            ValueError,
            "invalid host ip: 'a b'",
        ),
        (
            errors.InvalidMetadataError("a.j2", "missing src"),
            ValueError,
            "invalid metadata in template a.j2: missing src",
        ),
        (
            errors.NoBackupsError(".infrable/backups"),
            FileNotFoundError,
            "no backups found in: .infrable/backups",
        ),
        (
            errors.InvalidHostKeyCheckingError("maybe", {"yes", "no"}),
            ValueError,
            "invalid value 'maybe' for INFRABLE_STRICT_HOST_KEY_CHECKING."
            " Options are: no, yes",
        ),
        (errors.DuplicateIPError("1.1.1.1"), ValueError, "Duplicate IP: 1.1.1.1"),
        (errors.DuplicateFQDNError("a.b"), ValueError, "Duplicate FQDN: a.b"),
    ],
)
def test_error_messages(error, base, message):
    assert isinstance(error, errors.Error)
    assert isinstance(error, base)
    assert message in str(error)


def test_errors_can_be_raised_and_caught_as_base():
    with pytest.raises(errors.Error):
        raise errors.DuplicateIPError("1.1.1.1")
