import os

# Needed for AEDT Student 2025 R2
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

print("HFSS solution type:", hfss.solution_type)

length = 20.0
width = 10.0
thickness = 1.5
slot_width = 0.5

rail_width = (width - slot_width) / 2


# -------------------------------------
# # Air region
# -------------------------------------
#
# x = -3 to 23 mm
# y = -3 to 13 mm
# z = -3 to 4.5 mm

region = hfss.modeler.create_box(
    origin=[-3, -3, -3],
    sizes=[26, 16, 7.5],
    name="AirRegion",
    material="air",
)

region.transparency = 0.85

radiation = hfss.assign_radiation_boundary_to_objects(
    region,
    name="RadiationBoundary",
)

plane_wave = hfss.plane_wave(
    vector_format="Cartesian",
    polarization=[0, 1, 0],
    propagation_vector=[1, 0, 0],
    name="IncidentRF",
)

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
    name="ReferenceFieldPlane",
)

setup = hfss.create_setup(
    name="Setup37GHz",
    setup_type="HFSSDriven",
)

setup.props["Frequency"] = "37.4GHz"

setup.props["MinimumPasses"] = 5
setup.props["MinimumConvergedPasses"] = 2
setup.props["MaximumPasses"] = 10
setup.props["MaxDeltaS"] = 0.01
setup.props["PercentRefinement"] = 30

setup.props["IsEnabled"] = True
setup.props["SaveAnyFields"] = True
setup.props["SaveRadFieldsOnly"] = False

setup.update()

hfss.save_project()

solve_ok = setup.analyze()

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

slot_faces = slot_plane.faces

field_plot = hfss.post.create_fieldplot_surface(
    assignment=slot_faces,
    quantity="ComplexMag_E",
    setup=hfss.nominal_adaptive,
    intrinsics={
        "Freq": "37.4GHz",
    },
    plot_name="FreeSpaceElectricField",
)

solution_name = hfss.nominal_adaptive

intrinsics = {
    "Freq": "37.4GHz",
}

reference_e_mean = hfss.post.get_scalar_field_value(
    quantity="ComplexMag_E",
    scalar_function="Mean",
    solution=solution_name,
    intrinsics=intrinsics,
    object_name=slot_plane.name,
    object_type="surface",
)

reference_e_max = hfss.post.get_scalar_field_value(
    quantity="ComplexMag_E",
    scalar_function="Maximum",
    solution=solution_name,
    intrinsics=intrinsics,
    object_name=slot_plane.name,
    object_type="surface",
)

print(f"Average |E|: {reference_e_mean:.6f} V/m")
print(f"Maximum |E|: {reference_e_max:.6f} V/m")

if reference_e_mean != 0:
    print(
        f"Max / average: "
        f"{reference_e_max / reference_e_mean:.3f}"
    )

print("Complete")