# NudeNet Threshold Configuration

This document explains how to configure NudeNet thresholds for NSFW content detection in the Stable Diffusion MCP server.

## Overview

The NudeNet NSFW filter uses configurable thresholds to determine what body parts should be censored. Thresholds range from 0.0 (always censor) to 1.0 (never censor).

## Configuration Variables

Add these variables to your MCP.json environment section:

```json
{
  "env": {
    "NUDENET_THRESHOLD_FACE": "1.0",
    "NUDENET_THRESHOLD_BREAST_EXPOSED": "0.6", 
    "NUDENET_THRESHOLD_BREAST_COVERED": "1.0",
    "NUDENET_THRESHOLD_BUTTOCKS_EXPOSED": "0.6",
    "NUDENET_THRESHOLD_BUTTOCKS_COVERED": "1.0",
    "NUDENET_THRESHOLD_GENITALIA_EXPOSED": "0.3",
    "NUDENET_THRESHOLD_GENITALIA_COVERED": "1.0",
    "NUDENET_THRESHOLD_FEET": "1.0",
    "NUDENET_THRESHOLD_BELLY": "1.0",
    "NUDENET_THRESHOLD_ARMPITS": "1.0",
    "NUDENET_THRESHOLD_BACK": "1.0",
    "NUDENET_THRESHOLD_DEFAULT": "0.8",
		"NUDENET_EXPAND_HORIZONTAL": "1.0",
    "NUDENET_EXPAND_VERTICAL": "1.0",
    "NUDENET_FILTER_TYPE": "Variable blur",
    "NUDENET_BLUR_RADIUS": "25",
    "NUDENET_BLUR_STRENGTH_CURVE": "2",
    "NUDENET_PIXELATION_FACTOR": "15",
    "NUDENET_FILL_COLOR": "#000000",
    "NUDENET_MASK_SHAPE": "Ellipse",
    "NUDENET_MASK_BLEND_RADIUS": "10",
    "NUDENET_RECTANGLE_ROUND_RADIUS": "0",
    "NUDENET_NMS_THRESHOLD": "0.5"
  }
}
```

## Default Configuration

The default configuration allows:
- ✅ Faces (1.0) - Never censored
- ✅ Covered body parts (1.0) - Bikinis, underwear, etc.
- ✅ Non-intimate areas (1.0) - Feet, belly, armpits, back

And censors:
- 🔴 Exposed genitalia (0.3) - Highly sensitive
- 🟡 Exposed breasts/buttocks (0.6) - Moderately sensitive

## Body Part Categories

NudeNet detects 18 body part categories:

| Index | Category | Threshold Variable | Default |
|-------|----------|-------------------|---------|
| 0 | EXPOSED_ANUS | NUDENET_THRESHOLD_GENITALIA_EXPOSED | 0.3 |
| 1 | EXPOSED_ARMPITS | NUDENET_THRESHOLD_ARMPITS | 1.0 |
| 2 | COVERED_BELLY | NUDENET_THRESHOLD_BELLY | 1.0 |
| 3 | EXPOSED_BELLY | NUDENET_THRESHOLD_BELLY | 1.0 |
| 4 | COVERED_BUTTOCKS | NUDENET_THRESHOLD_BUTTOCKS_COVERED | 1.0 |
| 5 | EXPOSED_BUTTOCKS | NUDENET_THRESHOLD_BUTTOCKS_EXPOSED | 0.6 |
| 6 | FACE_F | NUDENET_THRESHOLD_FACE | 1.0 |
| 7 | FACE_M | NUDENET_THRESHOLD_FACE | 1.0 |
| 8 | COVERED_FEET | NUDENET_THRESHOLD_FEET | 1.0 |
| 9 | EXPOSED_FEET | NUDENET_THRESHOLD_FEET | 1.0 |
| 10 | COVERED_BREAST_F | NUDENET_THRESHOLD_BREAST_COVERED | 1.0 |
| 11 | EXPOSED_BREAST_F | NUDENET_THRESHOLD_BREAST_EXPOSED | 0.6 |
| 12 | COVERED_GENITALIA_F | NUDENET_THRESHOLD_GENITALIA_COVERED | 1.0 |
| 13 | EXPOSED_GENITALIA_F | NUDENET_THRESHOLD_GENITALIA_EXPOSED | 0.3 |
| 14 | EXPOSED_BREAST_M | NUDENET_THRESHOLD_BREAST_EXPOSED | 0.6 |
| 15 | EXPOSED_GENITALIA_M | NUDENET_THRESHOLD_GENITALIA_EXPOSED | 0.3 |
| 16 | COVERED_GENITALIA_M | NUDENET_THRESHOLD_GENITALIA_COVERED | 1.0 |
| 17 | EXPOSED_BACK | NUDENET_THRESHOLD_BACK | 1.0 |

## Threshold Guidelines

- **1.0** - Never censor (always allow)
- **0.8-0.9** - Rarely censor (high confidence required)
- **0.5-0.7** - Moderate censoring
- **0.3-0.4** - Aggressive censoring
- **0.0-0.2** - Always censor

## Use Cases

### Conservative (Family-Safe)
```json
"NUDENET_THRESHOLD_BREAST_EXPOSED": "0.3",
"NUDENET_THRESHOLD_BUTTOCKS_EXPOSED": "0.3",
"NUDENET_THRESHOLD_GENITALIA_EXPOSED": "0.1"
```

### Balanced (Default)
```json
"NUDENET_THRESHOLD_BREAST_EXPOSED": "0.6",
"NUDENET_THRESHOLD_BUTTOCKS_EXPOSED": "0.6", 
"NUDENET_THRESHOLD_GENITALIA_EXPOSED": "0.3"
```

### Permissive (Art/Medical)
```json
"NUDENET_THRESHOLD_BREAST_EXPOSED": "0.8",
"NUDENET_THRESHOLD_BUTTOCKS_EXPOSED": "0.8",
"NUDENET_THRESHOLD_GENITALIA_EXPOSED": "0.5"
```

## Testing Configuration

Use the test script to verify your configuration:

```bash
python test_nudenet_thresholds.py
```

This will show which thresholds are applied and test image generation with a bikini image.

## Implementation Details

The thresholds are applied in `modules/stable_diffusion/sd_client.py`:

1. Configuration loaded in MCP server: `scripts/mcp_servers/sd_mcp_server.py:43-54`
2. Passed to SDClient: `sd_mcp_server.py:84`
3. Applied in censoring: `sd_client.py:306-336`

## Troubleshooting

- **Images not being censored**: Lower threshold values (0.3-0.5)
- **Too much censoring**: Raise threshold values (0.7-1.0)
- **Faces being censored**: Set `NUDENET_THRESHOLD_FACE` to `1.0`
- **Bikinis being censored**: Set covered thresholds to `1.0`
