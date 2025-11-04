import os
import pandas as pd
import numpy as np
import pickle

# Define the path to the extracted data folder
data_folder = 'reformatted_data/performance/D4P4B3TE'

# Extract propeller diameter from folder name
folder_name = os.path.basename(data_folder)
diameter_string = folder_name.split('P')[0][1:]  # Extract the part after 'D' and before 'P'
if '-' in diameter_string:
    propeller_diameter = float(diameter_string.replace('-', '.')) * 0.0254  # Convert inches to meters
else:
    propeller_diameter = float(diameter_string) * 0.0254  # Convert inches to meters

# Initialize an empty list to store DataFrames for each RPM
rpm_dataframes = []

# Function to calculate CQ from CP
def calculate_cq(cp):
    return cp / (2 * np.pi)

# Read each .dat file and store it in a DataFrame
for filename in os.listdir(data_folder):
    if filename.endswith('.dat'):
        rpm = int(filename.replace('.dat', ''))  # Extract RPM from filename
        file_path = os.path.join(data_folder, filename)
        
        # Read the data
        data = pd.read_csv(file_path, comment='#', header=None,
                           names=['V', 'J', 'eta', 'CT', 'CP', 'P', 'Q', 'T'])
        data['rpm'] = rpm
        data['CQ'] = calculate_cq(data['CP'])
        
        # Add missing integer airspeeds (0–100 m/s) if not present
        all_speeds = pd.DataFrame({'V': range(101)})  # Create a DataFrame with all integer airspeeds
        data = pd.merge(all_speeds, data, on='V', how='outer').sort_values('V')  # Merge to find missing speeds
        
        # Interpolate missing values
        data.interpolate(method='linear', inplace=True)
        data.fillna(0, inplace=True)  # Fill any remaining NaN values with 0
        
        # Append to the list of RPM DataFrames
        rpm_dataframes.append(data)


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

# Example: Access data for airspeed 10 m/s
print(propeller_data[25])

char = propeller_data

# Save the data dictionary to a pickle file in the 'full-characteristics' subdirectory
output_directory = os.path.join('reformatted_data', 'full-characteristics')
os.makedirs(output_directory, exist_ok=True)  # Create the subdirectory if it doesn't exist
output_file = os.path.join(output_directory, 'APC_Prop_' + folder_name + '.pickle')

with open(output_file, 'wb') as f:
    pickle.dump(char,f)