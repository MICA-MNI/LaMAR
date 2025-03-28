#!/usr/bin/env python3
"""
Example script for contrast-agnostic registration using SynthSeg

This script demonstrates a full registration pipeline that uses SynthSeg's brain
parcellation to enable registration between images of different contrasts:

1. Generate parcellations of both input and reference images using SynthSeg
2. Register the parcellations to each other (contrast-agnostic)
3. Apply the resulting transformation to the original input image

This approach is useful for registering images with very different contrasts
(e.g., T1w to T2w, FLAIR to T1w, etc.) where direct intensity-based
registration might fail.
"""

import os
import argparse
import subprocess
import sys


def lamareg(input_image, reference_image, output_image=None, input_parc=None,
            reference_parc=None, output_parc=None, generate_warpfield=False, apply_warpfield=False,
            registration_method="SyNRA", affine_file=None, warp_file=None,
            inverse_warp_file=None, inverse_affine_file=None, 
            synthseg_threads=1, ants_threads=1):
    """
    Perform contrast-agnostic registration using SynthSeg parcellation.
    """
    # Create directories for all output files
    for file_path in [output_image, input_parc, reference_parc, output_parc, 
                     affine_file, warp_file, inverse_warp_file, inverse_affine_file]:
        if file_path is not None:
            output_dir = os.path.dirname(file_path)
            if output_dir:  # Only try to create if there's a directory part
                os.makedirs(output_dir, exist_ok=True)
                
    print(f"Processing input image: {input_image}")
    print(f"Reference image: {reference_image}")
    print(f"Using {synthseg_threads} thread(s) for SynthSeg and {ants_threads} thread(s) for ANTs")

    # Create environment with suppressed TensorFlow warnings
    env = os.environ.copy()
    env['TF_CPP_MIN_LOG_LEVEL'] = '3'  # 0=ALL, 1=INFO, 2=WARNING, 3=ERROR
    env['PYTHONWARNINGS'] = 'ignore'
    
    # Set ANTs/ITK thread count
    env['ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS'] = str(ants_threads)
    env['OMP_NUM_THREADS'] = str(ants_threads)  # OpenMP threads for ANTs
    
    # Print warnings for transform files that won't be saved
    if not apply_warpfield:
        if affine_file is None:
            print("Warning: No affine transform file path provided - affine transform will not be saved")
        if warp_file is None:
            print("Warning: No warp field file path provided - warp field will not be saved")
        if inverse_warp_file is None:
            print("Warning: No inverse warp field file path provided - inverse warp field will not be saved")
        if inverse_affine_file is None:
            print("Warning: No inverse affine transform file path provided - inverse affine transform will not be saved")

    try:
        # WORKFLOW 1 & 2: Full registration or generate warpfield
        if not apply_warpfield:
            # Step 1: Generate parcellations with SynthSeg if needed
            if input_image is not None:
                print("\n--- Step 1.1: Generating parcellation for input image ---")
                subprocess.run([
                    "lamar", "synthseg",
                    "--i", input_image,
                    "--o", input_parc,
                    "--parc",
                    "--cpu",
                    "--threads", str(synthseg_threads)  # Use SynthSeg threads
                ], check=True, env=env)
                
            if reference_image is not None:
                print("\n--- Step 1.2: Generating parcellation for reference image ---")
                subprocess.run([
                    "lamar", "synthseg",
                    "--i", reference_image,
                    "--o", reference_parc,
                    "--parc",
                    "--cpu",
                    "--threads", str(synthseg_threads)  # Use SynthSeg threads
                ], check=True, env=env)

            # Step 2: Register parcellations using coregister
            print("\n--- Step 2: Coregistering parcellated images ---")
            cmd = [
                "lamar", "coregister",
                "--fixed-file", reference_parc,
                "--moving-file", input_parc,
                "--output", output_parc,
                "--registration-method", registration_method,
            ]
            
            # Only include transform file flags if paths were provided
            if affine_file:
                cmd.extend(["--affine-file", affine_file])
            
            if warp_file:
                cmd.extend(["--warp-file", warp_file])
            
            if inverse_warp_file:
                cmd.extend(["--rev-warp-file", inverse_warp_file])
                
            if inverse_affine_file:
                cmd.extend(["--rev-affine-file", inverse_affine_file])
                
            subprocess.run(cmd, check=True, env=env)

        # WORKFLOW 1 & 3: Apply transformation to the original input image
        if not generate_warpfield and output_image is not None:
            print("\n--- Step 3: Applying transformation to original input image ---")
            apply_cmd = [
                "lamar", "apply_warp",
                "--moving", input_image,
                "--reference", reference_image,
                "--output", output_image
            ]
            
            # Only include transform flags if files were provided
            if affine_file:
                apply_cmd.extend(["--affine", affine_file])
            
            if warp_file:
                apply_cmd.extend(["--warp", warp_file])
                
            subprocess.run(apply_cmd, check=True, env=env)

            print(f"\nSuccess! Registered image saved to: {output_image}")
        elif generate_warpfield:
            success_msg = "\nSuccess! "
            if warp_file:
                success_msg += f"Warp field generated at: {warp_file}"
            if affine_file:
                success_msg += f"\nAffine transformation saved at: {affine_file}"
            print(success_msg)

    except subprocess.CalledProcessError as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Entry point for command-line use"""
    parser = argparse.ArgumentParser(description="Contrast-agnostic registration using SynthSeg")
    parser.add_argument("--moving", required=True, help="Input moving image to be registered")
    parser.add_argument("--fixed", required=True, help="Reference fixed image (target space)")
    parser.add_argument("--output", help="Output registered image")
    parser.add_argument("--moving-parc", required=True, help="Path for moving image parcellation")
    parser.add_argument("--fixed-parc", required=True, help="Path for fixed image parcellation")
    parser.add_argument("--registered-parc", required=True, help="Path for registered parcellation")
    parser.add_argument("--affine", required=True, help="Path for affine transformation")
    parser.add_argument("--warpfield", required=True, help="Path for warp field")
    parser.add_argument("--inverse-warpfield", help="Path for inverse warp field")
    parser.add_argument("--inverse-affine", help="Path for inverse affine transformation")
    parser.add_argument("--generate-warpfield", action="store_true", help="Generate warp field without applying it")
    parser.add_argument("--apply-warpfield", action="store_true", help="Apply existing warp field to moving image")
    parser.add_argument("--registration-method", default="SyNRA", help="Registration method")
    parser.add_argument("--synthseg-threads", type=int, default=1, help="Number of threads to use for SynthSeg segmentation")
    parser.add_argument("--ants-threads", type=int, default=1, help="Number of threads to use for ANTs registration")
    
    args = parser.parse_args()
    
    # Validate arguments based on workflow
    if args.apply_warpfield and (args.affine is None or args.warpfield is None):
        parser.error("--apply-warpfield requires --affine and --warpfield arguments")
    
    if args.generate_warpfield and args.output is not None:
        parser.error("--generate-warpfield cannot be used with --output (no output image is produced)")
    
    if not args.apply_warpfield and not args.generate_warpfield and args.output is None:
        parser.error("--output is required unless --generate-warpfield or --apply-warpfield is specified")
    
    lamareg(
        input_image=args.moving,
        reference_image=args.fixed,
        output_image=args.output,
        input_parc=args.moving_parc,
        reference_parc=args.fixed_parc,
        output_parc=args.registered_parc,
        generate_warpfield=args.generate_warpfield,
        apply_warpfield=args.apply_warpfield,
        registration_method=args.registration_method,
        affine_file=args.affine,
        warp_file=args.warpfield,
        inverse_warp_file=args.inverse_warpfield,
        inverse_affine_file=args.inverse_affine,
        synthseg_threads=args.synthseg_threads,
        ants_threads=args.ants_threads
    )


if __name__ == "__main__":
    main()