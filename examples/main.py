"""
Movix QC SDK - Complete Workflow Example

This script demonstrates a full quality control workflow:
1. Create a case with upper and lower STL files
2. Run data validation and verify results
3. Run occlusion and holes detection in parallel
4. Generate summary and viewer link
"""

import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from movix_qc_sdk import Client


def main():
    """Run complete QC workflow."""

    # Initialize client with staging configuration
    # Thresholds default to 0.0 - set your own values based on requirements:
    # - MOVIX_QC_OCCLUSION_THRESHOLD_MM (default: 0.0mm)
    # - MOVIX_QC_HOLES_THRESHOLD_AREA_MM (default: 0.0mm²)
    with Client(
        api_url="https://api-staging.movixtech.com",
        username="your-email@example.com",  # Replace with your email
        password="your-password",  # Replace with your password
        timeout=30,
        user_agent="Movix/1.2 (+support@movixtech.com)",
        occlusion_threshold_mm=0.0,  # Set based on your requirements
        holes_threshold_area_mm=0.0,  # Set based on your requirements
    ) as client:
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
            # Step 1: Create case and upload files
            print("📦 Creating case...")
            case = client.cases.create(note="SDK v0.2.2 example workflow")
            case_id = case.case_id
            print(f"✅ Case created: {case_id}")

            print("📤 Uploading STL files...")
            client.cases.upload_files(case_id, paths=[str(upper_stl), str(lower_stl)])
            print("✅ Files uploaded\n")

            # Step 2: Run data validation (synchronous)
            print("🔍 Running data validation...")
            validation_task = client.tasks.create_data_validation(case_id)
            validation_result = client.tasks.wait_for_completion(
                case_id,
                validation_task.task_id
            )

            # Check validation results
            if validation_result.result and validation_result.result.get("overall_valid"):
                print(f"✅ Data validation passed (task: {validation_task.task_id})\n")
            else:
                print(f"⚠️  Data validation failed (task: {validation_task.task_id})")
                if validation_result.result:
                    validations = validation_result.result.get("validations", {})
                    for key, val in validations.items():
                        if not val.get("valid"):
                            print(f"   - {key}: {val.get('message')}")
                print()

            # Step 3: Create occlusion and holes detection tasks
            print("⚡ Creating occlusion and holes detection tasks...")
            occlusion_task = client.tasks.create_occlusion(case_id)
            print(f"   Occlusion task: {occlusion_task.task_id}")

            holes_task = client.tasks.create_holes(case_id)
            print(f"   Holes task: {holes_task.task_id}")

            # Step 4: Wait for both tasks to complete (in parallel using threads)
            print("⏳ Waiting for results...")

            def wait_occlusion():
                return client.tasks.wait_for_completion(case_id, occlusion_task.task_id)

            def wait_holes():
                return client.tasks.wait_for_completion(case_id, holes_task.task_id)

            with ThreadPoolExecutor(max_workers=2) as executor:
                occlusion_future = executor.submit(wait_occlusion)
                holes_future = executor.submit(wait_holes)
                occlusion_result = occlusion_future.result()
                holes_result = holes_future.result()

            print("✅ Occlusion analysis complete")
            if occlusion_result.result:
                hyperocclusion = occlusion_result.result.get('hyperocclusion')
                print(f"   Hyperocclusion: {hyperocclusion}")
                if hyperocclusion:
                    penetration = occlusion_result.result.get('penetration')
                    print(f"   Penetration: {penetration}mm")
                else:
                    min_gap = occlusion_result.result.get('min_gap')
                    print(f"   Min gap: {min_gap}mm")

            print("✅ Holes detection complete")
            if holes_result.result:
                upper_holes = holes_result.result.get('upper_arch_holes_count', 0)
                lower_holes = holes_result.result.get('lower_arch_holes_count', 0)
                total = upper_holes + lower_holes
                print(f"   Total holes: {total} (upper: {upper_holes}, lower: {lower_holes})\n")

            # Step 5: Generate summary and viewer link
            print("📊 Generating summary and viewer link...")
            summary = client.cases.generate_summary(case_id)
            viewer_link = client.cases.generate_viewer_link(case_id)

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

            if summary.message:
                print("\n📋 Summary:")
                print(f"   {summary.message}")

            if viewer_link:
                print(f"\n🔗 Viewer Link: {viewer_link.url}")
                print(f"   Expires: {viewer_link.expires_at}")

            # Print detailed task results
            print("\n📈 Detailed Results:")

            # Occlusion results
            if occlusion_result.result:
                print(f"\n   Occlusion Analysis (Task {occlusion_result.task_id}):")
                result = occlusion_result.result
                print(f"   - Status: {result.get('status')}")
                print(f"   - Hyperocclusion: {result.get('hyperocclusion')}")
                print(f"   - Penetration: {result.get('penetration')}mm")
                print(f"   - Min gap: {result.get('min_gap')}mm")
                print(f"   - Overlap: {result.get('overlap')}mm²")
                print(f"   - Threshold used: {result.get('threshold_mm')}mm")

            # Holes results
            if holes_result.result:
                print(f"\n   Holes Detection (Task {holes_result.task_id}):")
                result = holes_result.result
                print(f"   - Status: {result.get('status')}")
                upper = result.get('upper_arch_holes_count', 0)
                lower = result.get('lower_arch_holes_count', 0)
                print(f"   - Upper arch holes: {upper}")
                print(f"   - Lower arch holes: {lower}")
                print(f"   - Total holes: {upper + lower}")

            print("="*60 + "\n")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
