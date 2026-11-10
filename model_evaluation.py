import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


MODEL_LABELS = ("happy", "neutral", "surprise", "rock", "angry", "sad")


def evaluate_predictions(rows):
    subjects_by_split = defaultdict(set)
    for row in rows:
        subject = row.get("subject_id", "").strip()
        split = row.get("split", "").strip().lower()
        if not subject or split not in {"train", "validation", "test"}:
            raise ValueError(
                "Every row needs a subject_id and a train, validation, or test split."
            )
        subjects_by_split[subject].add(split)
        if row.get("true_label") not in MODEL_LABELS:
            raise ValueError(f"Unknown true label: {row.get('true_label')!r}")
        if row.get("predicted_label") not in MODEL_LABELS:
            raise ValueError(f"Unknown predicted label: {row.get('predicted_label')!r}")

    if any(len(splits) > 1 for splits in subjects_by_split.values()):
        raise ValueError("A subject appears in more than one data split.")

    test_rows = [row for row in rows if row["split"].strip().lower() == "test"]
    if not test_rows:
        raise ValueError("The input contains no held-out test rows.")

    confusion = {label: {predicted: 0 for predicted in MODEL_LABELS} for label in MODEL_LABELS}
    for row in test_rows:
        confusion[row["true_label"]][row["predicted_label"]] += 1

    total = len(test_rows)
    correct = sum(confusion[label][label] for label in MODEL_LABELS)
    per_class = {}
    supported_recalls = []
    precisions = []
    weighted_f1 = 0.0
    weighted_precision = 0.0
    weighted_recall = 0.0
    macro_f1 = 0.0
    macro_precision = 0.0
    macro_recall = 0.0
    for label in MODEL_LABELS:
        true_positive = confusion[label][label]
        support = sum(confusion[label].values())
        predicted_count = sum(confusion[actual][label] for actual in MODEL_LABELS)
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / support if support else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
        if support:
            supported_recalls.append(recall)
        precisions.append(precision)
        macro_precision += precision / len(MODEL_LABELS)
        macro_recall += recall / len(MODEL_LABELS)
        macro_f1 += f1 / len(MODEL_LABELS)
        weighted_precision += precision * support / total
        weighted_recall += recall * support / total
        weighted_f1 += f1 * support / total

    return {
        "test_samples": total,
        "test_subjects": len(
            {row["subject_id"].strip() for row in test_rows}
        ),
        "accuracy": correct / total,
        "balanced_accuracy": sum(supported_recalls) / len(supported_recalls),
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "weighted_precision": weighted_precision,
        "weighted_recall": weighted_recall,
        "weighted_f1": weighted_f1,
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate predictions from a subject-separated held-out test split."
    )
    parser.add_argument("--predictions", required=True, type=Path)
    arguments = parser.parse_args()
    with arguments.predictions.open(encoding="utf-8-sig", newline="") as predictions_file:
        rows = list(csv.DictReader(predictions_file))
    print(json.dumps(evaluate_predictions(rows), indent=2))


if __name__ == "__main__":
    main()
