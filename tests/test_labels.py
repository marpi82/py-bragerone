import asyncio
import pytest
from bragerone.labels import LabelFetcher


@pytest.mark.asyncio
async def test_labels_bootstrap_no_crash():
    """Bootstrap shouldn’t crash and counters should be integers."""
    lf = LabelFetcher()
    # current implementation is a no-op; must not raise
    await lf.bootstrap(lang="pl")
    assert isinstance(lf.count_vars(), int)
    assert isinstance(lf.count_langs(), int)


def test_param_label_unknown_returns_none():
    """
    With the current minimal label store, unknown params have no label.
    That’s fine — higher layers can fall back to raw names.
    """
    lf = LabelFetcher()
    assert lf.param_label("P6", 7, "pl") is None


def test_idempotent_counters():
    """
    Counters should remain stable across no-op bootstrap calls.
    (Regression guard for future changes.)
    """
    lf = LabelFetcher()
    c1_vars = lf.count_vars()
    c1_langs = lf.count_langs()
    # pretend we call bootstrap again (still a no-op today)
    asyncio.get_event_loop().run_until_complete(lf.bootstrap(lang="pl"))
    c2_vars = lf.count_vars()
    c2_langs = lf.count_langs()
    assert c1_vars == c2_vars
    assert c1_langs == c2_langs
