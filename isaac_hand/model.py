"""Prepare the RViz hand description for Isaac Sim articulation control."""

from pathlib import Path
from xml.etree import ElementTree


def _prepare_urdf(urdf_path: Path, package_root: Path, output_path: Path) -> set[str]:
    tree = ElementTree.parse(urdf_path)
    robot = tree.getroot()
    if robot.tag != "robot":
        raise ValueError(f"Expected an expanded robot URDF at {urdf_path}")

    package_uri = "package://hand_motion_rviz/"
    for mesh in robot.iter("mesh"):
        filename = mesh.attrib["filename"]
        if filename.startswith(package_uri):
            path = package_root / filename.removeprefix(package_uri)
        else:
            path = urdf_path.parent / filename
        if not path.is_file():
            raise FileNotFoundError(f"Hand mesh {filename!r} was not found at {path}")
        mesh.set("filename", str(path.resolve()))

    for link in robot.findall("link"):
        if link.find("inertial") is not None:
            continue
        # Keep the empty mounts and wrist pivots connected to a physical base.
        # These approximate inertias keep visual mirroring stable without colliders.
        base = link.get("name") == "hands_base"
        inertial = ElementTree.SubElement(link, "inertial")
        ElementTree.SubElement(inertial, "mass", value="0.2" if base else "0.02")
        moment = "0.001" if base else "0.00003"
        ElementTree.SubElement(
            inertial, "inertia", ixx=moment, ixy="0", ixz="0",
            iyy=moment, iyz="0", izz=moment,
        )

    joints = [joint.attrib["name"] for joint in robot.findall("joint")
              if joint.get("type") in ("revolute", "continuous")]
    if len(joints) != 36 or len(set(joints)) != 36:
        raise ValueError(f"Expected 36 distinct angular hand joints in {urdf_path}")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return set(joints)


def load_hand_model(urdf_path: Path, package_root: Path, work_dir: Path) -> tuple[str, set[str]]:
    """Open the PhysX stage and return its fixed articulation root and joint names."""
    import omni.usd
    from isaacsim.asset.importer.urdf import URDFImporter, URDFImporterConfig
    from pxr import UsdPhysics

    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    physics_urdf = work_dir / "hands_physics.urdf"
    joint_names = _prepare_urdf(urdf_path, package_root, physics_urdf)

    usd_dir = work_dir / "usd"
    usd_dir.mkdir(exist_ok=True)
    config = URDFImporterConfig()
    config.urdf_path = str(physics_urdf)
    config.usd_path = str(usd_dir)
    config.fix_base = True
    config.merge_fixed_joints = True
    config.allow_self_collision = False
    config.collision_from_visuals = False
    importer = URDFImporter()
    importer.config = config
    usd_path = importer.import_urdf()

    context = omni.usd.get_context()
    if not usd_path or not context.open_stage(str(usd_path)):
        raise RuntimeError(f"Could not open the imported hand stage at {usd_path!r}")
    stage = context.get_stage()
    model = stage.GetDefaultPrim()
    if not model or not model.GetVariantSet("Physics").SetVariantSelection("physx"):
        raise RuntimeError(f"The hand stage has no selectable PhysX variant at {usd_path}")
    UsdPhysics.Scene.Define(stage, "/WorldPhysics").CreateGravityMagnitudeAttr(0.0)

    roots = [prim for prim in stage.Traverse() if prim.HasAPI(UsdPhysics.ArticulationRootAPI)]
    if len(roots) != 1:
        raise RuntimeError(f"Expected one fixed hand articulation, found {len(roots)} at {usd_path}")
    joints = [prim for prim in stage.Traverse() if prim.IsA(UsdPhysics.RevoluteJoint)]
    imported = {str(joint.GetName()) for joint in joints}
    if len(joints) != len(joint_names) or imported != joint_names:
        missing = sorted(joint_names - imported)
        unexpected = sorted(imported - joint_names)
        raise RuntimeError(f"Imported hand joints differ: missing={missing}, unexpected={unexpected}")
    for joint in joints:
        drive = UsdPhysics.DriveAPI.Apply(joint, "angular")
        drive.CreateStiffnessAttr().Set(20.0)
        drive.CreateDampingAttr().Set(2.0)

    return str(roots[0].GetPath()), joint_names
