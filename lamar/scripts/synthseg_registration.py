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


def synthseg_registration(input_image, reference_image, output_image, output_dir=None, input_parc=None,
                          reference_parc=None, output_parc=None, generate_warpfield=False, apply_warpfield=False,
                          registration_method="SyNRA"):
    """
    Perform contrast-agnostic registration using SynthSeg parcellation.

    Parameters
    ----------
    input_image : str
        Path to the input image to be registered
    reference_image : str
        Path to the reference image (target space)
    output_image : str
        Path where to save the registered input image
    output_dir : str, optional
        Directory to save intermediate files (default: current directory)
    """
    # Create output directory if specified
    if output_dir is None:
        output_dir = os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    # Define paths for intermediate files
    input_parc = os.path.join(output_dir, "input_parcellation.nii.gz")
    reference_parc = os.path.join(output_dir, "reference_parcellation.nii.gz")
    affine_transform = os.path.join(output_dir, "affine_transform.mat")
    warp_field = os.path.join(output_dir, "warp_field.nii.gz")
    inverse_warp = os.path.join(output_dir, "inverse_warp_field.nii.gz")

    print(f"Processing input image: {input_image}")
    print(f"Reference image: {reference_image}")
    print(f"Intermediate files will be saved in: {output_dir}")

    try:

        ## if user declares moving_parc but not moving -> assumes parcelation is already done
        if (apply_warpfield is False):

            if input_parc is not None and input_image is None:
                # Step 1: Generate parcellations with SynthSeg
                print("\n--- Step 1: Generating brain parcellations with SynthSeg ---")
                subprocess.run([
                    "python", "synthseg.py",
                    "--i", input_image,
                    "--o", input_parc,
                    "--parc",
                    "--cpu",
                    "--threads", "1"
                ], check=True)
                ## if user declares fixed_parc but not moving -> assumes parcelation is already done
            if reference_parc is not None and reference_image is None:
                # Step 1: Generate parcellations with SynthSeg
                print("\n--- Step 1: Generating brain parcellations with SynthSeg ---")
                subprocess.run([
                    "python", "synthseg.py",
                    "--i", reference_image,
                    "--o", reference_parc,
                    "--parc",
                    "--cpu",
                    "--threads", "1"
                ], check=True)

            # Step 2: Register parcellations using coregister
            print("\n--- Step 2: Coregistering parcellated images ---")
            subprocess.run([
                "python", "coregister.py",
                "--fixed-file", reference_parc,
                "--moving-file", input_parc,
                "--output", os.path.join(output_dir, "registered_parcellation.nii.gz"),
                # user should declare the output_parcellation
                "--affine-file", affine_transform,
                "--warp-file", warp_field,
                "--rev-warp-file", inverse_warp,
                "--rev-affine-file", os.path.join(output_dir, "inverse_affine_transform.mat"),
                "--registration-method", registration_method,

            ], check=True)

        # Step 3: Apply transformation to the original input image
        if generate_warpfield is False:
            print("\n--- Step 3: Applying transformation to original input image ---")
            subprocess.run([
                "python", "apply_warp.py",
                "--moving", input_image,
                "--reference", reference_image,
                "--affine", affine_transform,
                "--warp", warp_field,
                "--output", output_image
            ], check=True)

        print(f"\nSuccess! Registered image saved to: {output_image}")

    except subprocess.CalledProcessError as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Contrast-agnostic registration using SynthSeg")
    parser.add_argument("--moving", help="Input moving image to be registered")
    parser.add_argument("--fixed", help="Reference fixed image (target space)")
    parser.add_argument("--output", required=True, help="Output registered image")
    parser.add_argument("--workdir", help="Directory for intermediate files (default: current directory)")
    parser.add_argument("--moving-parc", help="Input moving parcellation")
    parser.add_argument("--fixed-parc", help="Reference fixed parcellation")
    parser.add_argument("--output-parc", help="Output registered parcellation")
    parser.add_argument("--generate-warpfield", action="store_true", help="Generate warp field for registration")
    parser.add_argument("--apply-warpfield", action="store_true", help="Apply warp field to moving image")
    parser.add_argument("--registration-method", default="SyNRA", help="Registration method")
    args = parser.parse_args()
    # if they call --registration-method -> pass through the string to the coregister.py
    synthseg_registration(
        input_image=args.moving,
        reference_image=args.fixed,
        output_image=args.output,
        output_dir=args.workdir,
        input_parc=args.moving_parc,
        reference_parc=args.fixed_parc,
        output_parc=args.output_parc,
        generate_warpfield=args.generate_warpfield,
        apply_warpfield=args.apply_warpfield,
        registration_method=args.registration_method
    )