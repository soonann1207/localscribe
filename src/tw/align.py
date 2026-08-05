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
            if ov > best_overlap:  # strictly greater: first speaker wins ties
                best_overlap = ov
                best_speaker = spk.speaker
        labeled.append(LabeledSegment(start=seg.start, end=seg.end, speaker=best_speaker, text=seg.text))
    return labeled


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_transcript(segments: list[LabeledSegment]) -> str:
    if not segments:
        return ""
    turns = []
    turn_start = segments[0].start
    current_speaker = segments[0].speaker
    current_texts = [segments[0].text]

    def _flush():
        timestamp = _format_timestamp(turn_start)
        turns.append(f"[{timestamp}] [{current_speaker}] {' '.join(current_texts)}")

    for seg in segments[1:]:
        if seg.speaker == current_speaker:
            current_texts.append(seg.text)
        else:
            _flush()
            turn_start = seg.start
            current_speaker = seg.speaker
            current_texts = [seg.text]
    _flush()
    return "\n\n".join(turns)


def bucket_by_interval(segments: list[LabeledSegment], interval_seconds: float = 300.0) -> dict[int, str]:
    buckets: dict[int, list[LabeledSegment]] = {}
    for seg in segments:
        interval_num = int(seg.start // interval_seconds) + 1
        buckets.setdefault(interval_num, []).append(seg)
    return {num: format_transcript(segs) for num, segs in buckets.items()}
