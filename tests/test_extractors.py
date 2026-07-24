"""Synthetic landmark tests for Phase 4 signal extractors."""

from __future__ import annotations

from importlib.util import find_spec
import unittest

from cv.hand_zone import HandZone, classify_hand_zone, classify_hands, hand_zone_score
from cv.head_pose import head_pose_risk
from cv.perclos import PerclosExtractor, eye_aspect_ratio
from cv.yawn import YawnExtractor, mouth_aspect_ratio, yawn_score


OPEN_EYE = ((0.0, 0.0), (1.0, 0.5), (3.0, 0.5), (4.0, 0.0), (3.0, -0.5), (1.0, -0.5))
CLOSED_EYE = ((0.0, 0.0), (1.0, 0.1), (3.0, 0.1), (4.0, 0.0), (3.0, -0.1), (1.0, -0.1))


def _hand(wrist: tuple[float, float], index_tip: tuple[float, float]) -> list[tuple[float, float]]:
    landmarks = [(0.0, 0.0)] * 9
    landmarks[0] = wrist
    landmarks[8] = index_tip
    return landmarks


class ExtractorTests(unittest.TestCase):
    def test_ear_and_rolling_perclos_with_synthetic_eye_landmarks(self) -> None:
        self.assertAlmostEqual(eye_aspect_ratio(OPEN_EYE), 0.25)
        self.assertAlmostEqual(eye_aspect_ratio(CLOSED_EYE), 0.05)

        extractor = PerclosExtractor(ear_closed_threshold=0.21, window_seconds=10.0)
        self.assertEqual(extractor.push_landmarks(0.0, OPEN_EYE, OPEN_EYE), 0.0)
        self.assertEqual(extractor.push_landmarks(1.0, CLOSED_EYE, CLOSED_EYE), 50.0)
        self.assertAlmostEqual(extractor.push_landmarks(2.0, CLOSED_EYE, CLOSED_EYE), 200.0 / 3.0)

    def test_perclos_rejects_degenerate_landmarks_and_time_reversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "zero horizontal"):
            eye_aspect_ratio(((0.0, 0.0),) * 6)
        extractor = PerclosExtractor()
        extractor.push_ear(1.0, 0.3)
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            extractor.push_ear(1.0, 0.1)

    def test_head_pose_risk_maps_known_angle_cases(self) -> None:
        self.assertEqual(head_pose_risk(0.0, 0.0), 0.0)
        self.assertEqual(head_pose_risk(10.0, 0.0), 50.0)
        self.assertEqual(head_pose_risk(0.0, 15.0), 100.0)
        self.assertEqual(head_pose_risk(-50.0, 0.0), 100.0)
        with self.assertRaisesRegex(ValueError, "finite"):
            head_pose_risk(float("nan"), 0.0)

    @unittest.skipUnless(find_spec("cv2") and find_spec("numpy"), "OpenCV and NumPy are not installed")
    def test_solve_pnp_recovers_known_synthetic_head_pose(self) -> None:
        import cv2
        import numpy as np

        from cv.head_pose import estimate_head_pose

        model_points = np.array(
            [
                (0.0, 0.0, 0.0),
                (0.0, -330.0, -65.0),
                (-225.0, 170.0, -135.0),
                (225.0, 170.0, -135.0),
                (-150.0, -150.0, -125.0),
                (150.0, -150.0, -125.0),
            ],
            dtype="double",
        )
        width, height = 640, 480
        focal_length = float(width)
        camera_matrix = np.array(
            [(focal_length, 0.0, width / 2.0), (0.0, focal_length, height / 2.0), (0.0, 0.0, 1.0)],
            dtype="double",
        )
        expected_pitch, expected_yaw = 8.0, 12.0
        pitch_radians, yaw_radians = np.deg2rad((expected_pitch, expected_yaw))
        rotation_x = np.array(
            [[1.0, 0.0, 0.0], [0.0, np.cos(pitch_radians), -np.sin(pitch_radians)], [0.0, np.sin(pitch_radians), np.cos(pitch_radians)]],
        )
        rotation_y = np.array(
            [[np.cos(yaw_radians), 0.0, np.sin(yaw_radians)], [0.0, 1.0, 0.0], [-np.sin(yaw_radians), 0.0, np.cos(yaw_radians)]],
        )
        rotation_vector, _ = cv2.Rodrigues(rotation_y @ rotation_x)
        projected, _ = cv2.projectPoints(
            model_points,
            rotation_vector,
            np.array((0.0, 0.0, 1000.0)),
            camera_matrix,
            np.zeros((4, 1)),
        )
        landmarks = {
            index: (float(point[0][0] / width), float(point[0][1] / height))
            for index, point in zip((1, 152, 33, 263, 61, 291), projected)
        }

        yaw, pitch = estimate_head_pose(landmarks, width, height)
        self.assertAlmostEqual(yaw, expected_yaw, places=5)
        self.assertAlmostEqual(pitch, expected_pitch, places=5)

    def test_hand_zone_classification_and_highest_risk_selection(self) -> None:
        on_wheel = _hand((0.5, 0.78), (0.8, 0.8))
        off_wheel = _hand((0.05, 0.2), (0.1, 0.2))
        phone = _hand((0.05, 0.8), (0.51, 0.31))
        face_center = (0.5, 0.3)

        self.assertEqual(classify_hand_zone(on_wheel, face_center=face_center), HandZone.ON_WHEEL)
        self.assertEqual(classify_hand_zone(off_wheel, face_center=face_center), HandZone.OFF_WHEEL)
        self.assertEqual(classify_hand_zone(phone, face_center=face_center), HandZone.PHONE_NEAR_FACE)
        self.assertEqual(classify_hands([], face_center=face_center), (HandZone.NOT_DETECTED, 0.0))
        self.assertEqual(classify_hands([on_wheel, phone], face_center=face_center), (HandZone.PHONE_NEAR_FACE, 100.0))
        self.assertEqual(hand_zone_score(HandZone.OFF_WHEEL), 60.0)

    def test_mar_and_yawn_score_from_synthetic_mouth_landmarks(self) -> None:
        self.assertAlmostEqual(mouth_aspect_ratio((0.5, 0.4), (0.5, 0.6), (0.0, 0.5), (1.0, 0.5)), 0.2)
        self.assertEqual(yawn_score(0.2, threshold=0.6), 0.0)
        self.assertEqual(yawn_score(0.9, threshold=0.6), 100.0)
        extractor = YawnExtractor(threshold=0.6)
        self.assertEqual(extractor.push_landmarks((0.5, 0.1), (0.5, 1.0), (0.0, 0.5), (1.0, 0.5)), 100.0)
        with self.assertRaisesRegex(ValueError, "zero width"):
            mouth_aspect_ratio((0.0, 0.0), (0.0, 1.0), (0.5, 0.5), (0.5, 0.5))


if __name__ == "__main__":
    unittest.main()
