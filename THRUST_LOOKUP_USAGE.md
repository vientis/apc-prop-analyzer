# Thrust Lookup Utility

## Overview

`thrust_lookup.py` is a command-line utility that calculates the required propeller operating point to achieve a desired thrust at a specified flight speed. It uses the same polynomial trendlines from `char_plotter.py` to interpolate propeller performance characteristics.

## Purpose

Given a target thrust and flight speed, this tool will determine:
- Required RPM
- Torque (Nm)
- Shaft Power (W and HP)
- Advance Ratio (J)
- Thrust Coefficient (CT)
- Power Coefficient (CP)
- Propeller Efficiency (η)

## Usage

### Interactive Mode

Simply run the script and follow the prompts:

```bash
python thrust_lookup.py
```

The CLI will ask you to:
1. **Select a propeller** (by number or name)
2. **Enter desired thrust** (in Newtons)
3. **Enter flight speed** (in m/s, range 0-100)

### Example Session

```
=== Propeller Thrust Lookup Utility ===

Available propellers:
   1. D10P10B2T
   2. D10P10B2TE
   3. D10P12B2TWE
   ...

Select propeller (1-13) or enter name directly: 1

Loading data for propeller: D10P10B2T
Propeller diameter: 10.0 inches (0.254 m)
Maximum mechanical RPM: 19000

Enter desired thrust (N): 10

Enter flight speed (m/s, 0-100): 25

Calculating operating point for 10.0N thrust at 25 m/s...
----------------------------------------------------------------------

======================================================================
OPERATING POINT: D10P10B2T
======================================================================

Flight Conditions:
  Flight Speed:             25.00 m/s
  Target Thrust:            10.00 N

Required Operating Point:
  RPM:                       7910 RPM
  Torque:                  0.3771 Nm
  Shaft Power:             177.69 W (0.24 HP)

Dimensionless Coefficients:
  Advance Ratio (J):       0.7520
  Thrust Coeff (CT):       0.1106
  Power Coeff (CP):        0.1063
  Efficiency (η):          0.7786 (77.86%)

======================================================================
```

## How It Works

1. **Load Data**: Reads the propeller's full characteristic data from pickle files
2. **Find Closest Speed**: If the requested flight speed isn't available, uses the closest speed in the data
3. **Fit Polynomial Curves**: Uses second-order polynomials to fit Thrust, Torque, and Power vs RPM (same as char_plotter.py)
4. **Solve for RPM**: Uses numerical solver to find the RPM that produces the target thrust
5. **Interpolate Coefficients**: Interpolates J, CT, CP, and efficiency from the actual data at the calculated RPM
6. **Display Results**: Shows comprehensive operating point information

## Features

### Automatic Speed Matching
If you enter a flight speed that isn't in the data (e.g., 22.5 m/s), the tool will automatically use the closest available speed and warn you:
```
⚠️  Warning: Flight speed 22.5 m/s not in data.
    Using closest available speed: 22 m/s
```

### Physical Limits Checking
The tool checks if the calculated RPM exceeds the maximum mechanical RPM (APC limit: 190,000 / diameter in inches):
```
⚠️  WARNING: Exceeds max mechanical RPM (19000)
```

### Performance Guidance
The tool provides interpretation of the results:
- Efficiency warnings if operation is far from optimal
- RPM practicality checks
- Thrust range validation

### Propeller Selection
You can select a propeller by:
- **Number**: Enter `1` for the first propeller
- **Exact name**: Enter `D10P10B2T`
- **Partial match**: Enter `D10P10` (if unique)

## Limitations

1. **Data Availability**: Results are only as accurate as the input data. If the requested thrust is outside the tested range, the tool will extrapolate and warn you.

2. **Speed Discretization**: Flight speeds are limited to 0-100 m/s in 1 m/s increments (or whatever is in the data files).

3. **Polynomial Fitting**: Uses second-order polynomials which work well within the tested range but may be less accurate for extrapolation.

4. **Single Operating Point**: The tool finds a single RPM solution. In some cases (e.g., with highly non-monotonic thrust curves), multiple solutions might exist.

## Technical Details

### Calculation Method
- **Thrust fitting**: Second-order polynomial fit to Thrust vs RPM data
- **Torque fitting**: Second-order polynomial fit to Torque vs RPM data  
- **Power fitting**: Second-order polynomial fit to Power vs RPM data
- **Dimensionless coefficients**: Linear interpolation from actual data values

### Data Range for Fitting
Following the same logic as `char_plotter.py`:
- Starts from the first RPM with positive thrust (excludes truncated zeros)
- Ends at maximum mechanical RPM (190,000 / diameter_inches)
- Requires at least 4 data points for fitting

### Efficiency Calculation
Efficiency and dimensionless coefficients (J, CT, CP) are interpolated directly from the test data rather than recalculated, ensuring consistency with the source data.

## Dependencies

Same as `char_plotter.py`:
- numpy
- pandas
- scipy
- matplotlib (imported via char_plotter)

## Help

For help, run:
```bash
python thrust_lookup.py --help
```

## See Also

- `char_plotter.py` - Visualization tool for propeller characteristics
- `PLOTTER_USAGE.md` - Documentation for the char_plotter tool
- `characteristic_generator.py` - Tool that generates the pickle data files
