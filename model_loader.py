import hashlib
import json
from pathlib import Path

import numpy as np


def load_emotion_artifacts(model_path, labels_path, metadata_path=None):
    from keras.models import load_model

    model_path = Path(model_path)
    labels_path = Path(labels_path)
    emotion_model = load_model(model_path, compile=False)
    labels = np.load(labels_path, allow_pickle=False)

    if metadata_path is not None:
        metadata_path = Path(metadata_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if metadata.get("model_sha256") != checksum:
            raise RuntimeError("The emotion model checksum does not match its metadata.")
        if (
            metadata.get("input_dimensions") != 1020
            or metadata.get("output_labels") != [str(label) for label in labels]
        ):
            raise RuntimeError("The emotion model metadata does not match its labels.")

    if (
        len(emotion_model.input_shape) != 2
        or emotion_model.input_shape[-1] != 1020
        or len(emotion_model.output_shape) != 2
        or emotion_model.output_shape[-1] != len(labels)
        or len(labels) != len(set(str(label) for label in labels))
    ):
        raise RuntimeError(
            "The emotion model must accept 1020 landmark values and return one score per unique label."
        )

    return emotion_model, labels
