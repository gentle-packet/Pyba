"""ItemPalette shop-state tests: owned dim, upgrade highlight, discount."""

import pytest

pytest.importorskip("PySide6")

from pyba.ui.session import BuildSession  # noqa: E402
from pyba.ui.views.item_palette import ItemPalette  # noqa: E402


class _NoIcons:
    """Stub IconCache: no threadpool, no network."""

    def bind(self, *args) -> None:
        pass


@pytest.fixture()
def session(data, qtbot):
    s = BuildSession(data)
    s.set_hero("hero_atlas")
    return s


@pytest.fixture()
def palette(session, qtbot):
    p = ItemPalette(session, _NoIcons())
    qtbot.addWidget(p)
    return p


def _cell(palette, class_name):
    return next(c for c in palette.cells if c.item.class_name == class_name)


def test_owned_cell_dims_but_stays_enabled(palette, session):
    session.add_item("upgrade_long_range")
    cell = _cell(palette, "upgrade_long_range")
    assert cell.shop_state == "owned"
    assert cell.property("shopState") == "owned"
    assert cell.isEnabled()  # hover preview must keep working
    assert cell.graphicsEffect() is not None


def test_owned_cell_click_is_noop(palette, session):
    session.add_item("upgrade_long_range")
    before = session.build
    _cell(palette, "upgrade_long_range").click()
    assert session.build == before


def test_upgrade_cell_highlights_with_discount(palette, session, data):
    session.add_item("upgrade_long_range")
    cell = _cell(palette, "upgrade_sharpshooter")
    assert cell.shop_state == "upgrade"
    long_range = data.shop_items["upgrade_long_range"]
    sharp = data.shop_items["upgrade_sharpshooter"]
    expected = sharp.cost - long_range.cost
    assert f"{sharp.cost:,} → {expected:,} souls" in cell.toolTip()
    assert long_range.name in cell.toolTip()
    # unrelated item stays normal
    assert _cell(palette, "upgrade_melee_charge").shop_state == "normal"


def test_dual_component_discount_stacks(palette, session, data):
    session.add_item("upgrade_long_range")
    session.add_item("upgrade_high_velocity_mag")
    cell = _cell(palette, "upgrade_sharpshooter")
    sharp = data.shop_items["upgrade_sharpshooter"]
    expected = (
        sharp.cost
        - data.shop_items["upgrade_long_range"].cost
        - data.shop_items["upgrade_high_velocity_mag"].cost
    )
    assert f"→ {expected:,} souls" in cell.toolTip()
    assert data.shop_items["upgrade_long_range"].name in cell.toolTip()
    assert data.shop_items["upgrade_high_velocity_mag"].name in cell.toolTip()


def test_buying_upgrade_transitions_states(palette, session):
    session.add_item("upgrade_long_range")
    _cell(palette, "upgrade_sharpshooter").click()
    assert _cell(palette, "upgrade_sharpshooter").shop_state == "owned"
    # component consumed -> its tile back to normal, tooltip discount gone
    component = _cell(palette, "upgrade_long_range")
    assert component.shop_state == "normal"
    assert component.graphicsEffect() is None
    assert "→" not in _cell(palette, "upgrade_sharpshooter").toolTip()


def test_win_rate_composes_with_discount(palette, session, data):
    session.add_item("upgrade_long_range")
    cell = _cell(palette, "upgrade_sharpshooter")
    cell.set_win_rate(0.55, 1234)
    tip = cell.toolTip()
    assert "→" in tip and "55.0% win rate" in tip
    cell.set_win_rate(None, None)
    assert "win rate" not in cell.toolTip()
    assert "→" in cell.toolTip()  # discount line survives
