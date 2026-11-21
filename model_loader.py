"""Load and validate the emotion model artifacts before inference."""
import hashlib
import json
from pathlib import Path

import numpy as np


def _load_labels(labels_path):
    labels = np.load(labels_path, allow_pickle=False)
    if labels.ndim != 1 or labels.size == 0:
        raise RuntimeError("The emotion label artifact must be a non-empty one-dimensional array.")

    normalized_labels = [str(label) for label in labels]
    if any(not label.strip() for label in normalized_labels):
        raise RuntimeError("The emotion label artifact contains an empty label.")
    if len(normalized_labels) != len(set(normalized_labels)):
        raise RuntimeError("The emotion label artifact contains duplicate labels.")
    return labels


def _validate_metadata(model_path, labels, metadata_path):
    metadata_path = Path(metadata_path)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("The emotion model metadata could not be read.") from error

    if not isinstance(metadata, dict):
        raise RuntimeError("The emotion model metadata must be a JSON object.")

    expected_checksum = metadata.get("model_sha256")
    if not isinstance(expected_checksum, str) or len(expected_checksum) != 64:
        raise RuntimeError("The emotion model metadata does not contain a valid SHA-256 checksum.")

    checksum = hashlib.sha256(Path(model_path).read_bytes()).hexdigest()
    if checksum != expected_checksum.lower():
        raise RuntimeError("The emotion model checksum does not match its metadata.")

    expected_labels = [str(label) for label in labels]
    if (
        metadata.get("input_dimensions") != 1020
        or metadata.get("output_labels") != expected_labels
    ):
        raise RuntimeError("The emotion model metadata does not match its labels or input dimensions.")


def load_emotion_artifacts(model_path, labels_path, metadata_path=None):
    """Load model and labels after validating the on-disk artifacts.

    Verifying the model digest before calling Keras prevents an unexpected or
    corrupted artifact from reaching the model deserializer.
    """
    model_path = Path(model_path)
    labels_path = Path(labels_path)
    labels = _load_labels(labels_path)

    if metadata_path is not None:
        _validate_metadata(model_path, labels, metadata_path)

    # Import only after artifact validation so invalid files are never passed
    # to Keras' model deserialization path.
    from keras.models import load_model

    emotion_model = load_model(model_path, compile=False)
    input_shape = emotion_model.input_shape
    output_shape = emotion_model.output_shape
    if (
        not isinstance(input_shape, (tuple, list))
        or len(input_shape) != 2
        or input_shape[-1] != 1020
        or not isinstance(output_shape, (tuple, list))
        or len(output_shape) != 2
        or output_shape[-1] != len(labels)
    ):
        raise RuntimeError(
            "The emotion model must accept 1020 landmark values and return one score per unique label."
        )

    return emotion_model, labels
