# Propeller Characteristic Plotter Usage Examples

## Example 1: Interactive Usage
```bash
python char_plotter.py
```
This will start the interactive interface where you can:
1. Select from available propellers
2. Enter a flight speed (0-100 m/s)
3. View the characteristic plots

## Example 2: Programmatic Usage
```python
from char_plotter import load_propeller_data, plot_characteristics, find_available_propellers

# List available propellers
propellers = find_available_propellers()
print("Available propellers:", propellers)

# Load data for a specific propeller
propeller_name = "D10P12B2TWE"
data = load_propeller_data(propeller_name)

# Plot characteristics for a specific flight speed (shows all three plots)
flight_speed = 25  # m/s
plot_characteristics(data, flight_speed, propeller_name)

# Save plot to default output_plots directory
plot_characteristics(data, flight_speed, propeller_name, save_plot=True)

# Plot with reference RPM markers and custom output directory
reference_rpms = [8000, 12000, 15000]
plot_characteristics(data, flight_speed, propeller_name, 
                   save_plot=True, output_dir='custom_analysis',
                   reference_rpms=reference_rpms)
```

## Example 3: Batch Processing
```python
import matplotlib.pyplot as plt
from char_plotter import load_propeller_data, plot_characteristics, find_available_propellers

# Set backend for saving files instead of displaying
plt.switch_backend('Agg')

# Process multiple propellers
propellers = find_available_propellers()
flight_speeds = [0, 25, 50, 75]

for prop in propellers[:3]:  # Process first 3 propellers
    data = load_propeller_data(prop)
    if data:
        for speed in flight_speeds:
            if speed in data:
                print(f"Processing {prop} at {speed} m/s")
                plot_characteristics(data, speed, prop)
                # Save plot with custom filename
                plt.savefig(f'batch_plot_{prop}_{speed}ms.png', dpi=150, bbox_inches='tight')
                plt.close()
```

## Available Propeller Data Structure
Each propeller data file contains:
- Dictionary with keys 0-100 (flight speeds in m/s)
- Each speed contains a DataFrame with columns:
  - `V`: Flight speed (m/s)
  - `J`: Advance ratio
  - `eta`: Efficiency
  - `CT`: Coefficient of thrust
  - `CP`: Coefficient of power
  - `P`: Power (W)
  - `Q`: Torque (Nm)
  - `T`: Thrust (N)
  - `rpm`: RPM
  - `CQ`: Coefficient of torque

## Curve Fitting
The plotter uses second-order polynomial fitting for thrust, torque, and power curves:
- Thrust: T = a₁×RPM² + b₁×RPM + c₁
- Torque: Q = a₂×RPM² + b₂×RPM + c₂
- Power: P = a₃×RPM² + b₃×RPM + c₃

## Features

- **Interactive propeller selection**: Choose from available propellers or enter name directly
- **Automatic speed matching**: Finds closest available flight speed if exact match not found
- **Three comprehensive plots**:
  - Thrust vs RPM
  - Torque vs RPM  
  - Shaft Power vs RPM
- **Second-order polynomial curve fitting**: Shows mathematical relationship between variables
- **Physical RPM limiting**: Excludes high-RPM extrapolated data points from curve fits using APC's 190,000/diameter rule
- **Truncated zero exclusion**: Starts curve fitting from first positive thrust value to exclude artificially truncated negative thrust values
- **Reference RPM markers**: Optional vertical lines with interpolated values from trendlines at user-specified RPMs
  - Only shows markers within the fitted RPM range (between first positive thrust and max mechanical RPM)
  - Displays interpolated thrust (N), torque (Nm), and power (W) values from the polynomial fits
  - Intelligent label positioning prevents overlap when reference RPMs are close together
- **Save functionality**: Option to save plots as high-resolution PNG files
  - Default output directory: `output_plots/` (automatically created)
  - Custom output directories can be specified programmatically

## Interactive Usage

When you run the script interactively, it will:

1. **Display available propellers** - Shows all propellers with data files
2. **Propeller selection** - Choose by number or enter name directly  
3. **Flight speed input** - Enter desired speed (0-100 m/s)
4. **Speed matching** - Automatically finds closest available speed if needed
5. **Reference RPM input** - Optionally specify RPMs to mark on graphs (comma-separated)
6. **Plot saving option** - Choose whether to save plots to files
7. **Generate plots** - Creates three plots with curve fits, reference markers, and saves/displays them