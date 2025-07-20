import httpx
import json
import base64
import uuid
import os
import logging
from typing import List, Dict, Any, Optional
from .models import SDModel, Sampler, LoRAModel, GenerateImageInput, ProgressResponse, GenerationResult, ModelFormat, ModelInfo
from .auth_manager import AuthManager

logger = logging.getLogger(__name__)

class SDClient:
    def __init__(self, base_url: str = "https://localhost:7860", auth_manager: Optional[AuthManager] = None, nudenet_config: Optional[Dict] = None):
        self.base_url = base_url.rstrip('/')
        self.auth_manager = auth_manager
        self._authenticated = False
        self.nudenet_config = nudenet_config or {}
        
    async def _create_authenticated_client(self, **kwargs) -> httpx.AsyncClient:
        """Create an authenticated HTTP client"""
        if self.auth_manager:
            return await self.auth_manager.create_authenticated_client("sd_webui", **kwargs)
        else:
            return httpx.AsyncClient(**kwargs)
    
    async def get_models(self) -> List[SDModel]:
        """Get available checkpoint models"""
        async with await self._create_authenticated_client() as client:
            response = await client.get(f"{self.base_url}/sdapi/v1/sd-models")
            response.raise_for_status()
            models_data = response.json()
            return [SDModel(**model) for model in models_data]
    
    async def get_samplers(self) -> List[Sampler]:
        """Get available samplers"""
        async with await self._create_authenticated_client() as client:
            response = await client.get(f"{self.base_url}/sdapi/v1/samplers")
            response.raise_for_status()
            samplers_data = response.json()
            return [Sampler(**sampler) for sampler in samplers_data]
    
    async def get_loras(self) -> List[LoRAModel]:
        """Get available LoRA models"""
        async with await self._create_authenticated_client() as client:
            response = await client.get(f"{self.base_url}/sdapi/v1/loras")
            response.raise_for_status()
            loras_data = response.json()
            return [LoRAModel(**lora) for lora in loras_data]
    
    async def get_progress(self, skip_current_image: bool = False) -> ProgressResponse:
        """Get current generation progress"""
        async with await self._create_authenticated_client() as client:
            params = {"skip_current_image": str(skip_current_image).lower()}
            response = await client.get(f"{self.base_url}/sdapi/v1/progress", params=params)
            response.raise_for_status()
            return ProgressResponse(**response.json())
    
    def _detect_model_format(self, model_name: str) -> ModelFormat:
        """Detect model format from model name"""
        model_lower = model_name.lower()
        
        if "xl" in model_lower or "sdxl" in model_lower:
            return ModelFormat.SDXL
        elif "sd3" in model_lower or "sd_3" in model_lower:
            return ModelFormat.SD3
        elif "flux" in model_lower:
            return ModelFormat.FLUX
        elif "1.5" in model_lower or "sd15" in model_lower or "v1-5" in model_lower:
            return ModelFormat.SD15
        else:
            # Default heuristic: check model size patterns
            if any(x in model_lower for x in ["base", "realistic", "anime", "photorealistic"]):
                return ModelFormat.SD15
            return ModelFormat.UNKNOWN
    
    def _get_model_constraints(self, model_format: ModelFormat) -> ModelInfo:
        """Get model-specific constraints and recommendations"""
        constraints = {
            ModelFormat.SD15: ModelInfo(
                name="Stable Diffusion 1.5",
                format=ModelFormat.SD15,
                recommended_steps=25,
                default_resolution=(512, 512),
                supported_resolutions=[
                    (512, 512), (512, 768), (768, 512),
                    (640, 640), (512, 896), (896, 512)
                ],
                recommended_cfg=7.0
            ),
            ModelFormat.SDXL: ModelInfo(
                name="Stable Diffusion XL",
                format=ModelFormat.SDXL,
                recommended_steps=30,
                default_resolution=(1024, 1024),
                supported_resolutions=[
                    (1024, 1024), (1152, 896), (896, 1152),
                    (1216, 832), (832, 1216), (1344, 768), (768, 1344)
                ],
                recommended_cfg=8.0
            ),
            ModelFormat.SD3: ModelInfo(
                name="Stable Diffusion 3",
                format=ModelFormat.SD3,
                recommended_steps=28,
                default_resolution=(1024, 1024),
                supported_resolutions=[
                    (1024, 1024), (1152, 896), (896, 1152),
                    (1216, 832), (832, 1216), (1536, 640), (640, 1536)
                ],
                recommended_cfg=5.0
            ),
            ModelFormat.FLUX: ModelInfo(
                name="Flux",
                format=ModelFormat.FLUX,
                recommended_steps=20,
                default_resolution=(1024, 1024),
                supported_resolutions=[
                    (1024, 1024), (1152, 896), (896, 1152),
                    (1344, 768), (768, 1344)
                ],
                recommended_cfg=1.0
            )
        }
        
        return constraints.get(model_format, constraints[ModelFormat.SD15])
    
    async def validate_and_adjust_params(self, params: GenerateImageInput, target_model: Optional[str] = None) -> GenerateImageInput:
        """Validate and adjust parameters based on current model"""
        if not params.enforce_model_constraints:
            return params
        
        # Get current model if not specified
        if not target_model:
            current_model = await self.get_current_model()
            target_model = current_model["model_name"]
        
        # Detect model format and get constraints
        model_format = self._detect_model_format(target_model)
        constraints = self._get_model_constraints(model_format)
        
        print(f"[SD] Model: {target_model}")
        print(f"[SD] Detected format: {model_format.value}")
        print(f"[SD] Applying constraints: {constraints.name}")
        
        # Create adjusted parameters
        adjusted_params = params.model_copy()
        
        # Adjust steps if using default low value
        if params.steps <= 10:  # Likely using default low value
            adjusted_params.steps = constraints.recommended_steps
            print(f"[SD] Steps adjusted: {params.steps} → {adjusted_params.steps}")
        
        # Adjust CFG scale for model type
        if model_format == ModelFormat.FLUX and params.cfg_scale > 2.0:
            adjusted_params.cfg_scale = constraints.recommended_cfg
            print(f"[SD] CFG adjusted for Flux: {params.cfg_scale} → {adjusted_params.cfg_scale}")
        elif model_format in [ModelFormat.SD3] and params.cfg_scale > 6.0:
            adjusted_params.cfg_scale = constraints.recommended_cfg
            print(f"[SD] CFG adjusted for SD3: {params.cfg_scale} → {adjusted_params.cfg_scale}")
        
        # Validate resolution
        current_res = (params.width, params.height)
        if current_res not in constraints.supported_resolutions:
            # Find closest supported resolution
            def res_distance(res):
                return abs(res[0] - params.width) + abs(res[1] - params.height)
            
            closest_res = min(constraints.supported_resolutions, key=res_distance)
            adjusted_params.width, adjusted_params.height = closest_res
            print(f"[SD] Resolution adjusted: {current_res} → {closest_res}")
        
        return adjusted_params
    
    async def generate_image(self, params: GenerateImageInput) -> List[GenerationResult]:
        """Generate image using txt2img API with model validation and proper parameters"""
        # Validate and adjust parameters based on current model
        adjusted_params = await self.validate_and_adjust_params(params)
        
        output_path = adjusted_params.output_path or "/tmp/images"
        os.makedirs(output_path, exist_ok=True)
        
        payload = {
            "prompt": adjusted_params.prompt,
            "negative_prompt": adjusted_params.negative_prompt,
            "steps": adjusted_params.steps,
            "width": adjusted_params.width,
            "height": adjusted_params.height,
            "cfg_scale": adjusted_params.cfg_scale,
            "sampler_name": adjusted_params.sampler_name,
            "seed": adjusted_params.seed,
            "n_iter": adjusted_params.batch_size,
            "tiling": adjusted_params.tiling,
            "restore_faces": adjusted_params.restore_faces,
            "distilled_cfg_scale": adjusted_params.distilled_cfg_scale,
            "scheduler": adjusted_params.scheduler_name,
        }
        
        async with await self._create_authenticated_client(timeout=300.0) as client:
            print(f"[SD] Starting image generation: {adjusted_params.prompt[:50]}...")
            print(f"[SD] Parameters: {adjusted_params.width}x{adjusted_params.height}, {adjusted_params.steps} steps, CFG {adjusted_params.cfg_scale}")
            
            # Start generation
            response = await client.post(f"{self.base_url}/sdapi/v1/txt2img", json=payload)
            response.raise_for_status()
            data = response.json()
            
            print(f"[SD] Generation response status: {response.status_code}")
            print(f"[SD] Images returned: {len(data.get('images', []))}")
            
            if not data.get("images"):
                raise ValueError("No images returned from server")
            
            results = []
            for i, image_data in enumerate(data["images"]):
                print(f"[SD] Processing image {i+1}/{len(data['images'])}")
                
                # Handle base64 data
                if image_data.startswith("data:image/"):
                    base64_data = image_data.split(",")[1]
                else:
                    base64_data = image_data
                
                try:
                    image_bytes = base64.b64decode(base64_data)
                    print(f"[SD] Image {i+1} decoded, size: {len(image_bytes)} bytes")
                except Exception as e:
                    print(f"[SD] Failed to decode image {i+1}: {e}")
                    continue
                
                # Get PNG info
                try:
                    png_info_resp = await client.post(
                        f"{self.base_url}/sdapi/v1/png-info", 
                        json={"image": f"data:image/png;base64,{base64_data}"}
                    )
                    png_info = png_info_resp.json().get("info", "")
                except Exception as e:
                    print(f"[SD] Failed to get PNG info: {e}")
                    png_info = ""
                
                # Save image
                filename = f"sd_{uuid.uuid4().hex}.png"
                save_path = os.path.join(output_path, filename)
                
                try:
                    with open(save_path, "wb") as f:
                        f.write(image_bytes)
                    print(f"[SD] Image saved: {save_path}")
                    
                    # Include generation parameters in result
                    gen_params = f"Model validation applied. Original steps: {params.steps}, Used steps: {adjusted_params.steps}. {png_info}"
                    results.append(GenerationResult(path=save_path, parameters=gen_params))
                except Exception as e:
                    print(f"[SD] Failed to save image: {e}")
                    continue
            
            print(f"[SD] Generation complete. {len(results)} images saved.")
            return results
    
    async def get_current_model(self) -> Dict[str, Any]:
        """Get currently loaded model"""
        async with await self._create_authenticated_client() as client:
            response = await client.get(f"{self.base_url}/sdapi/v1/options")
            response.raise_for_status()
            options = response.json()
            return {
                "model_name": options.get("sd_model_checkpoint", "Unknown"),
                "model_hash": options.get("sd_checkpoint_hash", "Unknown"),
                "model_sha256": options.get("sd_checkpoint_sha256", "Unknown")
            }
    
    async def load_checkpoint(self, model_name: str) -> Dict[str, Any]:
        """Load a specific checkpoint model"""
        async with await self._create_authenticated_client() as client:
            # First, get current options
            options_response = await client.get(f"{self.base_url}/sdapi/v1/options")
            options_response.raise_for_status()
            current_options = options_response.json()
            
            # Update the model checkpoint
            updated_options = {
                "sd_model_checkpoint": model_name
            }
            
            # Set the new options
            response = await client.post(f"{self.base_url}/sdapi/v1/options", json=updated_options)
            response.raise_for_status()
            
            # Verify the change
            new_model = await self.get_current_model()
            return {
                "success": True,
                "previous_model": current_options.get("sd_model_checkpoint", "Unknown"),
                "new_model": new_model["model_name"],
                "model_hash": new_model["model_hash"]
            }
    
    async def refresh_checkpoints(self) -> Dict[str, Any]:
        """Refresh the list of available checkpoints"""
        async with await self._create_authenticated_client() as client:
            response = await client.post(f"{self.base_url}/sdapi/v1/refresh-checkpoints")
            response.raise_for_status()
            return {"success": True, "message": "Checkpoints refreshed"}
    
    def _build_nudenet_thresholds(self) -> List[float]:
        """Build NudeNet thresholds array based on exact label order
        
        Based on actual NudeNet label order:
        0: Female_genitalia_covered, 1: Face_female, 2: Buttocks_exposed, 3: Female_breast_exposed,
        4: Female_genitalia_exposed, 5: Male_breast_exposed, 6: Anus_exposed, 7: Feet_exposed,
        8: Belly_covered, 9: Feet_covered, 10: Armpits_covered, 11: Armpits_exposed,
        12: Face_male, 13: Belly_exposed, 14: Male_genitalia_exposed, 15: Anus_covered,
        16: Female_breast_covered, 17: Buttocks_covered
        """
        # Helper function to safely convert to float
        def safe_float(value, default: float) -> float:
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        # Map to correct order based on actual NudeNet labels
        return [
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_GENITALIA_COVERED", 1.0), 1.0),    # 0: Female_genitalia_covered
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_FACE", 1.0), 1.0),                 # 1: Face_female
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_BUTTOCKS_EXPOSED", 0.1), 0.1),     # 2: Buttocks_exposed
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_BREAST_EXPOSED", 0.1), 0.1),       # 3: Female_breast_exposed
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_GENITALIA_EXPOSED", 0.1), 0.1),    # 4: Female_genitalia_exposed
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_BREAST_EXPOSED", 0.1), 0.1),       # 5: Male_breast_exposed  
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_GENITALIA_EXPOSED", 0.1), 0.1),    # 6: Anus_exposed
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_FEET", 1.0), 1.0),                 # 7: Feet_exposed
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_BELLY", 1.0), 1.0),                # 8: Belly_covered
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_FEET", 1.0), 1.0),                 # 9: Feet_covered
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_ARMPITS", 1.0), 1.0),              # 10: Armpits_covered
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_ARMPITS", 1.0), 1.0),              # 11: Armpits_exposed
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_FACE", 1.0), 1.0),                 # 12: Face_male
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_BELLY", 1.0), 1.0),                # 13: Belly_exposed
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_GENITALIA_EXPOSED", 0.1), 0.1),    # 14: Male_genitalia_exposed
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_GENITALIA_COVERED", 1.0), 1.0),    # 15: Anus_covered
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_BREAST_COVERED", 1.0), 1.0),       # 16: Female_breast_covered
            safe_float(self.nudenet_config.get("NUDENET_THRESHOLD_BUTTOCKS_COVERED", 1.0), 1.0),     # 17: Buttocks_covered
        ]

    def _build_nudenet_expand_arrays(self) -> tuple[List[float], List[float]]:
        """Build NudeNet expand_horizontal and expand_vertical arrays based on configuration"""
        # Helper function to safely convert to float
        def safe_float(value, default: float) -> float:
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        expand_h = safe_float(self.nudenet_config.get("NUDENET_EXPAND_HORIZONTAL", 1.0), 1.0)
        expand_v = safe_float(self.nudenet_config.get("NUDENET_EXPAND_VERTICAL", 1.0), 1.0)
        
        # Create arrays of 18 elements for all body part categories
        expand_horizontal = [expand_h] * 18
        expand_vertical = [expand_v] * 18
        
        return expand_horizontal, expand_vertical

    async def nudenet_censor(self, image_path: str, save_original: bool = True) -> Dict[str, Any]:
        """Use NudeNet extension to censor NSFW content in images"""
        if not os.path.exists(image_path):
            return {"success": False, "error": "Image file not found"}
        
        try:
            # Read image file
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Convert to base64 string (without data URL prefix)
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Build configurable thresholds and expand arrays
            thresholds = self._build_nudenet_thresholds()
            expand_horizontal, expand_vertical = self._build_nudenet_expand_arrays()
            
            # Helper functions for safe type conversion
            def safe_int(value, default: int) -> int:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default
            
            def safe_float(value, default: float) -> float:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            # Build complete payload with all configuration options
            payload = {
                "input_image": image_b64,
                "enable_nudenet": True,
                "output_mask": True,
                "filter_type": self.nudenet_config.get("NUDENET_FILTER_TYPE", "Variable blur"),
                "blur_radius": safe_int(self.nudenet_config.get("NUDENET_BLUR_RADIUS", 10), 10),
                "blur_strength_curve": safe_int(self.nudenet_config.get("NUDENET_BLUR_STRENGTH_CURVE", 3), 3),
                "pixelation_factor": safe_int(self.nudenet_config.get("NUDENET_PIXELATION_FACTOR", 5), 5),
                "fill_color": self.nudenet_config.get("NUDENET_FILL_COLOR", "#000000"),
                "mask_shape": self.nudenet_config.get("NUDENET_MASK_SHAPE", "Ellipse"),
                "mask_blend_radius": safe_int(self.nudenet_config.get("NUDENET_MASK_BLEND_RADIUS", 10), 10),
                "rectangle_round_radius": safe_int(self.nudenet_config.get("NUDENET_RECTANGLE_ROUND_RADIUS", 0), 0),
                "nms_threshold": safe_float(self.nudenet_config.get("NUDENET_NMS_THRESHOLD", 0.5), 0.5),
                "thresholds": thresholds,
                "expand_horizontal": expand_horizontal,
                "expand_vertical": expand_vertical
            }
            
            # Log configuration for debugging
            print(f"[NudeNet] Filter type: {payload['filter_type']}")
            print(f"[NudeNet] Blur radius: {payload['blur_radius']}")
            print(f"[NudeNet] Mask shape: {payload['mask_shape']}")
            print(f"[NudeNet] Using custom thresholds: {[round(t, 2) for t in thresholds]}")
            print(f"[NudeNet] Expand H/V: {expand_horizontal[0]}/{expand_vertical[0]}")
            
            async with await self._create_authenticated_client(timeout=60.0) as client:
                # First check if endpoint exists
                try:
                    response = await client.post(f"{self.base_url}/nudenet/censor", json=payload)
                    
                    # Log response details for debugging
                    print(f"[NudeNet] Status: {response.status_code}")
                    print(f"[NudeNet] Headers: {dict(response.headers)}")
                    
                    if response.status_code == 404:
                        return {
                            "success": False,
                            "error": "NudeNet extension not available at /nudenet/censor endpoint"
                        }
                    
                    if response.status_code == 500:
                        error_text = response.text[:500]
                        print(f"[NudeNet] 500 Error response: {error_text}")
                        return {
                            "success": False,
                            "error": f"NudeNet server error (500): {error_text}"
                        }
                    
                    response.raise_for_status()
                    
                    try:
                        result = response.json()
                        print(f"[NudeNet] Response: {result}")
                    except json.JSONDecodeError:
                        return {
                            "success": False,
                            "error": f"Invalid JSON response from NudeNet: {response.text[:200]}"
                        }
                    
                    # NudeNet API returns 'image' (censored) and 'mask' fields
                    censored_image_b64 = result.get("image", "")
                    detection_mask_b64 = result.get("mask", "")
                    
                    # Determine if NSFW content was detected and censored
                    has_censored_image = bool(censored_image_b64 and censored_image_b64 != "")
                    has_detection_mask = bool(detection_mask_b64 and detection_mask_b64 != "")
                    has_nsfw = has_censored_image or has_detection_mask
                    
                    censored_image_path = None
                    original_image_path = None
                    mask_image_path = None
                    
                    # Save images if we have results
                    if save_original or has_censored_image:
                        output_dir = os.getenv("IMAGE_OUT_PATH", "/tmp/images")
                        os.makedirs(output_dir, exist_ok=True)
                        
                        # Save original image if requested
                        if save_original:
                            original_filename = f"nudenet_original_{uuid.uuid4().hex}.png"
                            original_image_path = os.path.join(output_dir, original_filename)
                            with open(original_image_path, 'wb') as f:
                                f.write(base64.b64decode(image_b64))
                            print(f"[NudeNet] Original saved: {original_image_path}")
                        
                        # Save censored image if we have one
                        if has_censored_image:
                            censored_filename = f"nudenet_censored_{uuid.uuid4().hex}.png"
                            censored_image_path = os.path.join(output_dir, censored_filename)
                            with open(censored_image_path, 'wb') as f:
                                f.write(base64.b64decode(censored_image_b64))
                            print(f"[NudeNet] Censored saved: {censored_image_path}")
                        
                        # Save detection mask if we have one
                        if has_detection_mask:
                            mask_filename = f"nudenet_mask_{uuid.uuid4().hex}.png"
                            mask_image_path = os.path.join(output_dir, mask_filename)
                            with open(mask_image_path, 'wb') as f:
                                f.write(base64.b64decode(detection_mask_b64))
                            print(f"[NudeNet] Mask saved: {mask_image_path}")
                    
                    return {
                        "success": True,
                        "has_nsfw": has_nsfw,
                        "censored_image": censored_image_path,
                        "original_image": original_image_path,
                        "detection_mask": mask_image_path,
                        "censored_image_b64": censored_image_b64 if has_censored_image else None,
                        "original_image_b64": image_b64,
                        "detection_mask_b64": detection_mask_b64 if has_detection_mask else None,
                        "detection_classes": result.get("detection_classes", []),
                        "confidence_scores": result.get("confidence_scores", [])
                    }
                    
                except httpx.HTTPStatusError as e:
                    return {
                        "success": False,
                        "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"NudeNet request failed: {str(e)}"
            }
    
    async def get_supported_resolutions(self) -> List[Dict[str, int]]:
        """Get supported resolutions for image generation"""
        return [
            {"width": 1024, "height": 1024},
            {"width": 1152, "height": 896},
            {"width": 896, "height": 1152},
            {"width": 1216, "height": 832},
            {"width": 832, "height": 1216},
            {"width": 1344, "height": 768},
            {"width": 768, "height": 1344},
            {"width": 1536, "height": 640},
            {"width": 640, "height": 1536},
        ]