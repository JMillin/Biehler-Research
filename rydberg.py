import os

os.environ["PYAEDT_USE_PRE_GRPC_ARGS"] = "True"

from ansys.aedt.core import Hfss, settings

settings.grpc_secure_mode = False

hfss = Hfss(
    version="2025.2",
    new_desktop=False,
    non_graphical=False,
    student_version=True,
    close_on_exit=False,
    solution_type="Modal",
)

hfss.modeler.model_units = "mm"

# -------------------------------------
# Geometry
# -------------------------------------

# In mm
length = 20.0
width = 10.0
thickness = 1.5
slot_width = 0.5

# Silicon rails
rail_width = (width - slot_width) / 2

print(f"Slot width: {slot_width} mm")


# Silicon rails

rail_1 = hfss.modeler.create_box(
    origin=[0, 0, 0],
    sizes=[
        length,
        rail_width,
        thickness,
    ],
    name="SiliconRail1",
    material="silicon",
)

rail_2 = hfss.modeler.create_box(
    origin=[
        0,
        rail_width + slot_width,
        0,
    ],
    sizes=[
        length,
        rail_width,
        thickness,
    ],
    name="SiliconRail2",
    material="silicon",
)

print("Created silicon rails.")


# -------------------------------------
# Air region
# -------------------------------------
#
# Allows HFSS to solve Maxwell's equations
#
# Add 3 mm of air around every side of the device.
#
# x = -3 to 23 mm
# y = -3 to 13 mm
# z = -3 to 4.5 mm

region = hfss.modeler.create_region(
    pad_value=[3, 3, 3, 3, 3, 3],
    pad_type="Absolute Offset",
    name="AirRegion",
)

region.transparency = 0.85

print("Created air region.")


# -------------------------------------
# Radiation boundary
# -------------------------------------
#
# Waves continue to propogate in open space

radiation = hfss.assign_radiation_boundary_to_objects(
    region,
    name="RadiationBoundary",
)

print("Created radiation boundary.")


# -------------------------------------
# RF wave
# -------------------------------------
#
# RF propagation direction = +X
# Electric-field polarization = +Y
#
# E-field points across the silicon-vapor interface

plane_wave = hfss.plane_wave(
    vector_format="Cartesian",
    polarization=[0, 1, 0],
    propagation_vector=[1, 0, 0],
    name="IncidentRF",
)

print("Created incident RF plane wave.")


# -------------------------------------
# Field sampling plane
# -------------------------------------
#
#
# x = 0 to 20 mm
# y = 4.75 to 5.25 mm
# z = 0.75 mm

slot_plane = hfss.modeler.create_rectangle(
    orientation="XY",
    origin=[
        0,
        rail_width,
        thickness / 2,
    ],
    sizes=[
        length,
        slot_width,
    ],
    name="SlotFieldPlane",
)

print("Created slot field sampling plane.")


# -------------------------------------
# HFSS solution
# -------------------------------------

setup = hfss.create_setup(
    name="Setup37GHz",
    setup_type="HFSSDriven",
)

# Operating frequency from paper
setup.props["Frequency"] = "37.4GHz"

setup.props["MinimumPasses"] = 5
setup.props["MinimumConvergedPasses"] = 2
setup.props["MaximumPasses"] = 10

setup.props["MaxDeltaS"] = 0.01
setup.props["PercentRefinement"] = 30


# -------------------------------------
# Saves
# -------------------------------------

setup.props["IsEnabled"] = True
setup.props["SaveAnyFields"] = True
setup.props["SaveRadFieldsOnly"] = False

setup.update()

hfss.save_project()

# -------------------------------------
# EM solution
# -------------------------------------

print()
print("Starting silicon-device HFSS solve...")

solve_ok = setup.analyze()

print("Solve returned:", solve_ok)
print("Available solutions:", hfss.existing_analysis_sweeps)
print("Nominal adaptive solution:", hfss.nominal_adaptive)


# -------------------------------------
# Set plane wave (1V/m)
# -------------------------------------
#
# E_total = E_incident + E_scattered

hfss.osolution.EditSources(
    [
        [
            "FieldType:=", "TotalFields",
            "IncludePortPostProcessing:=", False,
            "SpecifySystemPower:=", False,
        ],
        [
            "Name:=", plane_wave.name,
            "Magnitude:=", "1V_per_meter",
            "Phase:=", "0deg",
        ],
    ]
)


# -------------------------------------
# EF plot
# -------------------------------------
#
# ComplexMag_E: the phase-independent amplitude

slot_faces = slot_plane.faces

field_plot = hfss.post.create_fieldplot_surface(
    assignment=slot_faces,
    quantity="ComplexMag_E",
    setup=hfss.nominal_adaptive,
    intrinsics={
        "Freq": "37.4GHz",
    },
    plot_name="SiliconSlotElectricField",
)


# -------------------------------------
# Solves the field
# -------------------------------------

print()
print("Calculating field values in the Cs slot...")

solution_name = hfss.nominal_adaptive

intrinsics = {
    "Freq": "37.4GHz",
}


# -------------------------------------
# Average |E| across the sampling plane
# -------------------------------------

e_mean = hfss.post.get_scalar_field_value(
    quantity="ComplexMag_E",
    scalar_function="Mean",
    solution=solution_name,
    intrinsics=intrinsics,
    object_name=slot_plane.name,
    object_type="surface",
)


# -------------------------------------
# # Maximum |E| on the sampling plane
# -------------------------------------

e_max = hfss.post.get_scalar_field_value(
    quantity="ComplexMag_E",
    scalar_function="Maximum",
    solution=solution_name,
    intrinsics=intrinsics,
    object_name=slot_plane.name,
    object_type="surface",
)


# -------------------------------------
# Results
# -------------------------------------

print(f"Average |E|: {e_mean:.6f} V/m")
print(f"Maximum |E|: {e_max:.6f} V/m")

if e_mean != 0:
    print(f"Max / average: {e_max / e_mean:.3f}")



# -------------------------------------
# Compare with free space reference
# -------------------------------------

reference_e_mean = 0.993253
reference_e_max = 1.002625


mean_enhancement = e_mean / reference_e_mean
max_enhancement = e_max / reference_e_max


print()
print("SILICON vs FREE SPACE")
print("----------------------")

print(f"Silicon average |E|:   {e_mean:.6f} V/m")
print(f"Free-space average:    {reference_e_mean:.6f} V/m")
print(f"Average enhancement:   {mean_enhancement:.3f} x")

print()

print(f"Silicon maximum |E|:   {e_max:.6f} V/m")
print(f"Free-space maximum:    {reference_e_max:.6f} V/m")
print(f"Maximum enhancement:   {max_enhancement:.3f} x")

print()
print("Complete")