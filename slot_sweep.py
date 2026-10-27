
import csv
import math
import os
import traceback
from datetime import datetime
from pathlib import Path

os.environ["PYAEDT_USE_PRE_GRPC_ARGS"] = "True"

from ansys.aedt.core import Hfss, settings

settings.grpc_secure_mode = False

SLOT_WIDTHS_MM = [0.4]

# SLOT_WIDTHS_MM = [0.35, 0.375, 0.4, 0.425, 0.45, 0.475, 0.5]

# SLOT_WIDTHS_MM = [
#     0.3, 0.4, 0.5, 0.6,
#     0.7, 0.8, 0.9, 1.0
# ]

LENGTH_MM = 20.0
TOTAL_WIDTH_MM = 10.0
THICKNESS_MM = 1.5
FREQUENCY_GHZ = 37.4
INCIDENT_E_V_PER_M = 1.0

# Better mesh settings exceeded student version limit
# MIN_PASSES = 8
# MIN_CONVERGED_PASSES = 2
# MAX_PASSES = 15
# MAX_DELTA_S = 0.01
# PERCENT_REFINEMENT = 40

MIN_PASSES = 5
MIN_CONVERGED_PASSES = 2
MAX_PASSES = 10
MAX_DELTA_S = 0.01
PERCENT_REFINEMENT = 30


# -------------------------------------
# Output files
# -------------------------------------

RUN_FOLDER = Path(__file__).resolve().parent / (
    "slot_sweep_" + datetime.now().strftime("%Y%m%d_%H%M%S")
)

RUN_FOLDER.mkdir(parents=True, exist_ok=True)

PROJECT_FILE = RUN_FOLDER / "SiliconSlotSweep.aedt"
CSV_FILE = RUN_FOLDER / "slot_sweep_results.csv"

CSV_COLUMNS = [
    "slot_width_mm",
    "rail_width_mm",
    "mean_E_V_per_m",
    "max_E_V_per_m",
    "max_over_mean",
    "status",
    "error",
]


def width_tag(slot_width):
    return f"{slot_width:g}".replace(".", "p")


# -------------------------------------
# Build geometries
# -------------------------------------

def build_and_solve(hfss, slot_width):

    if not (0 < slot_width < TOTAL_WIDTH_MM):
        raise ValueError(
            f"Invalid slot width: {slot_width} mm"
        )

    rail_width = (TOTAL_WIDTH_MM - slot_width) / 2.0

    hfss.modeler.model_units = "mm"

    print(f"Slot width: {slot_width} mm")
    print(f"Rail width: {rail_width} mm")

    # Silicon rails
    rail_1 = hfss.modeler.create_box(
        origin=[0, 0, 0],
        sizes=[
            LENGTH_MM,
            rail_width,
            THICKNESS_MM,
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
            LENGTH_MM,
            rail_width,
            THICKNESS_MM,
        ],
        name="SiliconRail2",
        material="silicon",
    )

    if not rail_1 or not rail_2:
        raise RuntimeError("Silicon rail creation failed")

    print("Created silicon rails.")


    # -------------------------------------
    # Air region
    # -------------------------------------

    region = hfss.modeler.create_region(
        pad_value=[3, 3, 3, 3, 3, 3],
        pad_type="Absolute Offset",
        name="AirRegion",
    )

    if not region:
        raise RuntimeError("Air region creation failed")

    region.transparency = 0.85

    print("Created air region.")


    # -------------------------------------
    # Boundary
    # -------------------------------------

    radiation = hfss.assign_radiation_boundary_to_objects(
        region,
        name="RadiationBoundary",
    )

    if not radiation:
        raise RuntimeError("Radiation boundary creation failed")

    print("Created radiation boundary.")


    # -------------------------------------
    # RF wave
    # ------------------------------------- 

    plane_wave = hfss.plane_wave(
        vector_format="Cartesian",
        polarization=[0, 1, 0],
        propagation_vector=[1, 0, 0],
        name="IncidentRF",
    )

    if not plane_wave:
        raise RuntimeError("Incident plane wave creation failed")

    print("Created incident RF plane wave.")


    # -------------------------------------
    # Field sampling plane
    # -------------------------------------

    slot_plane = hfss.modeler.create_rectangle(
        orientation="XY",
        origin=[
            0,
            rail_width,
            THICKNESS_MM / 2,
        ],
        sizes=[
            LENGTH_MM,
            slot_width,
        ],
        name="SlotFieldPlane",
    )

    if not slot_plane:
        raise RuntimeError("Slot sampling plane creation failed")

    print("Created slot field sampling plane.")


    # -------------------------------------
    # HFSS solution
    # -------------------------------------

    setup = hfss.create_setup(
        name="Setup37GHz",
        setup_type="HFSSDriven",
    )

    if not setup:
        raise RuntimeError("HFSS setup creation failed")

    setup.props["Frequency"] = f"{FREQUENCY_GHZ}GHz"

    setup.props["MaximumPasses"] = MAX_PASSES
    setup.props["MinimumPasses"] = MIN_PASSES
    setup.props["MinimumConvergedPasses"] = MIN_CONVERGED_PASSES

    setup.props["MaxDeltaS"] = MAX_DELTA_S
    setup.props["PercentRefinement"] = PERCENT_REFINEMENT


    # -------------------------------------
    # Saves
    # -------------------------------------
    setup.props["IsEnabled"] = True
    setup.props["SaveAnyFields"] = True
    setup.props["SaveRadFieldsOnly"] = False

    if setup.update() is False:
        raise RuntimeError("HFSS setup update failed")

    hfss.save_project()


    # -------------------------------------
    # EM solution
    # -------------------------------------

    print()
    print("Starting HFSS solve...", flush=True)

    solved = setup.analyze()

    # Some PyAEDT versions return None after a successful
    # solve. Only an explicit False is treated as failure.

    if solved is False:
        raise RuntimeError(
            "HFSS reported an unsuccessful solve"
        )

    print(
        f"Solve returned {solved!r}; "
        "extracting field results...",
        flush=True,
    )


    # -------------------------------------
    # Set plane wave (1V/m)
    # -------------------------------------

    hfss.osolution.EditSources(
        [
            [
                "FieldType:=", "TotalFields",
                "IncludePortPostProcessing:=", False,
                "SpecifySystemPower:=", False,
            ],
            [
                "Name:=", plane_wave.name,
                "Magnitude:=",
                f"{INCIDENT_E_V_PER_M:g}V_per_meter",
                "Phase:=", "0deg",
            ],
        ]
    )


    # -------------------------------------
    # Solves the field
    # -------------------------------------

    solution_name = hfss.nominal_adaptive

    intrinsics = {
        "Freq": f"{FREQUENCY_GHZ}GHz",
    }

    def field_stat(function):

        number = hfss.post.get_scalar_field_value(
            quantity="ComplexMag_E",
            scalar_function=function,
            solution=solution_name,
            intrinsics=intrinsics,
            object_name=slot_plane.name,
            object_type="surface",
        )

        if number is None or isinstance(number, bool):
            raise RuntimeError(
                f"Cannot calculate {function} field: "
                f"{number!r}"
            )

        number = float(number)

        if not math.isfinite(number):
            raise RuntimeError(
                f"Non-finite {function} field: {number!r}"
            )

        return number


    # Average electric field
    e_mean = field_stat("Mean")

    # Maximum electric field
    e_max = field_stat("Maximum")

    if e_mean <= 0:
        raise RuntimeError(
            f"Mean electric field is not positive: {e_mean}"
        )

    max_over_mean = e_max / e_mean


    # -------------------------------------
    # Field plot
    # -------------------------------------

    try:
        hfss.post.create_fieldplot_surface(
            assignment=slot_plane.faces,
            quantity="ComplexMag_E",
            setup=solution_name,
            intrinsics=intrinsics,
            plot_name="SiliconSlotElectricField",
        )

    except Exception as exc:
        print(f"Warning: field plot failed: {exc}")

    hfss.save_project()


    # -------------------------------------
    # Results
    # -------------------------------------

    print()
    print(f"Average |E|: {e_mean:.6f} V/m")
    print(f"Maximum |E|: {e_max:.6f} V/m")
    print(f"Max / average: {max_over_mean:.3f}")

    return {
        "slot_width_mm": slot_width,
        "rail_width_mm": rail_width,
        "mean_E_V_per_m": e_mean,
        "max_E_V_per_m": e_max,
        "max_over_mean": max_over_mean,
        "status": "OK",
        "error": "",
    }


# -------------------------------------
# Save
# -------------------------------------

def write_csv(rows):

    with CSV_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as output:

        writer = csv.DictWriter(
            output,
            fieldnames=CSV_COLUMNS,
        )

        writer.writeheader()
        writer.writerows(rows)


# -------------------------------------
# Plot
# -------------------------------------

def plot_results(rows):

    successes = sorted(
        [r for r in rows if r["status"] == "OK"],
        key=lambda r: r["slot_width_mm"],
    )

    if not successes:
        return

    try:
        import matplotlib.pyplot as plt

    except ImportError:
        print("Matplotlib not installed; skipping graphs.")
        return

    widths = [r["slot_width_mm"] for r in successes]
    means = [r["mean_E_V_per_m"] for r in successes]
    maxima = [r["max_E_V_per_m"] for r in successes]
    ratios = [r["max_over_mean"] for r in successes]

    fig, ax = plt.subplots()

    ax.plot(
        widths,
        means,
        marker="o",
        label="Mean |E|",
    )

    ax.plot(
        widths,
        maxima,
        marker="o",
        label="Maximum |E|",
    )

    ax.set_xlabel("Slot width (mm)")
    ax.set_ylabel("Electric field (V/m)")
    ax.set_title("Electric field vs slot width")

    ax.grid(True)
    ax.legend()

    fig.tight_layout()

    fig.savefig(
        RUN_FOLDER / "field_vs_slot_width.png",
        dpi=180,
    )

    plt.close(fig)


    # Max / mean vs slot width

    fig, ax = plt.subplots()

    ax.plot(
        widths,
        ratios,
        marker="o",
    )

    ax.set_xlabel("Slot width (mm)")
    ax.set_ylabel("Maximum |E| / Mean |E|")
    ax.set_title("Field nonuniformity vs slot width")

    ax.grid(True)

    fig.tight_layout()

    fig.savefig(
        RUN_FOLDER / "max_over_mean_vs_slot_width.png",
        dpi=180,
    )

    plt.close(fig)


# -------------------------------------
# Parameter sweep
# -------------------------------------

def main():

    print("Results folder:", RUN_FOLDER)
    print("HFSS project:", PROJECT_FILE)
    print("Slot widths:", SLOT_WIDTHS_MM)

    if not SLOT_WIDTHS_MM:
        raise ValueError("No slot widths specified")

    if len(set(SLOT_WIDTHS_MM)) != len(SLOT_WIDTHS_MM):
        raise ValueError("Duplicate slot widths specified")

    rows = []
    write_csv(rows)

    hfss = Hfss(
        project=str(PROJECT_FILE),
        design=f"Slot_{width_tag(SLOT_WIDTHS_MM[0])}",
        version="2025.2",
        new_desktop=True,
        non_graphical=False,
        student_version=True,
        close_on_exit=False,
        solution_type="Modal",
    )

    for index, width in enumerate(SLOT_WIDTHS_MM):

        design_name = f"Slot_{width_tag(width)}"

        print()
        print(
            f"[{index + 1}/{len(SLOT_WIDTHS_MM)}] "
            f"{design_name}",
            flush=True,
        )

        record = {
            "slot_width_mm": width,
            "rail_width_mm": (TOTAL_WIDTH_MM - width) / 2,
            "status": "ERROR",
            "error": "Not completed",
        }

        try:

            if index > 0:

                hfss.insert_design(
                    name=design_name,
                    solution_type="Modal",
                )

            active_name = hfss.design_name

            if (
                active_name != design_name
                and design_name in hfss.design_list
            ):
                hfss.set_active_design(design_name)
                active_name = hfss.design_name

            if active_name != design_name:
                raise RuntimeError(
                    f"Could not activate {design_name}; "
                    f"active design: {active_name!r}; "
                    f"available designs: {hfss.design_list!r}"
                )

            print(
                f"Active HFSS design: {active_name}",
                flush=True,
            )

            record = build_and_solve(hfss, width)

            print(
                f"Mean: {record['mean_E_V_per_m']:.6f} V/m; "
                f"Max: {record['max_E_V_per_m']:.6f} V/m; "
                f"Max/Mean: {record['max_over_mean']:.3f}",
                flush=True,
            )

        except Exception as exc:

            print(
                f"ERROR in {design_name}: {exc}",
                flush=True,
            )

            traceback.print_exc()

            record["error"] = str(exc)


        # Save results after every geometry

        rows.append(record)
        write_csv(rows)

        try:
            hfss.save_project()

        except Exception as exc:
            print(f"Warning: project save failed: {exc}")


    # -------------------------------------
    # Graph
    # -------------------------------------

    plot_results(rows)

    print()
    print("Parameter sweep finished.")
    print("CSV saved to:", CSV_FILE)
    print("Review ERROR rows before interpreting graphs.")


if __name__ == "__main__":
    main()
