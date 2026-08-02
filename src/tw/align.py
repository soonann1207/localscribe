from tw.types import LabeledSegment, SpeakerSegment, TranscriptSegment


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def align(transcript: list[TranscriptSegment], speakers: list[SpeakerSegment]) -> list[LabeledSegment]:
    labeled = []
    for seg in transcript:
        best_speaker = "UNKNOWN"
        best_overlap = 0.0
        for spk in speakers:
            ov = _overlap(seg.start, seg.end, spk.start, spk.end)
            if ov > best_overlap:
                best_overlap = ov
                best_speaker = spk.speaker
        labeled.append(LabeledSegment(start=seg.start, end=seg.end, speaker=best_speaker, text=seg.text))
    return labeled
