from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from enum import Enum

class SDModel(BaseModel):
    title: str
    model_name: str
    hash: Optional[str]
    sha256: Optional[str]
    filename: str
    config: Optional[str]

class Sampler(BaseModel):
    name: str
    aliases: List[str] = []
    options: Dict[str, str] = {}

class LoRAModel(BaseModel):
    name: str
    alias: str
    path: str
    metadata: Dict[str, Any] = {}

class ModelFormat(Enum):
    SD15 = "sd15"
    SDXL = "sdxl"
    SD3 = "sd3"
    FLUX = "flux"
    UNKNOWN = "unknown"

class ModelInfo(BaseModel):
    name: str
    format: ModelFormat
    recommended_steps: int
    default_resolution: tuple[int, int]
    supported_resolutions: List[tuple[int, int]]
    recommended_cfg: float

class GenerateImageInput(BaseModel):
    prompt: str
    negative_prompt: str = ""
    steps: int = 25  # Increased from 4
    width: int = 1024
    height: int = 1024
    cfg_scale: float = 7.0  # Better default
    sampler_name: str = "Euler"
    seed: int = -1
    batch_size: int = 1
    distilled_cfg_scale: float = 3.5
    scheduler_name: str = "Simple"
    tiling: bool = False
    restore_faces: bool = False
    output_path: Optional[str] = None
    enforce_model_constraints: bool = True

class ProgressResponse(BaseModel):
    progress: float
    eta_relative: float
    state: Dict[str, Any]
    current_image: Optional[str]
    textinfo: Optional[str]

class GenerationResult(BaseModel):
    path: str
    parameters: str

class LoRAInfo(BaseModel):
    name: str
    filename: str
    weight: float = 1.0
    trigger_words: List[str] = []
    category: str = "general"
    description: str = ""
    metadata: Dict[str, Any] = {}

class LoRASuggestion(BaseModel):
    lora: str
    confidence: float
    reason: str

class LoRAValidation(BaseModel):
    valid: bool
    warnings: List[str] = []
    recommendations: List[str] = []