"""Range-gated weapon damage in the UI: dps-vs-range curve step, stretched
falloff marks, and the distance-aware sidebar extractors. Expected values are
read from the dump items, never hardcoded balance numbers."""

import pytest

pytest.importorskip("PySide6")

from deadlock_eos import Build, resolve  # noqa: E402
from deadlock_eos import weapon_math as wm  # noqa: E402
from deadlock_eos.stats import RANGE_GATED_DAMAGE  # noqa: E402
from pyba.ui.session import BuildSession  # noqa: E402
from pyba.ui.views.range_graph import _curve, _falloff_marks, _threshold_marks  # noqa: E402
from pyba.ui.views.stats_pane import StatsContext, _dps_at  # noqa: E402

HERO = "hero_atlas"
LONG_RANGE = "upgrade_long_range"
CLOSE_QUARTERS = "upgrade_close_range"
LR_DAMAGE = "MODIFIER_VALUE_LONG_RANGE_BULLET_DAMAGE_INCREASE"
CR_DAMAGE = "MODIFIER_VALUE_CLOSE_RANGE_WEAPON_DAMAGE_INCREASE"


def gate(data, item_cn, damage_modifier):
    """(bonus pct, threshold meters) straight from the dump item."""
    item = data.shop_items[item_cn]
    pct = next(p.value for p in item.passive_modifiers if p.modifier_type == damage_modifier)
    threshold_type, _ = RANGE_GATED_DAMAGE[damage_modifier]
    threshold = next(
        p.value
        for p in item.properties.values()
        if p.modifier_type == threshold_type and not p.is_disabled
    )
    return pct, threshold


def test_curve_shows_step(data):
    naked = resolve(data, Build(hero=HERO), strict=False)
    res = resolve(data, Build(hero=HERO, items=(LONG_RANGE,)), strict=False)
    pct, min_m = gate(data, LONG_RANGE, LR_DAMAGE)

    points = _curve(res)
    # injected gate-edge samples: one just below the threshold, one at it
    below_d, below_dps = max((p for p in points if p[0] < min_m), key=lambda p: p[0])
    at_d, at_dps = min((p for p in points if p[0] >= min_m), key=lambda p: p[0])
    assert at_d == pytest.approx(min_m)
    assert below_d == pytest.approx(min_m, rel=1e-3)
    k = res.gun.falloff_range_mult
    falloff_ratio = wm.falloff_scale_stretched(
        res.gun.info, at_d * wm.UNITS_PER_METER, k
    ) / wm.falloff_scale_stretched(res.gun.info, below_d * wm.UNITS_PER_METER, k)
    assert at_dps / below_dps == pytest.approx((1.0 + pct / 100.0) * falloff_ratio)

    # naked curve still matches the old formula: scalar dps x plain falloff
    info = naked.gun.info
    for d_m, dps in _curve(naked):
        assert dps == pytest.approx(
            naked.gun.damage_per_second * wm.falloff_scale(info, d_m * wm.UNITS_PER_METER)
        )


def test_curve_close_item_elevates_near_range_only(data):
    naked = resolve(data, Build(hero=HERO), strict=False)
    res = resolve(data, Build(hero=HERO, items=(CLOSE_QUARTERS,)), strict=False)
    pct, max_m = gate(data, CLOSE_QUARTERS, CR_DAMAGE)
    assert res.gun.damage_per_second_at(5.0) == pytest.approx(
        naked.gun.damage_per_second_at(5.0) * (1.0 + pct / 100.0)
    )
    assert res.gun.damage_per_second_at(max_m + 5.0) == pytest.approx(
        naked.gun.damage_per_second_at(max_m + 5.0)
    )


def test_falloff_marks_stretched_and_threshold_present(data):
    naked = resolve(data, Build(hero=HERO), strict=False)
    res = resolve(data, Build(hero=HERO, items=(LONG_RANGE,)), strict=False)
    _, min_m = gate(data, LONG_RANGE, LR_DAMAGE)

    naked_start, naked_end = _falloff_marks(naked)
    start, end = _falloff_marks(res)
    k = res.gun.falloff_range_mult
    assert k > 1.0  # Long Range's fall-off range bonus landed
    if naked_start is not None:
        assert start == pytest.approx(naked_start * k)
    if naked_end is not None:
        assert end == pytest.approx(naked_end * k)

    assert _threshold_marks(naked) == []
    assert _threshold_marks(res) == [pytest.approx(min_m)]


def test_stats_rows_and_preview_delta(data, qtbot):
    session = BuildSession(data)
    session.set_hero(HERO)
    ctx = StatsContext()
    ctx.data = data

    at20 = _dps_at(20.0)
    baseline = at20(session.resolution, ctx)

    with qtbot.waitSignal(session.previewChanged) as blocker:
        session.preview_add_item(LONG_RANGE)
    preview = blocker.args[0]
    pct, _ = gate(data, LONG_RANGE, LR_DAMAGE)
    # the delta the sidebar renders on the @20m row: gate bonus + stretch
    assert at20(preview, ctx) > baseline * (1.0 + pct / 100.0) * 0.99

    session.add_item(LONG_RANGE)
    assert at20(session.resolution, ctx) == pytest.approx(at20(preview, ctx))
    # below the gate only the falloff stretch moves the number
    at5 = _dps_at(5.0)
    assert at5(session.resolution, ctx) >= _dps_at(5.0)(preview, ctx) * 0.999
