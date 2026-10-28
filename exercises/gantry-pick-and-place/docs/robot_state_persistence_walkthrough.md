# Robot state persistence walkthrough

## Why

The exercise bonus asks to save the **configuration** between restarts, which Step 3 already does. But the simulated robot was created fresh at every startup, so after a restart it always appeared at (0, 0, 0) with the gripper open and the cube back on Table A, wherever things really were. The dashboard would then show a state that doesn't match the cell.

Now the robot's **last known physical state** is saved too, and restored at startup:
- the robot's position;
- whether the gripper is closed;
- where the simulated cube is, and whether it's being held.

```
every state transition ──callback──▶ machine.robot_snapshot() ──▶ RobotStateStore.save() ──▶ SQLite
                                       (move done, grip, stop, fault, …)
startup:  RobotStateStore.load() ──▶ RobotDriver(initial_position=saved) ──▶ machine.restore_robot_state(saved)
shutdown: cancel motion ──▶ save once more (covers a shutdown mid-move)
```

---

## 1. `machine.py`: snapshot and restore

```python
@dataclass
class RobotSnapshot:
    position: list[float]
    gripper_closed: bool
    cube_position: list[float]
    cube_held: bool
```

A plain dataclass for the robot's physical state. It lives in `machine.py` because the simulated cube (held or resting) is the machine's concept.

```python
def robot_snapshot(self) -> RobotSnapshot: ...
def restore_robot_state(self, snapshot: RobotSnapshot) -> None: ...
```

- **`robot_snapshot()`** reads the driver's position and gripper, plus the machine's cube state.
- **`restore_robot_state()`** closes or opens the gripper and restores the cube (`_holding_cube`, `_cube_rest`). It **doesn't** set the position: the driver was already built at the saved position (section 2). The machine never teleports the robot, and the `GantryDriver` protocol has no "set position" method on purpose, since a real robot couldn't do that.
- **The machine still restarts in `ready`**, never mid-sequence (last-state recovery stays disabled). Resuming a half-finished motion after a crash, without knowing what happened in between, would be unsafe. If the robot was stopped mid-carry, it comes back in `ready` holding the cube, and the operator decides what to do next.
- **A restart also clears an unacknowledged fault:** the machine comes back in `ready` with no error message, even if it was in `fault` before. Persisting the fault and requiring Reset after a restart would be the stricter choice. It's listed here as a known trade-off.

`machine.py` still knows nothing about the database. It only offers a snapshot and a restore; saving is wired up in `main.py`.

---

## 2. `robot_driver.py`: `initial_position`

```python
def __init__(self, initial_position=(0.0, 0.0, 0.0), home_position=(0.0, 0.0, 0.0)):
```

- The simulated robot starts where it's told. `main.py` passes the saved position.
- It **raises `MotionError` if the starting position is outside the limits.** The simulator never checks its initial position, and a saved value could be bad (e.g. a hand-edited or corrupted database).
- This brings back a constructor parameter on `RobotDriver`. Unlike the removed `robot` parameter, it has a real caller.

---

## 3. `config_store.py`: `RobotStateRecord` and `RobotStateStore`

```python
class RobotStateRecord(SQLModel, table=True):
    __tablename__ = "robot_state"
    id; x; y; z; gripper_closed; cube_x; cube_y; cube_z; cube_held
```

- A second single-row table (`id = 1`), flattened like `ConfigRecord` (one column per value).
- **`RobotStateStore`** mirrors `ConfigStore`: `load()` returns a `RobotSnapshot` or `None`, and `save(snapshot)` writes it through the same `ModelAccessor`, still without `bootstrap()`, so there are no HTTP endpoints for it.
- Saves are recorded in the library's audit log with the actor `"machine"`. That adds about 10 small audit rows per pick-and-place cycle. That's fine for this exercise; a long-running production cell would want to prune them, or write this table without auditing.
- The file keeps its name, `config_store.py`, since it's the app's persistence module. Its docstring now says it stores both.

---

## 4. `main.py`: wiring

### When the state is saved

```python
machine.add_state_change_callback(lambda *_: save_robot_state(machine, state_store))
```

- The library calls state-change callbacks after **every successful transition**. Transitions happen exactly at the interesting moments: a move finished (each step fires `next`/`done`), the gripper closed or opened, a stop or fault, a reset. So the state is saved at each of those points.
- It's **not** saved on every 20 ms poll of a move. That would mean about 50 database writes per second for no real benefit.
- `save_robot_state` catches and logs any error. A failed save must never break a transition.

Also at **shutdown** (`lifespan`'s `finally`): running motion is cancelled first, so the driver stops where it is, and then the state is saved once more. That covers a normal shutdown in the middle of a move.

### Startup

```python
driver, snapshot = load_startup_robot(state_store)
config = load_startup_config(config_store, driver.limits)
machine = create_machine(driver, config, state_store, snapshot)
```

- **`load_startup_robot`** builds `RobotDriver(initial_position=saved_position)`. If nothing was saved, or the saved position is invalid, it falls back to a robot at the origin and ignores the saved state.
- **`create_machine`** builds the machine, applies the config, restores the gripper and cube, and attaches the save callback. Order matters: applying the config resets the cube to its configured start, so the saved cube state is restored **after** it.
- Tests build their machines with the same `create_machine`, so they exercise the same wiring as the real app.

### The limitation: a hard kill mid-move

If the server is **killed** during a move (crash, power loss, `Stop-Process -Force`), no shutdown code runs. The saved position is then the one from the last transition, i.e. where the current move **started**, not where it was interrupted. A real gantry solves this by reading its encoders, or by homing at startup. For a simulator, "position at the last completed step" is a reasonable approximation.

A stop **through the app** (the Stop button) isn't affected: it's a transition, so the exact stopped position is saved.

---

## 5. Tests (8 new, 73 in total)

- `test_robot_driver.py`: starts at `initial_position`; an initial position outside the limits is rejected.
- `test_machine.py`:
  - a snapshot taken mid-carry (gripper closed, cube held, cube at the robot) restored into a new machine with a driver at that position;
  - after a full sequence the snapshot has the cube on Table B and the gripper open.
- `test_api.py`:
  - after a jog, the saved position equals the target;
  - **with the real simulator driver**, a 50 mm move stopped after 0.2 s saves a position part-way (0 < x < 50), equal to where the robot stopped;
  - startup after a full sequence restores position, cube and gripper;
  - a saved position outside the limits falls back to the origin.

---

## 6. Real-server check

With the real server and simulator:
1. Started a sequence, and pressed Stop 3 s into `moveToDest` while carrying the cube. The status was `fault` at (−494.66, 567.84, 0), gripper closed, cube in the gripper.
2. **Killed** the server process (no graceful shutdown) and started it again.
3. Status after the restart: `ready`, at exactly (−494.66, 567.84, 0), gripper closed, cube in the gripper.

The stop was a transition, so its exact position was saved before the kill.
