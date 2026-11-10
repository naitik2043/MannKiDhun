import numpy as np


class UncertainMoodDetected(ValueError):
    pass


def normalize_mood(label, aliases):
    mood = str(label).strip().lower()
    return aliases.get(mood, mood)


def aggregate_predictions(frame_scores, labels, aliases, total_frames):
    scores = np.asarray(frame_scores, dtype=np.float64)
    labels = [str(label) for label in labels]
    if (
        scores.ndim != 2
        or scores.shape[1] != len(labels)
        or not 1 <= scores.shape[0] <= total_frames
        or not np.isfinite(scores).all()
        or np.any(scores < 0)
        or np.any(scores > 1)
        or not np.allclose(np.sum(scores, axis=1), 1.0, atol=0.02)
    ):
        raise ValueError("The emotion model returned invalid prediction scores.")

    mean_scores = np.mean(scores, axis=0)
    mood_index = int(np.argmax(mean_scores))
    mood = normalize_mood(labels[mood_index], aliases)
    consistency = float(
        np.mean(
            [
                normalize_mood(labels[int(np.argmax(frame))], aliases) == mood
                for frame in scores
            ]
        )
    )
    if total_frames > 1 and consistency < 0.6:
        raise UncertainMoodDetected(
            "Your expression estimates varied between frames. Hold still for a moment and try again."
        )

    valid_frames = int(scores.shape[0])
    return {
        "status": "success",
        "expression_estimate": mood,
        "prediction_scores": {
            normalize_mood(label, aliases): float(mean_scores[index])
            for index, label in enumerate(labels)
        },
        "valid_frames": valid_frames,
        "total_frames": int(total_frames),
        "consistency": consistency,
        "consistency_label": (
            "high" if consistency >= 0.8 else "moderate" if consistency >= 0.6 else "low"
        ),
        "quality_status": "good",
        "mood": mood,
        "confidence": float(mean_scores[mood_index]),
        "samples": valid_frames,
    }
