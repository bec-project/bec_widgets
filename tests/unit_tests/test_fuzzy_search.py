import itertools
import random

import pytest

from bec_widgets.utils import fuzzy_search
from bec_widgets.utils.fuzzy_search import (
    EXACT,
    PIECE,
    PIECES,
    PREFIX,
    WORD_PREFIX,
    best_matches,
    close_names,
    match,
    word_starts,
)


def marked(text: str, name: str) -> str | None:
    """The name with the letters the text matches in capitals, or None when it does not fit."""
    found = match(text, name)
    if found is None:
        return None
    return "".join(c.upper() if i in found.positions else c for i, c in enumerate(name))


@pytest.mark.parametrize(
    "text, name, kind",
    [
        ("samx", "samx", EXACT),
        ("samx", "samx_setpoint", PREFIX),
        ("set", "samx_setpoint", WORD_PREFIX),
        ("etp", "samx_setpoint", PIECE),
        ("bp3", "bpm3b", PIECES),
    ],
)
def test_a_text_fits_a_name_in_one_of_five_ways(text, name, kind):
    assert match(text, name).rank[0] == kind


@pytest.mark.parametrize("text, name", [("xyz", "samx_setpoint"), ("samx_setpoint", "samx")])
def test_a_text_that_is_not_in_the_name_does_not_fit(text, name):
    assert match(text, name) is None


def test_case_does_not_matter_and_an_empty_text_fits_everything():
    assert marked("BPM", "bpm4i") == "BPM4i"
    assert match("bpm", "BPM4i").positions == (0, 1, 2)
    for text in ("", "   "):
        found = match(text, "bpm4i")
        assert found is not None and found.positions == ()


def test_words_start_after_separators_at_capitals_and_where_digits_change():
    starts = word_starts("bpm4i_setPoint")
    assert [i for i, start in enumerate(starts) if start] == [0, 3, 4, 6, 9]


def test_the_start_of_a_word_wins_over_an_earlier_place():
    assert marked("set", "reset_setpoint") == "reset_SETpoint"
    assert match("set", "reset_setpoint").rank[0] == WORD_PREFIX


@pytest.mark.parametrize(
    "text, name, result",
    [
        ("bp3", "bpm3b", "BPm3b"),
        ("ss", "samx_setpoint", "Samx_Setpoint"),
        ("samxset", "samx_setpoint", "SAMX_SETpoint"),
        ("mi", "motor_is_moving", "Motor_Is_moving"),
        ("bi", "bpm4i", "Bpm4I"),
        ("abc", "a_b_ab_c", "a_b_AB_C"),
        ("ss", "samx_setpoint_status", "Samx_Setpoint_status"),
    ],
)
def test_pieces_each_start_a_word_in_order(text, name, result):
    assert marked(text, name) == result


@pytest.mark.parametrize(
    "text, name",
    [("smx", "samx"), ("sx", "samx"), ("eig", "eyex_motor_is_moving"), ("sp", "samx_setpoint")],
)
def test_letters_scattered_inside_words_do_not_fit(text, name):
    assert match(text, name) is None


def test_a_text_with_spaces_is_several_texts_that_must_all_fit():
    for text in ("samx set", "set samx"):
        assert marked(text, "samx_setpoint") == "SAMX_SETpoint"
        assert match(text, "samx_setpoint").rank[0] == WORD_PREFIX
    assert match("samx vel", "samx_setpoint") is None


def test_the_best_fit_comes_first_and_equal_fits_keep_their_order():
    names = ["s_a_m_x", "xsamx", "samx_motor_is_moving", "samx_setpoint", "samy", "samx"]
    names.append("hexapod_samx")
    assert [name for name, _fit in best_matches("samx", names)] == [
        "samx",
        "samx_setpoint",
        "samx_motor_is_moving",
        "hexapod_samx",
        "xsamx",
        "s_a_m_x",
    ]
    names = ["bpm4i", "bpm3a", "bpm4a"]
    assert [name for name, _fit in best_matches("bpm", names)] == names


def test_close_names_catch_a_typo_when_nothing_fits():
    assert close_names("smx", ["samy", "samx", "mbsx"]) == ["samx", "mbsx"]
    assert close_names("bmp4i", ["bpm4i", "samx"]) == ["bpm4i"]
    assert close_names("sm", ["samx"]) == []


def test_the_cut_into_pieces_is_the_cheapest_of_every_cut():
    rng = random.Random(20261119)
    for _ in range(2000):
        name = "".join(rng.choice("ab_1A") for _ in range(rng.randint(2, 10)))
        text = "".join(rng.choice("ab1") for _ in range(rng.randint(2, 4)))
        # Words start where the name as written says, the letters compare in lower case.
        starts = word_starts(name)
        found = fuzzy_search._pieces(text, name.lower(), starts)
        expected = _cost_of_every_cut(text, name.lower(), starts)
        assert (found[0] if found else None) == expected, (text, name)


def _cost_of_every_cut(text: str, name: str, starts: list[bool]) -> int | None:
    """The cheapest cost of :func:`fuzzy_search._pieces`, found by trying every cut."""
    best = None
    for cut_count in range(len(text)):
        for cuts in itertools.combinations(range(1, len(text)), cut_count):
            bounds = (0, *cuts, len(text))
            pieces = [text[a:b] for a, b in zip(bounds, bounds[1:])]
            stack = [(0, 0, ())]
            while stack:
                index, earliest, places = stack.pop()
                if index == len(pieces):
                    last = places[-1] + len(pieces[-1]) - 1
                    cost = len(pieces) * fuzzy_search._PIECE_COST + last + 1 - len(text)
                    best = cost if best is None else min(best, cost)
                    continue
                piece = pieces[index]
                for at in range(earliest, len(name) - len(piece) + 1):
                    if starts[at] and name.startswith(piece, at):
                        stack.append((index + 1, at + len(piece) + 1, places + (at,)))
    return best
