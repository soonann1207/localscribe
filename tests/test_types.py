from tw.types import TranscriptSegment, SpeakerSegment, LabeledSegment, rescale_segment_times

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

def test_rescale_segment_times_divides_by_factor():
    segments = [TranscriptSegment(start=2.0, end=4.0, text="hello")]
    result = rescale_segment_times(segments, factor=2.0)
    assert result[0].start == 1.0
    assert result[0].end == 2.0
    assert result[0].text == "hello"

def test_rescale_segment_times_no_op_at_factor_one():
    segments = [SpeakerSegment(start=2.0, end=4.0, speaker="SPEAKER_00")]
    result = rescale_segment_times(segments, factor=1.0)
    assert result[0].start == 2.0
    assert result[0].end == 4.0

def test_rescale_segment_times_preserves_original_list():
    segments = [TranscriptSegment(start=2.0, end=4.0, text="hello")]
    rescale_segment_times(segments, factor=2.0)
    assert segments[0].start == 2.0
