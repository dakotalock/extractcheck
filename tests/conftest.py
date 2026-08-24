import os

os.environ["EXTRACTCHECK_ALLOW_DEV"] = "1"
os.environ.setdefault(
    "EXTRACTCHECK_ED25519_SEED",
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)


import pytest


@pytest.fixture(autouse=True)
def _dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTCHECK_ALLOW_DEV", "1")
    monkeypatch.setenv(
        "EXTRACTCHECK_ED25519_SEED",
        os.environ["EXTRACTCHECK_ED25519_SEED"],
    )
