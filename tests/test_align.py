# tests/test_align.py
from tw.align import align, format_transcript
from tw.types import TranscriptSegment, SpeakerSegment, LabeledSegment

def test_align_assigns_majority_overlap_speaker():
    transcript = [TranscriptSegment(start=0.0, end=2.0, text="hello there")]
    speakers = [
        SpeakerSegment(start=0.0, end=1.5, speaker="SPEAKER_00"),
        SpeakerSegment(start=1.5, end=2.0, speaker="SPEAKER_01"),
    ]
    result = align(transcript, speakers)
    assert len(result) == 1
    assert result[0].speaker == "SPEAKER_00"
    assert result[0].text == "hello there"

def test_align_handles_no_overlapping_speaker():
    transcript = [TranscriptSegment(start=5.0, end=6.0, text="orphan segment")]
    speakers = [SpeakerSegment(start=0.0, end=1.0, speaker="SPEAKER_00")]
    result = align(transcript, speakers)
    assert result[0].speaker == "UNKNOWN"

def test_align_preserves_segment_order_and_timing():
    transcript = [
        TranscriptSegment(start=0.0, end=1.0, text="first"),
        TranscriptSegment(start=1.0, end=2.0, text="second"),
    ]
    speakers = [SpeakerSegment(start=0.0, end=2.0, speaker="SPEAKER_00")]
    result = align(transcript, speakers)
    assert [s.text for s in result] == ["first", "second"]
    assert result[1].start == 1.0
    assert result[1].end == 2.0

def test_align_tie_break_first_speaker_wins():
    """When two speakers have equal overlap, the first in list order wins (tie-break rule)."""
    transcript = [TranscriptSegment(start=0.0, end=2.0, text="ambiguous")]
    speakers = [
        SpeakerSegment(start=0.0, end=1.0, speaker="SPEAKER_00"),  # overlap: 1.0
        SpeakerSegment(start=1.0, end=2.0, speaker="SPEAKER_01"),  # overlap: 1.0
    ]
    result = align(transcript, speakers)
    assert result[0].speaker == "SPEAKER_00"  # first in list wins tie

def test_align_zero_duration_segment_resolves_to_unknown():
    """Zero-duration transcript segments (start == end) always resolve to UNKNOWN."""
    transcript = [TranscriptSegment(start=1.0, end=1.0, text="zero")]
    speakers = [SpeakerSegment(start=0.5, end=1.5, speaker="SPEAKER_00")]
    result = align(transcript, speakers)
    assert result[0].speaker == "UNKNOWN"

def test_align_empty_speakers_list():
    """Empty speakers list results in all segments marked UNKNOWN."""
    transcript = [
        TranscriptSegment(start=0.0, end=1.0, text="first"),
        TranscriptSegment(start=1.0, end=2.0, text="second"),
    ]
    speakers = []
    result = align(transcript, speakers)
    assert len(result) == 2
    assert all(s.speaker == "UNKNOWN" for s in result)

def test_align_multiple_segments_different_speakers():
    """Multiple transcript segments can each align to different speakers."""
    transcript = [
        TranscriptSegment(start=0.0, end=1.0, text="first"),
        TranscriptSegment(start=2.0, end=3.0, text="second"),
    ]
    speakers = [
        SpeakerSegment(start=0.0, end=1.0, speaker="SPEAKER_00"),
        SpeakerSegment(start=2.0, end=3.0, speaker="SPEAKER_01"),
    ]
    result = align(transcript, speakers)
    assert len(result) == 2
    assert result[0].speaker == "SPEAKER_00"
    assert result[1].speaker == "SPEAKER_01"

def test_format_transcript_merges_consecutive_same_speaker():
    segments = [
        LabeledSegment(start=0.0, end=1.0, speaker="SPEAKER_00", text="hello"),
        LabeledSegment(start=1.0, end=2.0, speaker="SPEAKER_00", text="there"),
        LabeledSegment(start=65.0, end=66.0, speaker="SPEAKER_01", text="hi back"),
    ]
    result = format_transcript(segments)
    assert result == "[00:00:00] [SPEAKER_00] hello there\n\n[00:01:05] [SPEAKER_01] hi back"

def test_format_transcript_empty_list_returns_empty_string():
    assert format_transcript([]) == ""

def test_format_transcript_single_segment():
    segments = [LabeledSegment(start=0.0, end=1.0, speaker="SPEAKER_00", text="solo")]
    assert format_transcript(segments) == "[00:00:00] [SPEAKER_00] solo"

def test_format_transcript_timestamp_uses_turns_first_segment_start():
    segments = [
        LabeledSegment(start=3661.0, end=3662.0, speaker="SPEAKER_00", text="over an hour in"),
    ]
    result = format_transcript(segments)
    assert result == "[01:01:01] [SPEAKER_00] over an hour in"
