"""BuildSession tests (pytest-qt): mutation funnel, undo/redo, preview."""

import pytest

pytest.importorskip("PySide6")

from deadlock_eos import Stat  # noqa: E402
from pyba.ui.session import BuildSession  # noqa: E402


@pytest.fixture()
def session(data, qtbot):
    return BuildSession(data)


def test_mutations_emit_and_resolve(session, qtbot):
    with qtbot.waitSignal(session.changed):
        session.set_hero("hero_atlas")
    with qtbot.waitSignal(session.changed):
        session.add_item("upgrade_clip_size")
    assert session.build.items == ("upgrade_clip_size",)
    assert session.resolution.stats[Stat.CLIP_SIZE].final > 9  # modifier applied

    session.add_item("upgrade_clip_size")  # duplicate is a no-op, no signal
    assert session.build.items == ("upgrade_clip_size",)


def test_stacks_and_tiers(session, qtbot):
    session.set_hero("hero_atlas")
    session.add_item("upgrade_berserker")
    with qtbot.waitSignal(session.changed):
        session.set_stacks("upgrade_berserker", 5)
    assert session.resolution.stats[Stat.WEAPON_DAMAGE_PCT].final > 0
    with qtbot.waitSignal(session.changed):
        session.set_tier("citadel_ability_bull_heal", 3)
    heal = session.resolution.abilities["citadel_ability_bull_heal"]
    assert heal.tier == 3
    assert session.max_stacks_for("upgrade_berserker") == 10
    assert session.max_stacks_for("upgrade_clip_size") is None


def test_undo_redo(session, qtbot):
    session.set_hero("hero_atlas")
    baseline = session.build
    session.add_item("upgrade_clip_size")
    session.set_level(5)
    assert session.can_undo()

    session.undo()
    assert session.build.level == 1 and session.build.items
    session.undo()
    assert session.build == baseline
    assert session.can_redo()
    session.redo()
    assert session.build.items == ("upgrade_clip_size",)

    # a new mutation clears redo
    session.set_level(3)
    assert not session.can_redo()


def test_upgrade_consumes_component(session, qtbot):
    session.set_hero("hero_atlas")
    session.add_item("upgrade_long_range")
    with qtbot.waitSignal(session.changed):
        session.add_item("upgrade_sharpshooter")
    assert "upgrade_sharpshooter" in session.build.items
    assert "upgrade_long_range" not in session.build.items

    # undo restores component and removes upgrade in one step
    session.undo()
    assert session.build.items == ("upgrade_long_range",)


def test_upgrade_consumes_all_owned_components(session, qtbot):
    session.set_hero("hero_atlas")
    session.add_item("upgrade_long_range")
    session.add_item("upgrade_high_velocity_mag")
    session.add_item("upgrade_sharpshooter")
    assert session.build.items == ("upgrade_sharpshooter",)


def test_upgrade_without_owned_component_removes_nothing(session, qtbot):
    session.set_hero("hero_atlas")
    session.add_item("upgrade_clip_size")
    session.add_item("upgrade_sharpshooter")
    assert session.build.items == ("upgrade_clip_size", "upgrade_sharpshooter")


def test_consumed_component_state_dropped(session, qtbot):
    # No component item has a stack handler today, so seed item_states
    # directly and check the candidate build (resolver would reject stacks).
    import dataclasses

    from deadlock_eos import ItemState

    session.set_hero("hero_atlas")
    session.add_item("upgrade_long_range")
    session._build = dataclasses.replace(
        session._build, item_states={"upgrade_long_range": ItemState(stacks=3)}
    )
    candidate = session._with_item("upgrade_sharpshooter")
    assert "upgrade_long_range" not in candidate.items
    assert "upgrade_long_range" not in candidate.item_states


def test_preview_upgrade_models_consumption(session, qtbot):
    session.set_hero("hero_atlas")
    session.add_item("upgrade_long_range")
    before = session.build
    with qtbot.waitSignal(session.previewChanged) as blocker:
        session.preview_add_item("upgrade_sharpshooter")
    assert blocker.args[0] is not None
    assert session.build == before  # preview never commits


def test_preview_does_not_mutate(session, qtbot):
    session.set_hero("hero_atlas")
    before = session.build
    with qtbot.waitSignal(session.previewChanged) as blocker:
        session.preview_add_item("upgrade_clip_size")
    preview = blocker.args[0]
    assert preview is not None
    assert preview.stats[Stat.CLIP_SIZE].final > session.resolution.stats[Stat.CLIP_SIZE].final
    assert session.build == before  # preview never commits

    with qtbot.waitSignal(session.previewChanged) as blocker:
        session.clear_preview()
    assert blocker.args[0] is None
