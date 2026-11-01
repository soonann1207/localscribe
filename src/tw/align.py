from tw.types import LabeledSegment, SpeakerSegment, TranscriptSegment


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def align(transcript: list[TranscriptSegment], speakers: list[SpeakerSegment]) -> list[LabeledSegment]:
    """Label each transcript segment with the speaker it overlaps most.

    Ties go to the speaker that comes first in `speakers`; a segment with no
    positive overlap is "UNKNOWN". Sweep over both lists sorted by start time
    (O((n + m) log(n + m) + n * k), k = concurrently active speaker turns)
    instead of comparing every segment with every turn, which is millions of
    comparisons for a multi-hour recording.
    """
    spk_order = sorted(range(len(speakers)), key=lambda i: speakers[i].start)
    seg_order = sorted(range(len(transcript)), key=lambda i: transcript[i].start)
    labels = ["UNKNOWN"] * len(transcript)

    active: list[int] = []  # indices into `speakers` that may still overlap
    next_spk = 0
    for seg_idx in seg_order:
        seg = transcript[seg_idx]
        # Admit turns that start before this segment ends ...
        while next_spk < len(spk_order) and speakers[spk_order[next_spk]].start < seg.end:
            active.append(spk_order[next_spk])
            next_spk += 1
        # ... and drop turns that ended before it starts: segments are visited
        # in start order, so those can't overlap any later segment either.
        active = [k for k in active if speakers[k].end > seg.start]

        best_overlap, best_index = 0.0, None
        for k in active:
            ov = _overlap(seg.start, seg.end, speakers[k].start, speakers[k].end)
            if ov > best_overlap or (ov == best_overlap and best_index is not None and k < best_index):
                best_overlap, best_index = ov, k
        if best_index is not None:
            labels[seg_idx] = speakers[best_index].speaker

    return [
        LabeledSegment(start=seg.start, end=seg.end, speaker=label, text=seg.text)
        for seg, label in zip(transcript, labels)
    ]


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
