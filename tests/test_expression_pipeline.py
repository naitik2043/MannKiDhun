import unittest
from types import SimpleNamespace

import numpy as np

from frame_validation import FrameQualityError, validate_frame_quality
from model_evaluation import evaluate_predictions
from prediction_aggregation import UncertainMoodDetected, aggregate_predictions


def face_landmarks(points=None):
    if points is None:
        points = [
            (0.25 + index / 2000, 0.30 + index / 3000)
            for index in range(468)
        ]
    return SimpleNamespace(
        landmark=[SimpleNamespace(x=x, y=y) for x, y in points]
    )


def textured_frame():
    pixels = np.random.default_rng(42).integers(
        80, 176, size=(160, 160, 1), dtype=np.uint8
    )
    return np.repeat(pixels, 3, axis=2)


class FrameValidationTests(unittest.TestCase):
    def test_accepts_visible_face_with_sufficient_lighting_and_detail(self):
        result = validate_frame_quality(textured_frame(), face_landmarks())
        self.assertEqual(result["quality_status"], "good")

    def test_rejects_face_that_is_too_small(self):
        points = [
            (0.45 + index / 30000, 0.45 + index / 30000)
            for index in range(468)
        ]
        with self.assertRaisesRegex(FrameQualityError, "too small"):
            validate_frame_quality(textured_frame(), face_landmarks(points))

    def test_rejects_face_outside_frame(self):
        points = [
            (-0.3 if index < 100 else 0.25 + index / 2000, 0.30 + index / 3000)
            for index in range(468)
        ]
        with self.assertRaisesRegex(FrameQualityError, "outside the frame"):
            validate_frame_quality(textured_frame(), face_landmarks(points))

    def test_rejects_dark_and_blurred_frames(self):
        with self.assertRaisesRegex(FrameQualityError, "too dark"):
            validate_frame_quality(
                np.zeros((160, 160, 3), dtype=np.uint8), face_landmarks()
            )
        with self.assertRaisesRegex(FrameQualityError, "blurry"):
            validate_frame_quality(
                np.full((160, 160, 3), 120, dtype=np.uint8), face_landmarks()
            )


class PredictionAggregationTests(unittest.TestCase):
    labels = ["happy", "neutral", "surprise", "rock", "angry", "sad"]
    aliases = {"susurprise": "surprise", "rocrock": "rock"}

    def test_reports_mean_scores_and_consistency(self):
        scores = [
            [0.8, 0.1, 0.02, 0.02, 0.03, 0.03],
            [0.8, 0.1, 0.02, 0.02, 0.03, 0.03],
            [0.8, 0.1, 0.02, 0.02, 0.03, 0.03],
            [0.1, 0.1, 0.02, 0.02, 0.03, 0.73],
            [0.1, 0.1, 0.02, 0.02, 0.03, 0.73],
        ]
        result = aggregate_predictions(scores, self.labels, self.aliases, 5)
        self.assertEqual(result["expression_estimate"], "happy")
        self.assertEqual(result["valid_frames"], 5)
        self.assertAlmostEqual(result["consistency"], 0.6)
        self.assertAlmostEqual(result["prediction_scores"]["happy"], 0.52)

    def test_rejects_excessively_inconsistent_predictions(self):
        scores = [
            [0.8, 0.1, 0.02, 0.02, 0.03, 0.03],
            [0.1, 0.1, 0.02, 0.02, 0.03, 0.73],
            [0.8, 0.1, 0.02, 0.02, 0.03, 0.03],
            [0.1, 0.1, 0.02, 0.02, 0.03, 0.73],
        ]
        with self.assertRaises(UncertainMoodDetected):
            aggregate_predictions(scores, self.labels, self.aliases, 4)

    def test_rejects_invalid_probability_distribution(self):
        with self.assertRaisesRegex(ValueError, "invalid prediction scores"):
            aggregate_predictions([[0.5] * 6], self.labels, self.aliases, 1)


class EvaluationTests(unittest.TestCase):
    def test_evaluates_only_subject_separated_held_out_test_rows(self):
        rows = [
            {
                "subject_id": "train-subject",
                "split": "train",
                "true_label": "happy",
                "predicted_label": "happy",
            },
            {
                "subject_id": "test-subject-a",
                "split": "test",
                "true_label": "happy",
                "predicted_label": "happy",
            },
            {
                "subject_id": "test-subject-b",
                "split": "test",
                "true_label": "sad",
                "predicted_label": "happy",
            },
        ]
        metrics = evaluate_predictions(rows)
        self.assertEqual(metrics["test_samples"], 2)
        self.assertEqual(metrics["test_subjects"], 2)
        self.assertEqual(metrics["accuracy"], 0.5)
        self.assertEqual(metrics["balanced_accuracy"], 0.5)
        self.assertEqual(metrics["confusion_matrix"]["sad"]["happy"], 1)

    def test_rejects_subjects_leaking_across_splits(self):
        rows = [
            {
                "subject_id": "same-person",
                "split": split,
                "true_label": "happy",
                "predicted_label": "happy",
            }
            for split in ("train", "test")
        ]
        with self.assertRaisesRegex(ValueError, "more than one data split"):
            evaluate_predictions(rows)


if __name__ == "__main__":
    unittest.main()
