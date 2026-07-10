"""Fit JSON persistence round-trip tests."""

import pytest

from deadlock_eos import Build, ItemState, Stat
from pyba.fits import Fit, fit_from_dict, fit_to_dict, load_fit, save_fit


def sample_fit() -> Fit:
    return Fit(
        name="Test Abrams",
        notes="round-trip",
        build=Build(
            hero="hero_atlas",
            level=12,
            items=("upgrade_clip_size", "upgrade_berserker"),
            ability_tiers={"citadel_ability_bull_heal": 3},
            item_states={"upgrade_berserker": ItemState(stacks=10)},
            overrides={Stat.SPIRIT_POWER: 100.0},
        ),
    )


def test_roundtrip_dict():
    fit = sample_fit()
    restored = fit_from_dict(fit_to_dict(fit))
    assert restored == fit
    assert restored.build.overrides == {Stat.SPIRIT_POWER: 100.0}
    assert restored.build.item_states["upgrade_berserker"].stacks == 10


def test_roundtrip_file(tmp_path):
    fit = sample_fit()
    path = tmp_path / "abrams.fit.json"
    save_fit(fit, path)
    assert load_fit(path) == fit


def test_version_gate():
    payload = fit_to_dict(sample_fit())
    payload["format_version"] = 999
    with pytest.raises(ValueError, match="format_version"):
        fit_from_dict(payload)
