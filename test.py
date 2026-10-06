import os

os.environ["PYAEDT_USE_PRE_GRPC_ARGS"] = "True"

from ansys.aedt.core import Hfss, settings

settings.grpc_secure_mode = False

hfss = Hfss(
    version="2025.2",
    new_desktop=True,
    non_graphical=False,
    student_version=True,
    close_on_exit=False,
)

hfss.modeler.model_units = "mm"

block = hfss.modeler.create_box(
    origin=[0, 0, 0],
    sizes=[20, 10, 1.5],
    name="SiliconBlock",
    material="silicon",
)

print("Connected to HFSS successfully.")
print("Created:", block.name)