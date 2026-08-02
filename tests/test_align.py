# tests/test_align.py
from tw.align import align
from tw.types import TranscriptSegment, SpeakerSegment

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
