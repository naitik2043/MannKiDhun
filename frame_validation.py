import cv2
import numpy as np


class FrameQualityError(ValueError):
    pass


def validate_frame_quality(image_array, face_landmarks):
    if image_array is None or image_array.ndim < 2:
        raise FrameQualityError("A usable camera frame could not be read.")

    height, width = image_array.shape[:2]
    points = np.asarray(
        [(landmark.x, landmark.y) for landmark in face_landmarks.landmark],
        dtype=np.float32,
    )
    if points.ndim != 2 or points.shape[0] < 468 or not np.isfinite(points).all():
        raise FrameQualityError(
            "Your face was only partly visible. Center your face and try again."
        )

    in_bounds = np.logical_and(points >= 0.0, points <= 1.0).all(axis=1)
    if float(np.mean(in_bounds)) < 0.95:
        raise FrameQualityError(
            "Your face was partly outside the frame. Move it into view and try again."
        )

    visible_points = points[in_bounds]
    min_x, min_y = visible_points.min(axis=0)
    max_x, max_y = visible_points.max(axis=0)
    face_width = float(max_x - min_x)
    face_height = float(max_y - min_y)
    if face_width < 0.12 or face_height < 0.12:
        raise FrameQualityError(
            "Your face looks too small. Move a little closer to the camera."
        )

    x1 = max(0, int(np.floor(min_x * width)))
    x2 = min(width, int(np.ceil(max_x * width)))
    y1 = max(0, int(np.floor(min_y * height)))
    y2 = min(height, int(np.ceil(max_y * height)))
    face_crop = image_array[y1:y2, x1:x2]
    if face_crop.size == 0:
        raise FrameQualityError(
            "Your face was only partly visible. Center your face and try again."
        )

    gray = (
        cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        if face_crop.ndim == 3
        else face_crop
    )
    brightness = float(np.mean(gray))
    if brightness < 35:
        raise FrameQualityError(
            "The image is too dark to analyze. Try a brighter, evenly lit spot."
        )
    if brightness > 220:
        raise FrameQualityError(
            "The image is overexposed. Move away from strong light and try again."
        )

    if min(gray.shape[:2]) >= 8:
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if sharpness < 8.0:
            raise FrameQualityError(
                "The image looks blurry. Hold still and try the check again."
            )

    return {"quality_status": "good"}
