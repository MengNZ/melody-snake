"""Note-level evaluation metrics with explicit definitions.

Reference note: {midi, start, end} (seconds)
Predicted note: {midiNote, startTime, endTime} (the app's NoteEvent)

Matching (greedy, one-to-one): for each reference note in onset order, assign
the temporally-most-overlapping unmatched predicted note. A pair counts as a
TEMPORAL MATCH when overlap / min(duration) >= overlap_ratio.

Per matched pair, the pitch error is diff = pred.midiNote - ref.midi:
  - |diff| <= pitch_tol            -> hit (correct note + correct pitch)
  - 11.0 <= |diff| <= 13.0         -> octave error
  - otherwise                      -> wrong pitch

Definitions:
  note_precision  = hits / n_predicted
  note_recall     = hits / n_reference
  f1              = 2*P*R/(P+R)
  pitch_accuracy  = hits / (hits + octave + wrong)   [of temporally-matched notes]
  octave_error_rate = octave / n_predicted
  mean_abs_onset_error = mean(|pred.startTime - ref.start|) over pitch-correct hits
  interval_accuracy = correct interval / adjacent reference pairs whose two notes
    both have temporal matches; pitch-class intervals ignore octave transposition
"""


def _overlap(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def evaluate(pred, ref, overlap_ratio=0.5, pitch_tol=0.5):
    refs = sorted(ref, key=lambda n: n["start"])
    preds = sorted(pred, key=lambda n: n["startTime"])

    used_pred = [False] * len(preds)
    matched_ref = [False] * len(refs)
    matched_pred_for_ref = {}

    hits = []      # (pred, ref, diff, onset_err)
    octaves = []   # (pred, ref, diff, onset_err)
    wrong = []     # (pred, ref, diff, onset_err)

    for ri, r in enumerate(refs):
        r_dur = r["end"] - r["start"]
        best_i = -1
        best_ov = 0.0
        for pi, p in enumerate(preds):
            if used_pred[pi]:
                continue
            ov = _overlap(p["startTime"], p["endTime"], r["start"], r["end"])
            p_dur = p["endTime"] - p["startTime"]
            ratio = ov / max(min(r_dur, p_dur), 1e-6)
            if ratio > best_ov:
                best_ov = ratio
                best_i = pi

        if best_i >= 0 and best_ov >= overlap_ratio:
            used_pred[best_i] = True
            matched_ref[ri] = True
            p = preds[best_i]
            matched_pred_for_ref[ri] = p
            diff = p["midiNote"] - r["midi"]
            onset_err = p["startTime"] - r["start"]
            if abs(diff) <= pitch_tol:
                hits.append((p, r, diff, onset_err))
            elif 11.0 <= abs(diff) <= 13.0:
                octaves.append((p, r, diff, onset_err))
            else:
                wrong.append((p, r, diff, onset_err))

    fn = [r for ri, r in enumerate(refs) if not matched_ref[ri]]
    fp = [p for pi, p in enumerate(preds) if not used_pred[pi]]

    n_pred = len(preds)
    n_ref = len(refs)
    n_hit = len(hits)
    n_oct = len(octaves)
    n_wrong = len(wrong)

    precision = n_hit / n_pred if n_pred else 0.0
    recall = n_hit / n_ref if n_ref else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    pitch_acc = n_hit / (n_hit + n_oct + n_wrong) if (n_hit + n_oct + n_wrong) else 0.0
    oct_rate = n_oct / n_pred if n_pred else 0.0
    onset_errs = [abs(h[3]) for h in hits]
    mean_onset = float(np_mean(onset_errs)) if onset_errs else None

    interval_errors = []
    pitch_class_interval_errors = []
    for ri in range(len(refs) - 1):
        if ri not in matched_pred_for_ref or ri + 1 not in matched_pred_for_ref:
            continue
        ref_interval = refs[ri + 1]["midi"] - refs[ri]["midi"]
        pred_interval = (matched_pred_for_ref[ri + 1]["midiNote"]
                         - matched_pred_for_ref[ri]["midiNote"])
        interval_errors.append(abs(pred_interval - ref_interval))
        pitch_class_interval_errors.append((pred_interval - ref_interval) % 12)
    n_intervals = len(interval_errors)
    interval_accuracy = (sum(error <= pitch_tol for error in interval_errors) / n_intervals
                         if n_intervals else None)
    pitch_class_interval_accuracy = (
        sum(error == 0 for error in pitch_class_interval_errors) / n_intervals
        if n_intervals else None
    )

    return {
        "n_reference": n_ref,
        "n_predicted": n_pred,
        "hits": n_hit,
        "false_negatives": len(fn),
        "false_positives": len(fp),
        "octave_errors": n_oct,
        "wrong_pitch": n_wrong,
        "note_precision": precision,
        "note_recall": recall,
        "f1": f1,
        "pitch_accuracy": pitch_acc,
        "adjacent_interval_pairs": n_intervals,
        "interval_accuracy": interval_accuracy,
        "pitch_class_interval_accuracy": pitch_class_interval_accuracy,
        "octave_error_rate": oct_rate,
        "mean_abs_onset_error_s": mean_onset,
        "interval_definitions": {
            "matching": "consecutive reference notes count only when both have temporal event matches",
            "interval_accuracy": "signed semitone interval difference is within pitch_tol; octave matters",
            "pitch_class_interval_accuracy": "directed semitone interval difference is 0 modulo 12; octave is ignored",
        },
    }


def np_mean(values):
    return sum(values) / len(values)
