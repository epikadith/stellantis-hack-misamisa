"""Public interface for the Predictive Driver Risk Cockpit CV module.

The FastAPI backend imports this package directly and calls
``get_current_frame_result`` approximately every 200 ms.  Phase 0 provides a
schema-valid safe result; later phases replace the placeholder producer with
the webcam and signal-fusion pipeline without changing this public contract.
"""

from .calibration import CalibrationEngine, CalibrationState
from .fusion import FusionWeights, SignalFusionEngine, compute_risk
from .interface import close_pipeline, get_current_frame_result, process_camera_frame, set_context_mode, start_calibration
from .pipeline import RiskPipeline
from .schema import CONTEXT_MODES, build_result, validate_result
from .trajectory import TrajectoryAnalyzer, TrajectoryConfig

__all__ = [
    "CONTEXT_MODES",
    "CalibrationEngine",
    "CalibrationState",
    "close_pipeline",
    "compute_risk",
    "build_result",
    "get_current_frame_result",
    "process_camera_frame",
    "FusionWeights",
    "RiskPipeline",
    "set_context_mode",
    "SignalFusionEngine",
    "start_calibration",
    "TrajectoryAnalyzer",
    "TrajectoryConfig",
    "validate_result",
]
