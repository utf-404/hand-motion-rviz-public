"""Mirror the existing ROS 2 hand tracking stream in Isaac Sim."""

import argparse
import json
import math
import sys
import time
from pathlib import Path

from isaac_hand.model import load_hand_model


def ordered_targets(names, positions, dof_names):
    """Return a complete finite pose in Isaac Sim's articulation order."""
    if len(names) != len(dof_names) or len(positions) != len(dof_names):
        return None
    by_name = dict(zip(names, positions))
    if by_name.keys() != set(dof_names) or not all(map(math.isfinite, positions)):
        return None
    return [by_name[name] for name in dof_names]


def set_up_view(stage):
    from pxr import Gf, UsdGeom, UsdLux

    camera = UsdGeom.Camera.Define(stage, "/HandsView")
    camera.CreateFocalLengthAttr(26.0)
    camera.CreateClippingRangeAttr(Gf.Vec2f(0.01, 10.0))
    # The palm faces -Z and the fingers point +X. Positive Y is screen right.
    view = Gf.Matrix4d(1).SetLookAt(
        Gf.Vec3d(0.035, 0, -0.72), Gf.Vec3d(0.035, 0, 0), Gf.Vec3d(1, 0, 0),
    )
    UsdGeom.Xformable(camera).AddTransformOp().Set(view.GetInverse())

    fill = UsdLux.DomeLight.Define(stage, "/FillLight")
    fill.CreateIntensityAttr(350.0)
    key = UsdLux.DistantLight.Define(stage, "/KeyLight")
    key.CreateIntensityAttr(1400.0)
    key.CreateAngleAttr(30.0)
    UsdGeom.Xformable(key).AddRotateXYZOp().Set(Gf.Vec3f(153, -23, 0))
    return camera.GetPath()


def make_subscriber(topic):
    import omni.graph.core as og

    keys = og.Controller.Keys
    _, (_, subscriber), _, _ = og.Controller.edit(
        {"graph_path": "/HandMotion", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("Tick", "omni.graph.action.OnPlaybackTick"),
                ("Subscribe", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
            ],
            keys.CONNECT: [("Tick.outputs:tick", "Subscribe.inputs:execIn")],
            keys.SET_VALUES: [
                ("Subscribe.inputs:topicName", topic),
                ("Subscribe.inputs:queueSize", 1),
            ],
        },
    )
    return tuple(og.Controller.attribute(f"outputs:{name}", subscriber)
                 for name in ("jointNames", "positionCommand", "timeStamp"))


def simulate(app, args):
    import numpy as np
    import omni.kit.app
    import omni.timeline
    import omni.usd

    manager = omni.kit.app.get_app().get_extension_manager()
    for extension in ("isaacsim.asset.importer.urdf", "isaacsim.ros2.bridge",
                      "isaacsim.core.experimental.prims"):
        manager.set_extension_enabled_immediate(extension, True)
        if not manager.is_extension_enabled(extension):
            raise RuntimeError(f"Could not enable {extension}")
    app.update()

    from isaacsim.core.experimental.prims import Articulation

    root, expected = load_hand_model(args.urdf, args.package_root, args.work_dir)
    stage = omni.usd.get_context().get_stage()
    camera_path = set_up_view(stage)
    if args.headless_seconds is None:
        from omni.kit.viewport.utility import get_active_viewport

        viewport = get_active_viewport()
        if viewport is None:
            raise RuntimeError("No Isaac Sim viewport is available")
        viewport.camera_path = camera_path

    names, positions, stamp = make_subscriber(args.topic)
    articulation = Articulation(root)
    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    print(f"Listening for {len(expected)} hand joints on {args.topic}", flush=True)

    frame_count = 0
    previous_stamp = None
    dof_names = None
    low = high = measured = None
    deadline = (None if args.headless_seconds is None
                else time.monotonic() + args.headless_seconds)
    try:
        while app.is_running() and (deadline is None or time.monotonic() < deadline):
            app.update()
            if not timeline.is_playing():
                continue
            if dof_names is None:
                dof_names = articulation.dof_names
                if len(dof_names) != len(expected) or set(dof_names) != expected:
                    raise RuntimeError("The loaded articulation does not expose all 36 URDF joints")

            targets = ordered_targets(names.get(), positions.get(), dof_names)
            if targets is None:
                continue
            with np.errstate(over="ignore"):
                target_array = np.asarray([targets], dtype=np.float32)
            if not np.isfinite(target_array).all():
                continue
            articulation.set_dof_position_targets(target_array)

            current_stamp = stamp.get()
            if current_stamp != previous_stamp:
                previous_stamp = current_stamp
                frame_count += 1
                if frame_count == 1:
                    print(f"Received and applied {len(dof_names)} joint targets", flush=True)

            if deadline is not None:
                measured = articulation.get_dof_positions().numpy()[0]
                if not np.isfinite(measured).all():
                    raise RuntimeError("Isaac Sim returned non-finite hand joint angles")
                low = measured.copy() if low is None else np.minimum(low, measured)
                high = measured.copy() if high is None else np.maximum(high, measured)

        if deadline is not None:
            if measured is None:
                raise RuntimeError(f"No complete hand pose received on {args.topic}")
            print("Headless result " + json.dumps({
                "frames": frame_count,
                "joint_count": len(dof_names),
                "ranges_rad": dict(zip(dof_names, (high - low).tolist())),
                "final_rad": dict(zip(dof_names, measured.tolist())),
            }), flush=True)
    finally:
        timeline.stop()


def positive_duration(value):
    duration = float(value)
    if not math.isfinite(duration) or duration <= 0:
        raise argparse.ArgumentTypeError("expected a finite duration greater than zero")
    return duration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--topic", default="/joint_states")
    parser.add_argument("--headless-seconds", type=positive_duration)
    args = parser.parse_args()

    from isaacsim import SimulationApp

    headless = args.headless_seconds is not None
    app = SimulationApp({
        "headless": headless,
        "disable_viewport_updates": headless,
        "fast_shutdown": True,
        "multi_gpu": False,
    })
    status = 0
    try:
        simulate(app, args)
    except KeyboardInterrupt:
        status = 130
    except Exception as error:
        print(f"Hand motion: {error}", file=sys.stderr, flush=True)
        status = 1
    finally:
        app.close(exit_code=status)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
