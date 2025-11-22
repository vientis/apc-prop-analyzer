#!/usr/bin/env python3
"""
Propeller Thrust Lookup Utility

This utility allows you to specify desired thrust and airspeed, then calculates
the required RPM and other propeller characteristics using the polynomial trendlines
from char_plotter.py.

Usage:
    python thrust_lookup.py
    
The script will prompt for:
- Propeller identifier (e.g., D10P12B2TWE)
- Desired thrust (in Newtons)
- Flight speed (in m/s)

It will return:
- Required RPM
- Torque (Nm)
- Shaft Power (W)
- Advance Ratio (J)
- Thrust Coefficient (CT)
- Power Coefficient (CP)
- Efficiency (η)
"""

import os
import sys
import numpy as np
from scipy.optimize import fsolve, curve_fit
from char_plotter import (
    PropellerDataManager,
    PlotUtilities,
    find_available_propellers,
    load_propeller_data
)


class ThrustLookupUtility:
    """Utility for finding propeller operating point given thrust and airspeed."""
    
    def __init__(self, data, propeller_name):
        self.data = data
        self.propeller_name = propeller_name
        self.diameter_inches = PropellerDataManager.extract_propeller_diameter(propeller_name)
        self.max_mechanical_rpm = PropellerDataManager.calculate_max_mechanical_rpm(self.diameter_inches)
    
    def _find_operating_point_static(self, target_thrust):
        """
        Find operating point at zero airspeed (static thrust) using interpolation.
        
        At zero airspeed, torque and power have highly non-linear relationships with RPM
        due to complex flow physics (vortex ring state, recirculation, etc.).
        Polynomial fitting is inappropriate, so we use direct interpolation instead.
        
        Args:
            target_thrust: Desired thrust in Newtons
            
        Returns:
            dict: Operating point data
        """
        speed_data = self.data[0]
        
        # Extract data
        rpm = speed_data['rpm'].values
        thrust = speed_data['T'].values
        torque = speed_data['Q'].values
        power = speed_data['P'].values
        ct_values = speed_data['CT'].values
        cp_values = speed_data['CP'].values
        
        # Filter out zero RPM
        nonzero_mask = rpm > 0
        rpm = rpm[nonzero_mask]
        thrust = thrust[nonzero_mask]
        torque = torque[nonzero_mask]
        power = power[nonzero_mask]
        ct_values = ct_values[nonzero_mask]
        cp_values = cp_values[nonzero_mask]
        
        # Check if target thrust is in range
        min_thrust = thrust.min()
        max_thrust = thrust.max()
        
        if target_thrust < min_thrust:
            print(f"⚠️  Warning: Target thrust {target_thrust:.2f}N is below minimum tested thrust")
            print(f"    Minimum thrust in data: {min_thrust:.2f}N at {rpm[0]:.0f} RPM")
            print(f"    Results will be extrapolated and may be inaccurate")
        elif target_thrust > max_thrust:
            print(f"⚠️  Warning: Target thrust {target_thrust:.2f}N exceeds maximum tested thrust")
            print(f"    Maximum thrust in data: {max_thrust:.2f}N at {rpm[-1]:.0f} RPM")
            print(f"    Results will be extrapolated and may be inaccurate")
        
        # Interpolate (or extrapolate if necessary) to find RPM and other values
        # Use linear interpolation for better stability with non-monotonic data
        required_rpm = np.interp(target_thrust, thrust, rpm)
        required_torque = np.interp(required_rpm, rpm, torque)
        required_power = np.interp(required_rpm, rpm, power)
        ct = np.interp(required_rpm, rpm, ct_values)
        cp = np.interp(required_rpm, rpm, cp_values)
        
        # At zero airspeed: J=0, efficiency=0
        advance_ratio = 0.0
        efficiency = 0.0
        
        # Check RPM limits
        if required_rpm > self.max_mechanical_rpm:
            print(f"⚠️  Warning: Required RPM ({required_rpm:.0f}) exceeds maximum mechanical RPM")
            print(f"    Maximum mechanical RPM: {self.max_mechanical_rpm}")
            print(f"    This operating point may damage the propeller!")
        
        return {
            'rpm': required_rpm,
            'thrust': target_thrust,
            'torque': required_torque,
            'power': required_power,
            'flight_speed': 0.0,
            'advance_ratio': advance_ratio,
            'ct': ct,
            'cp': cp,
            'efficiency': efficiency,
            'diameter_inches': self.diameter_inches,
            'max_mechanical_rpm': self.max_mechanical_rpm,
            'is_static': True
        }
    
    def find_operating_point(self, target_thrust, flight_speed):
        """
        Find the RPM required to produce target thrust at given flight speed.
        
        Args:
            target_thrust: Desired thrust in Newtons
            flight_speed: Flight speed in m/s
            
        Returns:
            dict: Operating point data including RPM, torque, power, J, CT, CP, eta
        """
        # Find closest available flight speed in data
        if flight_speed not in self.data:
            closest_speed = PropellerDataManager.find_closest_value(self.data, flight_speed)
            print(f"⚠️  Warning: Flight speed {flight_speed} m/s not in data.")
            print(f"    Using closest available speed: {closest_speed} m/s")
            flight_speed = closest_speed
        
        # Special handling for zero airspeed (static thrust)
        # At V=0, torque and power are highly non-linear and polynomial fitting is inappropriate
        if flight_speed == 0:
            return self._find_operating_point_static(target_thrust)
        
        speed_data = self.data[flight_speed]
        
        # Extract data for fitting
        rpm = speed_data['rpm'].values
        thrust = speed_data['T'].values
        torque = speed_data['Q'].values
        power = speed_data['P'].values
        j_values = speed_data['J'].values
        ct_values = speed_data['CT'].values
        cp_values = speed_data['CP'].values
        eta_values = speed_data['eta'].values
        
        # Filter data for curve fitting (same logic as char_plotter)
        # Use threshold to avoid tiny/noisy values followed by negative thrust
        # Check for consecutive points above threshold to avoid spurious data
        thrust_threshold = 0.1  # Newtons
        significant_thrust_indices = np.where((rpm > 0) & (thrust > thrust_threshold))[0]
        
        if len(significant_thrust_indices) > 0:
            # Find first point where thrust is consistently above threshold
            first_positive_idx = None
            
            for candidate_idx in significant_thrust_indices:
                look_ahead = min(2, len(thrust) - candidate_idx - 1)
                
                if look_ahead >= 2:
                    # Check if next 2 consecutive points are also above threshold
                    if thrust[candidate_idx + 1] > thrust_threshold and thrust[candidate_idx + 2] > thrust_threshold:
                        first_positive_idx = candidate_idx
                        break
                elif look_ahead == 1:
                    # Near end, check if next point is also above threshold
                    if thrust[candidate_idx + 1] > thrust_threshold:
                        first_positive_idx = candidate_idx
                        break
                else:
                    # At the very end
                    first_positive_idx = candidate_idx
                    break
            
            # Fallback: if no consecutive region found, use first significant index
            if first_positive_idx is None:
                first_positive_idx = significant_thrust_indices[0]
            
            first_positive_rpm = rpm[first_positive_idx]
        else:
            # Fallback to any positive thrust
            positive_thrust_indices = np.where((rpm > 0) & (thrust > 0))[0]
            if len(positive_thrust_indices) == 0:
                print("Error: No positive thrust values found in data")
                return None
            first_positive_idx = positive_thrust_indices[0]
            first_positive_rpm = rpm[first_positive_idx]
        
        # TODO: TEMPORARY FIX - Remove this once input data is cleaned up
        # Reduce max RPM by 1000 to avoid anomalies in high-RPM data for 10 inch props
        effective_max_rpm = self.max_mechanical_rpm - 1000 if self.max_mechanical_rpm else None
        
        # Create fitting mask
        if effective_max_rpm:
            fitting_mask = (rpm >= first_positive_rpm) & (rpm <= effective_max_rpm)
        else:
            fitting_mask = rpm >= first_positive_rpm
        
        rpm_fit = rpm[fitting_mask]
        thrust_fit = thrust[fitting_mask]
        torque_fit = torque[fitting_mask]
        power_fit = power[fitting_mask]
        
        if len(rpm_fit) < 4:
            print("Error: Insufficient data points for curve fitting (need at least 4 for 3rd order power polynomial)")
            return None
        
        # Fit polynomial curves (2nd order for thrust/torque, 3rd order for power)
        try:
            popt_thrust, _ = curve_fit(PlotUtilities.second_order_polynomial, rpm_fit, thrust_fit)
            popt_torque, _ = curve_fit(PlotUtilities.second_order_polynomial, rpm_fit, torque_fit)
            popt_power, _ = curve_fit(PlotUtilities.third_order_polynomial, rpm_fit, power_fit)
        except Exception as e:
            print(f"Error fitting curves: {e}")
            return None
        
        # Check if target thrust is within achievable range
        max_thrust_in_range = thrust_fit.max()
        min_thrust_in_range = thrust_fit.min()
        
        if target_thrust > max_thrust_in_range * 1.1:  # Allow 10% extrapolation
            print(f"⚠️  Warning: Target thrust {target_thrust:.2f}N exceeds maximum achievable thrust")
            print(f"    Maximum thrust in fitted range: {max_thrust_in_range:.2f}N")
            print(f"    Attempting calculation anyway (extrapolated result)")
        elif target_thrust < min_thrust_in_range:
            print(f"⚠️  Warning: Target thrust {target_thrust:.2f}N is below minimum thrust")
            print(f"    Minimum thrust in fitted range: {min_thrust_in_range:.2f}N")
        
        # Solve for RPM that produces target thrust
        def thrust_error(rpm_val):
            return PlotUtilities.second_order_polynomial(rpm_val, *popt_thrust) - target_thrust
        
        # Use initial guess based on linear interpolation
        if target_thrust >= min_thrust_in_range and target_thrust <= max_thrust_in_range:
            initial_guess = np.interp(target_thrust, thrust_fit, rpm_fit)
        else:
            initial_guess = rpm_fit[len(rpm_fit)//2]  # Use midpoint
        
        try:
            required_rpm = fsolve(thrust_error, initial_guess)[0]
        except Exception as e:
            print(f"Error solving for RPM: {e}")
            return None
        
        # Check if solution is reasonable
        if required_rpm < 0:
            print(f"Error: Calculated negative RPM ({required_rpm:.0f}). Cannot achieve target thrust.")
            return None
        
        if required_rpm > self.max_mechanical_rpm * 1.2:
            print(f"⚠️  Warning: Required RPM ({required_rpm:.0f}) significantly exceeds maximum mechanical RPM")
            print(f"    Maximum mechanical RPM: {self.max_mechanical_rpm}")
            print(f"    This operating point may damage the propeller!")
        
        # Calculate other characteristics at this RPM
        calculated_thrust = PlotUtilities.second_order_polynomial(required_rpm, *popt_thrust)
        required_torque = PlotUtilities.second_order_polynomial(required_rpm, *popt_torque)
        required_power = PlotUtilities.third_order_polynomial(required_rpm, *popt_power)
        
        # Interpolate dimensionless coefficients from actual data
        # These should come from the data, not be recalculated, to match the data source
        advance_ratio = np.interp(required_rpm, rpm_fit, j_values[fitting_mask])
        ct = np.interp(required_rpm, rpm_fit, ct_values[fitting_mask])
        cp = np.interp(required_rpm, rpm_fit, cp_values[fitting_mask])
        efficiency = np.interp(required_rpm, rpm_fit, eta_values[fitting_mask])
        
        # Get diameter for display
        diameter_m = self.diameter_inches * 0.0254  # Convert inches to meters
        
        return {
            'rpm': required_rpm,
            'thrust': calculated_thrust,
            'torque': required_torque,
            'power': required_power,
            'flight_speed': flight_speed,
            'advance_ratio': advance_ratio,
            'ct': ct,
            'cp': cp,
            'efficiency': efficiency,
            'diameter_inches': self.diameter_inches,
            'max_mechanical_rpm': self.max_mechanical_rpm,
            'is_static': False
        }


class ThrustLookupCLI:
    """Interactive command-line interface for thrust lookup."""
    
    def __init__(self):
        self.data_manager = PropellerDataManager()
    
    def run(self):
        """Run the interactive CLI."""
        print("=== Propeller Thrust Lookup Utility ===\n")
        
        # Find available propellers
        available_propellers = find_available_propellers()
        
        if not available_propellers:
            print("No propeller data files found in reformatted_data/full-characteristics/")
            return
        
        print("Available propellers:")
        for i, prop in enumerate(available_propellers, 1):
            print(f"  {i:2d}. {prop}")
        
        # Get propeller selection
        propeller_name = self._get_propeller_selection(available_propellers)
        
        # Load propeller data
        print(f"\nLoading data for propeller: {propeller_name}")
        data = load_propeller_data(propeller_name)
        
        if data is None:
            print(f"Failed to load data for propeller {propeller_name}")
            return
        
        # Create lookup utility
        lookup = ThrustLookupUtility(data, propeller_name)
        
        # Display propeller info
        if lookup.diameter_inches:
            print(f"Propeller diameter: {lookup.diameter_inches} inches ({lookup.diameter_inches * 0.0254:.3f} m)")
        if lookup.max_mechanical_rpm:
            print(f"Maximum mechanical RPM: {lookup.max_mechanical_rpm}")
        
        # Get target thrust and flight speed
        target_thrust = self._get_thrust()
        flight_speed = self._get_flight_speed()
        
        # Calculate operating point
        print(f"\nCalculating operating point for {target_thrust}N thrust at {flight_speed} m/s...")
        print("-" * 70)
        
        result = lookup.find_operating_point(target_thrust, flight_speed)
        
        if result:
            self._display_results(result, propeller_name)
        else:
            print("Failed to calculate operating point.")
    
    def _get_propeller_selection(self, available_propellers):
        """Get propeller selection from user."""
        while True:
            try:
                selection = input(f"\nSelect propeller (1-{len(available_propellers)}) or enter name directly: ").strip()
                
                if selection.isdigit():
                    index = int(selection) - 1
                    if 0 <= index < len(available_propellers):
                        return available_propellers[index]
                    else:
                        print(f"Please enter a number between 1 and {len(available_propellers)}")
                        continue
                
                if selection in available_propellers:
                    return selection
                else:
                    matches = [prop for prop in available_propellers if selection.upper() in prop.upper()]
                    if len(matches) == 1:
                        print(f"Found match: {matches[0]}")
                        return matches[0]
                    elif len(matches) > 1:
                        print(f"Multiple matches found: {', '.join(matches)}")
                        print("Please be more specific.")
                    else:
                        print(f"Propeller '{selection}' not found. Available options listed above.")
                        
            except (ValueError, KeyboardInterrupt):
                print("\nOperation cancelled.")
                sys.exit(0)
    
    def _get_thrust(self):
        """Get target thrust from user."""
        while True:
            try:
                thrust_input = input("\nEnter desired thrust (N): ").strip()
                thrust = float(thrust_input)
                
                if thrust > 0:
                    return thrust
                else:
                    print("Thrust must be positive")
                    
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                sys.exit(0)
    
    def _get_flight_speed(self):
        """Get flight speed from user."""
        while True:
            try:
                speed_input = input("Enter flight speed (m/s, 0-100): ").strip()
                speed = float(speed_input)
                
                if 0 <= speed <= 100:
                    if speed == int(speed):
                        speed = int(speed)
                    return speed
                else:
                    print("Flight speed must be between 0 and 100 m/s")
                    
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                sys.exit(0)
    
    def _display_results(self, result, propeller_name):
        """Display the calculated operating point results."""
        print("\n" + "=" * 70)
        print(f"OPERATING POINT: {propeller_name}")
        print("=" * 70)
        
        # Add note for static thrust
        if result.get('is_static', False):
            print("\n⚠️  STATIC THRUST CONDITION (Zero Airspeed)")
            print("    Using direct interpolation (polynomial fitting not valid at V=0)")
        
        print(f"\nFlight Conditions:")
        print(f"  Flight Speed:        {result['flight_speed']:>10.2f} m/s")
        print(f"  Target Thrust:       {result['thrust']:>10.2f} N")
        
        print(f"\nRequired Operating Point:")
        print(f"  RPM:                 {result['rpm']:>10.0f} RPM")
        
        # Add warning if exceeds max mechanical RPM
        if result['rpm'] > result['max_mechanical_rpm']:
            print(f"  ⚠️  WARNING: Exceeds max mechanical RPM ({result['max_mechanical_rpm']})")
        
        print(f"  Torque:              {result['torque']:>10.4f} Nm")
        print(f"  Shaft Power:         {result['power']:>10.2f} W ({result['power']/745.7:.2f} HP)")
        
        print(f"\nDimensionless Coefficients:")
        print(f"  Advance Ratio (J):   {result['advance_ratio']:>10.4f}")
        print(f"  Thrust Coeff (CT):   {result['ct']:>10.4f}")
        print(f"  Power Coeff (CP):    {result['cp']:>10.4f}")
        print(f"  Efficiency (η):      {result['efficiency']:>10.4f} ({result['efficiency']*100:.2f}%)")
        
        print("\n" + "=" * 70)
        
        # Add interpretation guidance
        if result['efficiency'] < 0.3:
            print("⚠️  Low efficiency - propeller is operating far from optimal conditions")
        elif result['efficiency'] > 0.8:
            print("✓ Good efficiency - propeller is operating near optimal conditions")
        
        if result['rpm'] < 1000:
            print("⚠️  Very low RPM - may not be practical")
        
        print()


def main():
    """Main function to run the thrust lookup utility."""
    cli = ThrustLookupCLI()
    cli.run()


if __name__ == "__main__":
    # Check for help argument
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print(__doc__)
        sys.exit(0)
    
    # Check if required directories exist
    if not os.path.exists('reformatted_data/full-characteristics'):
        print("Error: reformatted_data/full-characteristics directory not found.")
        print("Please run characteristic_generator.py first to generate the data files.")
        sys.exit(1)
    else:
        try:
            main()
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            sys.exit(0)
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
