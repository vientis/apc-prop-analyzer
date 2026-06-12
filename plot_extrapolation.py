#!/usr/bin/env python3
"""
Verification plot for the negative thrust/torque extrapolation.

Plots thrust and torque vs RPM for the D13P10B2TE propeller at 0, 27 and 42 m/s.
Existing (measured) points are drawn in dark blue; the supplemented extrapolated
points (below the zero-thrust / windmilling regime) are drawn in light blue.

Run after regenerating the pickle with characteristic_generator.py (extrapolation on):
    .venv/bin/python plot_extrapolation.py
"""

import os
import pickle

import matplotlib
matplotlib.use('Agg')  # headless: write a file, no display needed
import matplotlib.pyplot as plt

PROPELLER = 'D13P10B2TE'
AIRSPEEDS = [0, 27, 42]  # m/s
PICKLE_DIR = 'reformatted_data/full-characteristics'
OUTPUT_DIR = 'plots'

EXISTING_COLOR = '#08306b'  # dark blue  - measured data
NEW_COLOR = '#6baed6'       # light blue - extrapolated data


def load_propeller(name):
    path = os.path.join(PICKLE_DIR, f'APC_Prop_{name}.pickle')
    with open(path, 'rb') as f:
        return pickle.load(f)


def main():
    data = load_propeller(PROPELLER)

    fig, axes = plt.subplots(2, len(AIRSPEEDS), figsize=(15, 8), sharex=True)
    fig.suptitle(
        f'{PROPELLER}: thrust & torque vs RPM with negative-thrust extrapolation\n'
        'dark blue = measured (APC), light blue = extrapolated (windmilling/drag)',
        fontsize=13)

    # (column metric, y-axis label) for the two rows
    rows = [('T', 'Thrust (N)'), ('Q', 'Torque (N·m)')]

    for col, v in enumerate(AIRSPEEDS):
        df = data[v].sort_values('rpm')
        existing = df[~df['extrapolated']]
        new = df[df['extrapolated']]

        for row, (metric, ylabel) in enumerate(rows):
            ax = axes[row, col]
            ax.axhline(0, color='grey', linewidth=0.8, linestyle='--', zorder=1)
            ax.scatter(existing['rpm'], existing[metric],
                       color=EXISTING_COLOR, s=30, zorder=3, label='existing (measured)')
            if len(new) > 0:
                ax.scatter(new['rpm'], new[metric],
                           color=NEW_COLOR, s=30, zorder=2, label='extrapolated')

            if row == 0:
                ax.set_title(f'V = {v} m/s')
            if col == 0:
                ax.set_ylabel(ylabel)
            if row == len(rows) - 1:
                ax.set_xlabel('RPM')
            ax.grid(True, alpha=0.3)
            if row == 0 and col == 0:
                ax.legend(loc='upper left', fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.94])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f'{PROPELLER}_thrust_torque_extrapolation.png')
    fig.savefig(out_path, dpi=150)
    print(f'Saved plot to {out_path}')


if __name__ == '__main__':
    main()
