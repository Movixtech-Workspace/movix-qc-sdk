"""
Movix QC SDK - Complete Workflow Example

This script demonstrates a full quality control workflow:
1. Create a case with upper and lower STL files
2. Run data validation and verify results
3. Run occlusion and holes detection in parallel
4. Generate summary and viewer link
"""

import asyncio
import sys
from pathlib import Path

from movix_qc_sdk import Client


async def main():
    """Run complete QC workflow."""

    # Initialize client with staging configuration
    # Thresholds default to 0.0 - set your own values based on requirements:
    # - MOVIX_QC_OCCLUSION_THRESHOLD_MM (default: 0.0mm)
    # - MOVIX_QC_HOLES_THRESHOLD_AREA_MM (default: 0.0mm²)
    client = Client(
        api_url="https://api-staging.movixtech.com",  # Replace with actual staging URL
        username="your-username",  # Replace with your username
        password="your-password",  # Replace with your password
        timeout=30,
        user_agent="Movix/1.2 (+support@movixtech.com)",
        occlusion_threshold_mm=0.2,  # Set based on your requirements (0.0 = all occlusions detected)
        holes_threshold_area_mm=10.0,  # Set based on your requirements (0.0 = all holes detected)
    )

    print("🚀 Starting Movix QC workflow...\n")

    # File paths - replace with your actual STL files
    upper_stl = Path(__file__).parent / "upper.stl"
    lower_stl = Path(__file__).parent / "lower.stl"

    # Validate files exist
    if not upper_stl.exists() or not lower_stl.exists():
        print("❌ Error: STL files not found!")
        print(f"   Expected: {upper_stl}")
        print(f"   Expected: {lower_stl}")
        print("\n   Please add your upper.stl and lower.stl files to the examples/ directory.")
        sys.exit(1)

    try:
        # Step 1: Create case
        print("📦 Creating case...")
        case = await client.cases.create(
            upper_stl_path=str(upper_stl),
            lower_stl_path=str(lower_stl)
        )
        case_id = case.case_id
        print(f"✅ Case created: {case_id}\n")

        # Step 2: Run data validation (synchronous)
        print("🔍 Running data validation...")
        validation_task = await client.tasks.create_data_validation(case_id)
        validation_result = await client.tasks.wait_for_completion(
            case_id,
            validation_task.task_id
        )

        # Check validation results
        if validation_result.result and validation_result.result.get("overall_valid"):
            print(f"✅ Data validation passed (task: {validation_task.task_id})")
            print(f"   Valid jaws: {validation_result.result.get('valid_jaws', [])}\n")
        else:
            print(f"⚠️  Data validation failed (task: {validation_task.task_id})")
            print(f"   Result: {validation_result.result}\n")
            # Continue anyway for demonstration purposes

        # Step 3: Run occlusion and holes detection in parallel
        print("⚡ Running occlusion and holes detection in parallel...")
        occlusion_task, holes_task = await asyncio.gather(
            client.tasks.create_occlusion(case_id),
            client.tasks.create_holes(case_id)
        )
        print(f"   Occlusion task: {occlusion_task.task_id}")
        print(f"   Holes task: {holes_task.task_id}")

        # Step 4: Wait for both tasks to complete
        print("⏳ Waiting for results...")
        occlusion_result, holes_result = await asyncio.gather(
            client.tasks.wait_for_completion(case_id, occlusion_task.task_id),
            client.tasks.wait_for_completion(case_id, holes_task.task_id)
        )

        print("✅ Occlusion analysis complete")
        if occlusion_result.result:
            print(f"   Result: {occlusion_result.result}")

        print("✅ Holes detection complete")
        if holes_result.result:
            print(f"   Result: {holes_result.result}\n")

        # Step 5: Generate summary and viewer link
        print("📊 Generating summary and viewer link...")
        summary_task = await client.cases.create_summary_and_viewer(case_id)
        summary_result = await client.tasks.wait_for_completion(
            case_id,
            summary_task.task_id
        )

        # Extract viewer link
        viewer_link = None
        if summary_result.result and "viewer_link" in summary_result.result:
            viewer_link = summary_result.result["viewer_link"]

        # Display final results
        print("\n" + "="*60)
        print("🎉 QC Workflow Complete!")
        print("="*60)
        print(f"Case ID: {case_id}")
        validation_status = (
            "✅ Passed"
            if validation_result.result and validation_result.result.get('overall_valid')
            else "⚠️  Issues found"
        )
        print(f"Data Validation: {validation_status}")
        print("Occlusion: ✅ Analyzed")
        print("Holes: ✅ Analyzed")

        if viewer_link:
            print(f"\n🔗 Viewer Link: {viewer_link}")
        else:
            print("\n⚠️  Viewer link not available")

        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
