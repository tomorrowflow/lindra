"""Background selection by date and the background revision (ADR 0010), as pure functions."""

from dataclasses import dataclass
from datetime import datetime

from lindra import background


@dataclass(frozen=True)
class Contact:
    id: int
    kind: str
    occurred_at: datetime
    acceptances: int = 0


def at(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 10, day, hour)


ASSESSMENT = Contact(1, "assessment", at(5), acceptances=2)
FIRST = Contact(2, "visit", at(9), acceptances=1)
SECOND = Contact(3, "visit", at(12), acceptances=3)
THIRD = Contact(4, "visit", at(14))
ALL = [THIRD, SECOND, ASSESSMENT, FIRST]


def ids(found):
    return [e.id for e in found]


def test_a_visit_draws_on_the_assessment_and_the_visits_dated_before_it():
    assert ids(background.background_of(SECOND, ALL)) == [1, 2]


def test_a_later_visit_is_never_background():
    assert ids(background.background_of(FIRST, ALL)) == [1]


def test_a_backdated_visit_sees_only_what_preceded_its_date():
    backdated = Contact(5, "visit", at(10), acceptances=0)

    found = background.background_of(backdated, [*ALL, backdated])

    assert ids(found) == [1, 2]


def test_visits_at_the_same_moment_are_not_background_of_each_other():
    twin = Contact(6, "visit", at(9))

    assert ids(background.background_of(twin, [*ALL, twin])) == [1]
    assert ids(background.background_of(FIRST, [*ALL, twin])) == [1]


def test_an_earlier_time_on_the_same_day_counts_as_earlier():
    morning = Contact(7, "visit", at(12, 8))

    assert ids(background.background_of(SECOND, [*ALL, morning])) == [1, 2, 7]


def test_the_assessment_is_background_even_when_a_visit_is_dated_before_it():
    early = Contact(8, "visit", at(4))

    assert ids(background.background_of(early, [*ALL, early])) == [1]


def test_the_assessment_has_no_background():
    assert background.background_of(ASSESSMENT, ALL) == []
    assert background.revision(ASSESSMENT, ALL) == 0


def test_the_background_revision_is_the_sum_of_the_acceptance_counters():
    assert background.revision(THIRD, ALL) == 2 + 1 + 3
    assert background.revision(SECOND, ALL) == 2 + 1
    assert background.revision(FIRST, ALL) == 2


def test_accepting_a_later_visit_does_not_move_the_revision_of_an_earlier_one():
    accepted_again = Contact(4, "visit", at(14), acceptances=9)

    assert background.revision(SECOND, [ASSESSMENT, FIRST, SECOND, accepted_again]) == 3


def test_accepting_an_encounter_of_the_background_moves_the_revision():
    again = Contact(1, "assessment", at(5), acceptances=3)

    assert background.revision(SECOND, [again, FIRST, SECOND]) == 3 + 1


def test_a_visit_is_not_part_of_its_own_background():
    assert 3 not in ids(background.background_of(SECOND, ALL))


def test_only_encounters_with_an_accepted_draft_have_anything_to_draw_on():
    visit = Contact(9, "visit", at(13))

    found = background.accepted(background.background_of(visit, [*ALL, visit]))

    assert ids(found) == [1, 2, 3]
    assert background.accepted([Contact(10, "assessment", at(5))]) == []


def test_a_reference_source_names_its_encounter():
    key = background.source_key(12)

    assert key == "encounter:12"
    assert background.encounter_of(key) == 12
    assert background.encounter_of("notes") is None
    assert background.encounter_of("encounter:") is None
    assert background.encounter_of("encounter:1x") is None
    assert background.encounter_of("encounter:-3") is None
