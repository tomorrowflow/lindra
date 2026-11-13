"""The append rule for an accepted transcript: pure logic, no storage, no HTTP.

A transcript becomes a marked passage at the end of the notes. The typed text stays exactly as
it is, byte for byte, and the passage always starts on a line of its own after a blank line.
"""

from datetime import datetime

import pytest

from lindra import cases, dictation

AT = datetime(2026, 11, 10, 14, 30, 41)
MARK = "[Diktat, 10.11.2026 14:30]"


def test_a_transcript_in_empty_notes_becomes_the_marked_passage():
    assert dictation.append("", "Nachts wacht sie zweimal auf.", AT) == (
        f"{MARK}\nNachts wacht sie zweimal auf.\n"
    )


def test_a_transcript_is_added_after_a_blank_line_below_the_typed_text():
    notes = "Rückenschmerz seit 14 Monaten."

    assert dictation.append(notes, "Dazu Schlafstörung.", AT) == (
        f"{notes}\n\n{MARK}\nDazu Schlafstörung.\n"
    )


@pytest.mark.parametrize(
    ("notes", "separator"),
    [
        ("Text", "\n\n"),
        ("Text\n", "\n"),
        ("Text\n\n", ""),
        ("Text\n\n\n", ""),
        ("Text ", "\n\n"),
        ("Text\r\n", "\n"),
    ],
)
def test_the_typed_text_is_kept_exactly_and_only_a_missing_blank_line_is_added(notes, separator):
    appended = dictation.append(notes, "Neu.", AT)

    assert appended == f"{notes}{separator}{MARK}\nNeu.\n"
    assert appended.startswith(notes)


def test_the_transcript_loses_only_its_outer_blanks():
    appended = dictation.append("", "  \nErste Zeile.\nZweite Zeile.\n\n ", AT)

    assert appended == f"{MARK}\nErste Zeile.\nZweite Zeile.\n"


def test_a_second_dictation_comes_after_the_first_and_leaves_it_alone():
    first = dictation.append("Eigene Notiz.", "Erstes Diktat.", AT)
    later = datetime(2026, 11, 10, 15, 2)

    second = dictation.append(first, "Zweites Diktat.", later)

    assert second.startswith(first)
    assert second.endswith("\n\n[Diktat, 10.11.2026 15:02]\nZweites Diktat.\n")


def test_the_marker_names_the_minute_of_the_clock():
    assert dictation.marker(datetime(2026, 1, 5, 9, 7, 59)) == "[Diktat, 05.01.2026 09:07]"


def test_a_transcript_that_would_exceed_the_notes_limit_is_refused_and_names_the_limit():
    notes = "x" * (cases.MAX_NOTES_LENGTH - 10)

    with pytest.raises(cases.Invalid) as refused:
        dictation.append(notes, "Dieses Diktat passt nicht mehr hinein.", AT)

    assert str(cases.MAX_NOTES_LENGTH) in refused.value.errors["transcript"]


@pytest.mark.parametrize(
    "body", [{}, {"transcript": ""}, {"transcript": " \n "}, {"transcript": 7}]
)
def test_a_missing_or_blank_transcript_is_not_a_transcript(body):
    with pytest.raises(cases.Invalid) as refused:
        dictation.parse_transcript(body)

    assert "transcript" in refused.value.errors


def test_a_transcript_is_read_as_the_physician_corrected_it():
    assert dictation.parse_transcript({"transcript": "\n Korrigiert. \n"}) == "Korrigiert."
