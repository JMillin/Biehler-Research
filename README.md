# Rydberg Vapor Cell Simulation

This repository contains the current workflow for simulating and optimizing Rydberg-atom vapor cell geometries for RF electric-field enhancement.

The simulations are performed in **ANSYS HFSS** and controlled through Python using **PyAEDT**.

The current model is very simplified and is being used to validate a baseline before adding more complicated features.

## Current model

- Device length: 20 mm
- Total width: 10 mm
- Silicon thickness: 1.5 mm
- Vapor slot width: 0.5 mm
- Silicon rail width: 4.75 mm
- Surrounding air region: 3 mm padding on all sides

The vapor cell is modeled as the gap between the silicon rails. 

Applied RF plane-wave:

- Frequency: 37.4 GHz
- Propagation direction: +x
- Electric-field polarization: +y
- Incident electric-field amplitude: 1 V/m

The field quantity used is `ComplexMag_E`, which gives the phase-independent magnitude of the complex electric field.

## Files

### `test.py`

Simple PyAEDT/HFSS connection test. Confirms that Python can control HFSS

### `air_reference.py`

Free-space reference simulation. This is meant to confirm that a 1 V/m plane wave is measured as such.

Current result:

- Average |E| = 0.993253 V/m

### `rydberg.py`

Main silicon-slot simulation. This constructs the simulation and runs the HFSS solution. It extracts the electric field and compares it to the free-space reference.

Current result:

- Average |E| in silicon slot = 3.078884 V/m
- Maximum |E| in silicon slot = 6.498128 V/m
- Average field enhancement = approximately 3.10x
- Maximum local field enhancement = approximately 6.48x

- ## Software

- Windows
- ANSYS Electronics Desktop Student 2025 R2
- Python 3.11
- PyAEDT
- Conda environment
