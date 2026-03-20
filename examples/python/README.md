# Movix QC SDK - Usage Example

This example demonstrates a complete quality control workflow using the Movix QC SDK.

## What It Does

The script performs a full QC analysis:

1. Creates a case with upper and lower STL files
2. Runs data validation and verifies results
3. Runs occlusion, holes detection, and scan integrity in parallel
4. Generates a summary and viewer link
5. Displays results and viewer URL

## Prerequisites

- Python 3.11 or higher
- Movix QC API credentials (configured for staging environment)
- Upper and lower STL files for testing

## Setup

### 1. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Add Your STL Files

Place your test files in this directory:
- `upper.stl` - Upper jaw STL file
- `lower.stl` - Lower jaw STL file

### 4. Configure Credentials

Edit `main.py` and replace the placeholder values:

```python
client = Client(
    api_url="https://api-staging.movixtech.com",  # Your staging API URL
    username="your-email@example.com",             # Your email address
    password="your-password",                      # Your password
    timeout=30,
    user_agent="Movix/1.2 (+support@movixtech.com)",
    occlusion_threshold_mm=0.2,                    # Occlusion threshold (default: 0.0mm)
    occlusion_threshold_gap_mm=0.15,               # Gap threshold (default: 0.0mm)
    holes_threshold_area_mm=10.0,                  # Holes threshold (default: 0.0mm²)
)
```

#### Threshold Configuration

**Important**: Thresholds default to `0.0`, meaning all detected issues will be reported. You should set appropriate threshold values based on your quality requirements.

You can configure quality check thresholds in three ways (in order of precedence):

1. **Method parameters** (highest priority - overrides client and environment settings):
   ```python
   client.tasks.create_occlusion(case_id, threshold_mm=0.3, threshold_gap_mm=0.15)
   client.tasks.create_holes(case_id, threshold_area_mm=15.0, crown_dilation_mm=0.0)
   client.tasks.create_scan_integrity(case_id, exclude_crowns=[18, 28, 38, 48])
   ```

2. **Client initialization** (overrides environment variables):
   ```python
   client = Client(
       ...,
       occlusion_threshold_mm=0.2,
       occlusion_threshold_gap_mm=0.15,
       holes_threshold_area_mm=10.0,
   )
   ```

3. **Environment variables** (lowest priority):
   ```bash
   export MOVIX_QC_OCCLUSION_THRESHOLD_MM=0.2
   export MOVIX_QC_OCCLUSION_THRESHOLD_GAP_MM=0.15
   export MOVIX_QC_HOLES_THRESHOLD_AREA_MM=10.0
   ```

**Parameter Meanings**:
- `occlusion_threshold_mm`: Minimum penetration depth in millimeters to flag as hyperocclusion. Set to `0.0` to detect all occlusions.
- `occlusion_threshold_gap_mm`: Gap threshold in millimeters for open-contact detection. Set to `0.0` to detect all gaps.
- `holes_threshold_area_mm`: Minimum hole area in mm² to include in results. Set to `0.0` to detect all holes regardless of size.
- `crown_dilation_mm`: Crown dilation distance in mm for hole detection (optional, method parameter only).
- `exclude_crowns`: List of FDI tooth numbers to exclude from analysis (optional, method parameter only).

## Running the Example

```bash
python main.py
```

## Expected Output

```
🚀 Starting Movix QC workflow...

📦 Creating case...
✅ Case created: case_abc123

🔍 Running data validation...
✅ Data validation passed (task: task_xyz789)
   Valid jaws: ['upper', 'lower']

⚡ Creating analysis tasks...
   Occlusion task: task_abc456
   Holes task: task_def789
   Scan Integrity task: task_ghi012
⏳ Waiting for results...
✅ Occlusion analysis complete
✅ Holes detection complete
✅ Scan Integrity analysis complete

📊 Generating summary and viewer link...

============================================================
🎉 QC Workflow Complete!
============================================================
Case ID: case_abc123
Data Validation: ✅ Passed
Occlusion: ✅ Analyzed
Holes: ✅ Analyzed
Scan Integrity: ✅ Analyzed

🔗 Viewer Link: https://viewer.movixtech.com/case/abc123
============================================================
```

## Troubleshooting

### STL files not found
Make sure `upper.stl` and `lower.stl` are in the `examples/python/` directory.

### Authentication failed
Verify your username and password are correct and configured for the staging environment.

### Connection timeout
Check the `base_url` and ensure the staging API is accessible.

## Next Steps

- Modify the script to process multiple cases
- Add error handling for specific scenarios
- Integrate into your production pipeline
- Explore other SDK features in the [main documentation](../../README.md)
