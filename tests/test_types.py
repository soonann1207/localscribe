from tw.types import TranscriptSegment, SpeakerSegment, LabeledSegment

def test_transcript_segment_fields():
    seg = TranscriptSegment(start=0.0, end=1.5, text="hello")
    assert seg.start == 0.0
    assert seg.end == 1.5
    assert seg.text == "hello"

def test_speaker_segment_fields():
    seg = SpeakerSegment(start=0.0, end=1.5, speaker="SPEAKER_00")
    assert seg.speaker == "SPEAKER_00"

def test_labeled_segment_fields():
    seg = LabeledSegment(start=0.0, end=1.5, speaker="SPEAKER_00", text="hello")
    assert seg.speaker == "SPEAKER_00"
    assert seg.text == "hello"
