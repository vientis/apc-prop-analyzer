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


def generate_propeller_characteristics(data_folder, verbose=False):
    """
    Generate characteristic data for a single propeller.
    
    Args:
        data_folder: Path to the propeller performance data folder
        verbose: Print progress information
        
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
            # Power (P) scales with RPM^3 -> use cubic interpolation
            # V doesn't need interpolation (it's the merge key)
            
            # Use quadratic interpolation for thrust and torque (order=2)
            for col in ['T', 'Q']:
                if col in data.columns:
                    data[col].interpolate(method='polynomial', order=2, inplace=True)
            
            # Use cubic interpolation for power (order=3)
            if 'P' in data.columns:
                data['P'].interpolate(method='polynomial', order=3, inplace=True)
            
            data.fillna(0, inplace=True)  # Fill any remaining NaN values with 0
            
            # Calculate dimensionless coefficients from interpolated physical quantities
            # Using SI units: V (m/s), rpm, D (m), T (N), Q (N·m), P (W)
            rho = 1.225  # Air density in kg/m³ at sea level
            n = rpm / 60.0  # Convert RPM to revolutions per second (Hz)
            D = propeller_diameter  # Already in meters
            
            # Calculate dimensionless coefficients
            # J = V / (n * D) - Advance ratio
            data['J'] = np.where(n > 0, data['V'] / (n * D), 0)
            
            # CT = T / (rho * n^2 * D^4) - Thrust coefficient
            data['CT'] = np.where(n > 0, data['T'] / (rho * n**2 * D**4), 0)
            
            # CP = P / (rho * n^3 * D^5) - Power coefficient
            data['CP'] = np.where(n > 0, data['P'] / (rho * n**3 * D**5), 0)
            
            # CQ = CP / (2 * pi) - Torque coefficient
            data['CQ'] = data['CP'] / (2 * np.pi)
            
            # eta = (CT * J) / CP - Propulsive efficiency
            data['eta'] = np.where(data['CP'] > 0, (data['CT'] * data['J']) / data['CP'], 0)
            
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
        propeller_data, folder_name = generate_propeller_characteristics(data_folder, verbose=args.verbose)
        
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