# Propeller Characteristic Plotter Usage Examples

## Example 1: Interactive Usage
```bash
python char_plotter.py
```
This will start the interactive interface where you can:
1. Select from available propellers
2. Choose plot type:
   - **RPM Sweep**: Thrust/Torque/Power vs RPM at specific flight speed
   - **J Sweep**: CT/CP/Efficiency vs Advance Ratio (J) at specific RPM
3. Enter parameters based on plot type
4. Optionally add reference markers
5. View or save the characteristic plots

## Example 2: Programmatic Usage - RPM Sweep
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

## Example 3: Programmatic Usage - J Sweep (New Feature)
```python
from char_plotter import load_propeller_data, plot_j_sweep

# Load data for a specific propeller
propeller_name = "D10P12B2TWE"
data = load_propeller_data(propeller_name)

# Plot CT, CP, and Efficiency vs J at a specific RPM
target_rpm = 10000  # RPM
plot_j_sweep(data, target_rpm, propeller_name)

# Save plot with reference J values
reference_j_values = [0.3, 0.5, 0.7]
plot_j_sweep(data, target_rpm, propeller_name, 
            save_plot=True, 
            reference_j_values=reference_j_values)
```

## Example 4: Batch Processing
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

### Plot Types
1. **RPM Sweep Plots** (Thrust/Torque/Power vs RPM at specific flight speed)
   - Three comprehensive plots: Thrust vs RPM, Torque vs RPM, Shaft Power vs RPM
   - Second-order polynomial curve fitting for mathematical relationships
   - Physical RPM limiting using APC's 190,000/diameter rule
   - Truncated zero exclusion for accurate fitting
   - Optional reference RPM markers with interpolated values

2. **J Sweep Plots** (CT/CP/Efficiency vs Advance Ratio at specific RPM) - NEW!
   - Three comprehensive plots: CT vs J, CP vs J, Efficiency vs J
   - Shows performance across flight speed range at constant RPM
   - Optional reference J value markers with interpolated coefficients
   - Ideal for analyzing propeller efficiency characteristics

### General Features
- **Interactive propeller selection**: Choose from available propellers or enter name directly
- **Automatic value matching**: Finds closest available speed/RPM if exact match not found
- **Reference markers**: Optional vertical lines with interpolated values from trendlines
  - Intelligent label positioning prevents overlap when reference values are close together
  - Displays interpolated values at user-specified points
- **Save functionality**: Option to save plots as high-resolution PNG files
  - Default output directory: `output_plots/` (automatically created)
  - Custom output directories can be specified programmatically
- **Class-based architecture**: Easy to extend with new plot types in the future

## Interactive Usage

When you run the script interactively, it will:

1. **Display available propellers** - Shows all propellers with data files
2. **Propeller selection** - Choose by number or enter name directly
3. **Plot type selection** - Choose between:
   - RPM Sweep (Thrust/Torque/Power vs RPM)
   - J Sweep (CT/CP/Efficiency vs J)
4. **Parameter input** - Based on plot type:
   - RPM Sweep: Enter flight speed (0-100 m/s)
   - J Sweep: Enter target RPM
5. **Reference markers** - Optionally specify reference values to mark on graphs
   - RPM Sweep: Enter reference RPMs (comma-separated)
   - J Sweep: Enter reference J values (comma-separated)
6. **Plot saving option** - Choose whether to save plots to files
7. **Generate plots** - Creates three plots with reference markers and saves/displays them