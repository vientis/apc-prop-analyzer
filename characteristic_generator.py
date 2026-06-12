#!/usr/bin/env python3
"""
APC Propeller Characteristic Generator

Generates full characteristic pickle files from .dat performance data.
Includes CLI for batch processing or selective generation.
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
import pickle
from pathlib import Path


def extrapolate_below_zero(propeller_data, propeller_diameter, n_anchor=4):
    """
    Supplement the zero-truncated (windmilling) region of each airspeed DataFrame
    with a physically-grounded negative thrust/torque extrapolation.

    The APC source data is truncated at the zero-thrust point, so any (airspeed, rpm)
    combination where the rpm is too low to produce forward thrust is filled with 0 by
    the generator. Physically the prop windmills there and produces negative thrust
    (drag) and reduced torque that continue smoothly below zero.

    Method - tangent continuation of the measured trend:
        For a fixed airspeed V, thrust and torque vs RPM are continued below the lowest
        measured RPM by extending the local trend of the nearest measured points. The
        line is anchored exactly at the last real (lowest-RPM) data point and uses the
        slope of the nearest ``n_anchor`` measured points, so the extrapolation is
        continuous in both value and slope at the hand-off (no kink) and monotonic by
        construction. Thrust and torque therefore keep decreasing through the
        windmilling regime - thrust passing into drag and torque heading toward the
        autorotation (zero-torque) crossing - rather than turning back up.

        A global quadratic was deliberately avoided: because the measured torque curve
        bottoms out right at the zero-thrust boundary, a parabola fit to it turns back
        *up* when extrapolated, which is non-physical and produces a visible kink where
        the extrapolated and measured data meet.

    Args:
        propeller_data: Dictionary {V: DataFrame} produced by the generator
        propeller_diameter: Propeller diameter in metres
        n_anchor: Number of lowest-RPM measured points used to estimate the local slope

    Returns:
        The same dictionary, with truncated cells replaced by extrapolated values and a
        new boolean column 'extrapolated' marking the supplemented rows.
    """
    rho = 1.225  # Air density in kg/m^3 at sea level (matches generator)
    D = propeller_diameter

    for v in range(101):
        df = propeller_data[v]  # already sorted ascending by rpm with a clean index
        if 'extrapolated' not in df.columns:
            df['extrapolated'] = False

        # Static case: J = 0 for every rpm, so there is no truncated region to fill.
        if v == 0:
            continue

        # The truncated (zero-filled) cells form a block at the low-RPM / high-J end; the
        # measured data is a block at the high-RPM end. The hand-off is the highest-RPM
        # zero cell: everything at or below it is extrapolated (this also absorbs any
        # stray/ragged points the source leaves below the truncation edge), and the clean
        # contiguous measured block above it provides the anchor and local slope.
        thrust = df['T'].values
        zero_pos = np.where(thrust == 0)[0]  # includes the rpm=0 row
        if len(zero_pos) == 0:
            continue
        z = int(zero_pos.max())

        # Need at least 2 measured points above the hand-off to estimate a slope.
        measured = df.iloc[z + 1:]
        if len(measured) < 2:
            continue

        # Anchor at the lowest measured RPM of the clean block and take the local slope
        # from its nearest points. Slopes are clamped non-negative so the continuation is
        # always monotonically decreasing toward lower RPM (no kink, no upturn).
        boundary = measured.iloc[0]
        rpm_b, T_b, Q_b = boundary['rpm'], boundary['T'], boundary['Q']
        local = measured.iloc[:n_anchor]
        slope_T = max(np.polyfit(local['rpm'], local['T'], 1)[0], 0.0)
        slope_Q = max(np.polyfit(local['rpm'], local['Q'], 1)[0], 0.0)

        for pos in range(z + 1):
            idx = df.index[pos]
            rpm = df.at[idx, 'rpm']
            n = rpm / 60.0  # rev/s

            # Tangent line from the boundary; min() guards against ever rising back above
            # the measured boundary value at lower RPM.
            T_ex = min(float(T_b + slope_T * (rpm - rpm_b)), float(T_b))
            Q_ex = min(float(Q_b + slope_Q * (rpm - rpm_b)), float(Q_b))

            df.at[idx, 'T'] = T_ex
            df.at[idx, 'Q'] = Q_ex
            df.at[idx, 'P'] = 2 * np.pi * n * Q_ex  # keep P = 2*pi*n*Q invariant

            # Dimensionless coefficients are undefined at n=0 (division by zero); leave
            # them at their existing 0 there, matching the generator's np.where guard.
            if n > 0:
                df.at[idx, 'CT'] = T_ex / (rho * n**2 * D**4)
                df.at[idx, 'CP'] = df.at[idx, 'P'] / (rho * n**3 * D**5)
                df.at[idx, 'CQ'] = df.at[idx, 'CP'] / (2 * np.pi)
                df.at[idx, 'eta'] = (T_ex * v) / df.at[idx, 'P'] if df.at[idx, 'P'] != 0 else 0

            df.at[idx, 'extrapolated'] = True

    return propeller_data


def generate_propeller_characteristics(data_folder, verbose=False, extrapolate=True):
    """
    Generate characteristic data for a single propeller.

    Args:
        data_folder: Path to the propeller performance data folder
        verbose: Print progress information
        extrapolate: Supplement the zero-truncated region with a physically-grounded
            negative thrust/torque extrapolation (see extrapolate_below_zero)

    Returns:
        tuple: (propeller_data dict, folder_name) or (None, None) if failed
    """
    # Extract propeller diameter from folder name
    folder_name = os.path.basename(data_folder)
    
    if verbose:
        print(f"Processing {folder_name}...", end=' ')
    
    try:
        diameter_string = folder_name.split('P')[0][1:]  # Extract the part after 'D' and before 'P'
        if '-' in diameter_string:
            propeller_diameter = float(diameter_string.replace('-', '.')) * 0.0254  # Convert inches to meters
        else:
            propeller_diameter = float(diameter_string) * 0.0254  # Convert inches to meters
    except (ValueError, IndexError) as e:
        if verbose:
            print(f"Error parsing diameter: {e}")
        return None, None
    
    # Initialize an empty list to store DataFrames for each RPM
    rpm_dataframes = []
    
    # Read each .dat file and store it in a DataFrame
    dat_files = [f for f in os.listdir(data_folder) if f.endswith('.dat')]
    if not dat_files:
        if verbose:
            print("No .dat files found")
        return None, None
    
    for filename in dat_files:
        try:
            rpm = int(filename.replace('.dat', ''))  # Extract RPM from filename
            file_path = os.path.join(data_folder, filename)
            
            # Read the data (original file contains V, J, eta, CT, CP, P, Q, T)
            data = pd.read_csv(file_path, comment='#', header=None,
                               names=['V', 'J', 'eta', 'CT', 'CP', 'P', 'Q', 'T'])
            data['rpm'] = rpm
            
            # Add missing integer airspeeds (0–100 m/s) if not present
            all_speeds = pd.DataFrame({'V': range(101)})  # Create a DataFrame with all integer airspeeds
            data = pd.merge(all_speeds, data, on='V', how='outer').sort_values('V')  # Merge to find missing speeds
            
            # Fill rpm column for interpolated rows (merge creates NaN for new rows)
            data['rpm'] = rpm
            
            # Interpolate physical quantities with appropriate polynomial orders
            # Thrust (T), Torque (Q) scale with RPM^2 -> use quadratic interpolation
            # Power (P) MUST be derived from Q to maintain P = 2πnQ relationship
            # V doesn't need interpolation (it's the merge key)
            
            # Use quadratic interpolation for thrust and torque (order=2)
            for col in ['T', 'Q']:
                if col in data.columns:
                    data[col].interpolate(method='polynomial', order=2, inplace=True)
            
            data.fillna(0, inplace=True)  # Fill any remaining NaN values with 0
            
            # Physical constants and unit conversions
            # Using SI units: V (m/s), rpm, D (m), T (N), Q (N·m), P (W)
            rho = 1.225  # Air density in kg/m³ at sea level
            n = rpm / 60.0  # Convert RPM to revolutions per second (Hz)
            D = propeller_diameter  # Already in meters
            
            # CRITICAL: Derive power from torque to maintain fundamental relationship
            # P = 2π × n × Q (where n is in Hz)
            # This ensures mathematical consistency throughout the data pipeline
            data['P'] = 2 * np.pi * n * data['Q']
            
            # Calculate dimensionless coefficients from physical quantities
            # J = V / (n * D) - Advance ratio
            data['J'] = np.where(n > 0, data['V'] / (n * D), 0)
            
            # CT = T / (rho * n^2 * D^4) - Thrust coefficient
            data['CT'] = np.where(n > 0, data['T'] / (rho * n**2 * D**4), 0)
            
            # CP = P / (rho * n^3 * D^5) - Power coefficient
            # Now derived from P which is derived from Q, maintaining consistency
            data['CP'] = np.where(n > 0, data['P'] / (rho * n**3 * D**5), 0)
            
            # CQ = CP / (2 * pi) - Torque coefficient (alternative: Q / (rho * n^2 * D^5))
            data['CQ'] = data['CP'] / (2 * np.pi)
            
            # eta = (T * V) / P - Propulsive efficiency (for V > 0)
            # This is the fundamental definition: useful power / shaft power
            # At V=0 (static thrust), efficiency is zero (no forward motion)
            # Dimensionless form: eta = (CT * J) / CP should give same result
            data['eta'] = np.where(data['P'] > 0, (data['T'] * data['V']) / data['P'], 0)
            
            # Append to the list of RPM DataFrames
            rpm_dataframes.append(data)
        except Exception as e:
            if verbose:
                print(f"\nWarning: Error processing {filename}: {e}")
            continue
    
    if not rpm_dataframes:
        if verbose:
            print("No valid data processed")
        return None, None
    
    # Add the zero RPM case
    zero_rpm_data = pd.DataFrame({
        'V': range(101),  # Airspeeds 0–100 m/s
        'J': 0, 'eta': 0, 'CT': 0, 'CP': 0,
        'P': 0, 'Q': 0, 'T': 0,
        'rpm': 0, 'CQ': 0
    })
    rpm_dataframes.append(zero_rpm_data)
    
    # Build the final dictionary
    propeller_data = {v: [] for v in range(101)}
    
    # Populate the dictionary with interpolated data
    for data in rpm_dataframes:
        for v in range(101):
            row = data[data['V'] == v]
            propeller_data[v].append(row)
    
    # Convert dictionary entries to DataFrames
    for v in range(101):
        propeller_data[v] = pd.concat(propeller_data[v], ignore_index=True)
        propeller_data[v] = propeller_data[v].sort_values(by='rpm').reset_index(drop=True)
    
    # Supplement the zero-truncated windmilling region with negative thrust/torque.
    if extrapolate:
        propeller_data = extrapolate_below_zero(propeller_data, propeller_diameter)

    if verbose:
        print("✓")

    return propeller_data, folder_name


def save_propeller_data(propeller_data, folder_name, output_directory='reformatted_data/full-characteristics'):
    """
    Save propeller characteristic data to a pickle file.
    
    Args:
        propeller_data: Dictionary of characteristic data
        folder_name: Name of the propeller folder
        output_directory: Directory to save the pickle file
        
    Returns:
        str: Path to saved file or None if failed
    """
    try:
        os.makedirs(output_directory, exist_ok=True)
        output_file = os.path.join(output_directory, f'APC_Prop_{folder_name}.pickle')
        
        with open(output_file, 'wb') as f:
            pickle.dump(propeller_data, f)
        
        return output_file
    except Exception as e:
        print(f"Error saving {folder_name}: {e}")
        return None


def get_available_propellers(data_dir='reformatted_data/performance'):
    """
    Get list of available propeller folders.
    
    Returns:
        list: Sorted list of propeller folder names
    """
    if not os.path.exists(data_dir):
        return []
    
    folders = [f for f in os.listdir(data_dir) 
               if os.path.isdir(os.path.join(data_dir, f))]
    return sorted(folders)


def main():
    parser = argparse.ArgumentParser(
        description='Generate APC propeller characteristic files from performance data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all propeller characteristics
  python characteristic_generator.py --all
  
  # Generate specific propellers
  python characteristic_generator.py D10P7B2TE D12P6B2TE
  
  # List available propellers
  python characteristic_generator.py --list
  
  # Generate with verbose output
  python characteristic_generator.py --all --verbose
        """
    )
    
    parser.add_argument('propellers', nargs='*', 
                        help='Specific propeller names to generate (e.g., D10P7B2TE)')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Generate characteristics for all available propellers')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List all available propellers and exit')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print detailed progress information')
    parser.add_argument('--no-extrapolate', dest='extrapolate', action='store_false',
                        help='Disable negative thrust/torque extrapolation (legacy zero-truncated behaviour)')
    parser.add_argument('--data-dir', default='reformatted_data/performance',
                        help='Directory containing propeller performance data (default: reformatted_data/performance)')
    parser.add_argument('--output-dir', default='reformatted_data/full-characteristics',
                        help='Directory to save pickle files (default: reformatted_data/full-characteristics)')
    
    args = parser.parse_args()
    
    # Get available propellers
    available_propellers = get_available_propellers(args.data_dir)
    
    if not available_propellers:
        print(f"Error: No propeller data found in {args.data_dir}")
        return 1
    
    # Handle --list option
    if args.list:
        print(f"Available propellers ({len(available_propellers)}):")
        for prop in available_propellers:
            print(f"  {prop}")
        return 0
    
    # Determine which propellers to process
    if args.all:
        propellers_to_process = available_propellers
        print(f"Generating characteristics for all {len(propellers_to_process)} propellers...")
    elif args.propellers:
        # Validate requested propellers
        propellers_to_process = []
        for prop in args.propellers:
            if prop in available_propellers:
                propellers_to_process.append(prop)
            else:
                print(f"Warning: Propeller '{prop}' not found in {args.data_dir}")
        
        if not propellers_to_process:
            print("Error: No valid propellers specified")
            return 1
    else:
        # No arguments provided, show help
        parser.print_help()
        return 0
    
    # Process propellers
    success_count = 0
    fail_count = 0
    
    for i, prop_name in enumerate(propellers_to_process, 1):
        if not args.verbose:
            # Show progress bar for non-verbose mode
            progress = i / len(propellers_to_process) * 100
            print(f"\rProgress: [{i}/{len(propellers_to_process)}] {progress:.1f}% - {prop_name:<30}", end='', flush=True)
        
        data_folder = os.path.join(args.data_dir, prop_name)
        propeller_data, folder_name = generate_propeller_characteristics(
            data_folder, verbose=args.verbose, extrapolate=args.extrapolate)
        
        if propeller_data is not None:
            output_file = save_propeller_data(propeller_data, folder_name, args.output_dir)
            if output_file:
                success_count += 1
            else:
                fail_count += 1
        else:
            fail_count += 1
    
    # Print summary
    if not args.verbose:
        print()  # New line after progress bar
    
    print(f"\n{'='*60}")
    print(f"Generation complete!")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {fail_count}")
    print(f"  Total:   {len(propellers_to_process)}")
    print(f"{'='*60}")
    
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())