from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DefectDetail(BaseModel):
    defect_type: str
    confidence: float
    bbox: List[float]
    association_method: str = "center_containment"
    overlap_score: float = 1.0


class OnionRecord(BaseModel):
    onion_id: int
    bbox: List[float]  # [x1, y1, x2, y2]
    width_pixels: float
    height_pixels: float
    diameter_pixels: float
    area_pixels: float
    equivalent_diameter_pixels: float
    approximate_size_category: str
    physical_diameter_mm: Optional[float] = None
    rotten: bool = False
    sprout: bool = False
    double_split: bool = False
    defect_types: List[str] = Field(default_factory=list)
    defects_detail: List[DefectDetail] = Field(default_factory=list)
    confidence: float
    status: str  # "Sound" | "Defective"
    explanation: str


class SizeDistribution(BaseModel):
    large: int = 0
    medium: int = 0
    small: int = 0
    large_percent: float = 0.0
    medium_percent: float = 0.0
    small_percent: float = 0.0


class LotStatistics(BaseModel):
    total_onions: int
    sound_onions: int
    defective_onions: int
    rotten_count: int
    sprout_count: int
    double_split_count: int
    unassigned_defects: int
    defect_indicator_percent: float
    decay_indicator_percent: float
    sprout_indicator_percent: float
    double_split_indicator_percent: float
    size_distribution: SizeDistribution
    avg_approx_diameter_pixels: float
    min_approx_diameter_pixels: float
    max_approx_diameter_pixels: float
    avg_physical_diameter_mm: Optional[float] = None


class RuleCriterionResult(BaseModel):
    criterion: str
    limit: str
    observed: str
    status: str  # "PASS", "FAIL", "NOT_EVALUATED"
    details: str


class AssessmentResult(BaseModel):
    standard_id: str
    standard_name: str
    assessment_status: str
    summary: str
    evaluated_criteria: List[RuleCriterionResult] = Field(default_factory=list)
    un_evaluated_criteria: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    recommendation: str
    regulatory_disclaimer: str


class OnionGradingRecord(BaseModel):
    onion_id: int
    size_category: str
    visible_defects: List[str] = Field(default_factory=list)
    grade_category: str
    reason: str


class CategoryBreakdown(BaseModel):
    count: int = 0
    percentage: float = 0.0
    criteria: str
    observed_result: str


class GradingLotSummary(BaseModel):
    is_configured: bool = False
    status_message: str = "Grade A / URS calculation unavailable"
    unavailability_reason: Optional[str] = None
    missing_criteria: List[str] = Field(default_factory=list)
    total_onions_assessed: int = 0
    grade_a_count: int = 0
    grade_a_percentage: float = 0.0
    urs_count: int = 0
    urs_percentage: float = 0.0
    defective_count: int = 0
    defective_percentage: float = 0.0
    undersized_count: int = 0
    undersized_percentage: float = 0.0
    insufficient_data_count: int = 0
    insufficient_data_percentage: float = 0.0
    onion_gradings: List[OnionGradingRecord] = Field(default_factory=list)
    categories_breakdown: Dict[str, CategoryBreakdown] = Field(default_factory=dict)
    assessment_basis_statement: str = ""


class AnalyzeResponse(BaseModel):
    status: str
    total_onions: int
    visible_defects: int
    defect_indicator_percent: float
    size_distribution: Dict[str, int]
    onions: List[OnionRecord]
    lot_statistics: LotStatistics
    assessment: AssessmentResult
    grading: Optional[GradingLotSummary] = None
    annotated_image: Optional[str] = None
    limitations: List[str]
    memory_telemetry: Dict[str, Any]
    calibration_used: bool
    inference_time_ms: float

