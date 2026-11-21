import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from model_loader import load_emotion_artifacts


class ModelArtifactLoaderTests(unittest.TestCase):
    labels = ["happy", "neutral", "surprise", "rock", "angry", "sad"]

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.model_path = self.root / "model.h5"
        self.labels_path = self.root / "labels.npy"
        self.metadata_path = self.root / "model_metadata.json"
        self.model_bytes = b"test-model-artifact"
        self.model_path.write_bytes(self.model_bytes)
        np.save(self.labels_path, np.asarray(self.labels, dtype="<U10"))
        self.write_metadata()

    def tearDown(self):
        self.directory.cleanup()

    def write_metadata(self, **overrides):
        metadata = {
            "input_dimensions": 1020,
            "output_labels": list(self.labels),
            "model_sha256": hashlib.sha256(self.model_bytes).hexdigest(),
        }
        metadata.update(overrides)
        self.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    @staticmethod
    def valid_model():
        return SimpleNamespace(input_shape=(None, 1020), output_shape=(None, 6))

    def test_loads_model_after_checksum_and_metadata_validation(self):
        with patch("keras.models.load_model", return_value=self.valid_model()) as load_model:
            model, labels = load_emotion_artifacts(
                self.model_path, self.labels_path, self.metadata_path
            )

        load_model.assert_called_once_with(self.model_path, compile=False)
        self.assertEqual(model.input_shape, (None, 1020))
        self.assertEqual(labels.tolist(), self.labels)

    def test_rejects_checksum_mismatch_before_model_deserialization(self):
        self.model_path.write_bytes(b"unexpected-model-artifact")

        with patch("keras.models.load_model") as load_model:
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                load_emotion_artifacts(
                    self.model_path, self.labels_path, self.metadata_path
                )

        load_model.assert_not_called()

    def test_rejects_metadata_label_mismatch_before_deserialization(self):
        self.write_metadata(output_labels=["unexpected-label"])

        with patch("keras.models.load_model") as load_model:
            with self.assertRaisesRegex(RuntimeError, "metadata"):
                load_emotion_artifacts(
                    self.model_path, self.labels_path, self.metadata_path
                )

        load_model.assert_not_called()

    def test_rejects_duplicate_labels_before_deserialization(self):
        np.save(self.labels_path, np.asarray(["happy", "happy"], dtype="<U10"))

        with patch("keras.models.load_model") as load_model:
            with self.assertRaisesRegex(RuntimeError, "duplicate labels"):
                load_emotion_artifacts(
                    self.model_path, self.labels_path, self.metadata_path
                )

        load_model.assert_not_called()

    def test_rejects_model_with_incompatible_input_shape(self):
        incompatible_model = SimpleNamespace(
            input_shape=(None, 48, 48), output_shape=(None, 6)
        )
        with patch("keras.models.load_model", return_value=incompatible_model):
            with self.assertRaisesRegex(RuntimeError, "1020 landmark values"):
                load_emotion_artifacts(
                    self.model_path, self.labels_path, self.metadata_path
                )


if __name__ == "__main__":
    unittest.main()
