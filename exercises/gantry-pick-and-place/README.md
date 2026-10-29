# **Robot Pick & Place Simulation**

A FastAPI backend (`vention-communication`, `vention-state-machine`, `vention-storage`) that drives the provided `robot_sim.Robot`, and a React + TypeScript dashboard to configure and run the pick-and-place sequence.

**Demo video:** [docs/Demo.mp4](docs/Demo.mp4). GitHub may not play a file this size in the browser; use "View raw" to download it.

---

## Run with Docker

From this folder, with Docker running:

```bash
docker compose up --build
```

Open **http://localhost:8080**. Stop with Ctrl+C. The configuration and robot state are kept in a Docker volume; `docker compose down -v` resets them.

---

## Run without Docker

Requires **Python 3.10** (the `vention-*` libraries don't install on 3.11+) and **Node.js 18+**.

### Backend

From `backend/`:

```bash
# Windows
py -3.10 -m venv venv
venv\Scripts\activate

# macOS / Linux
python3.10 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

### Frontend

From `frontend/`, with the backend running:

```bash
npm install
npm run dev
```

Open **http://localhost:5173**.

### Tests

From `backend/`, with the venv active:

```bash
python -m pytest
```

---

<a id="exercise-statement"></a>

## **Problem Statement**

You are tasked with building a proof-of-concept for a 3-axis gantry robot solution. The goal is to implement a Python backend that controls a robotic arm using a State Machine and a React frontend to visualize and configure the operation.

You must simulate a "Pick and Place" sequence: picking a cube from **Table A** and placing it on **Table B** within the provided application footprint.

![image](https://github.com/VentionCoExperiments/MachineApps-take-home-public/raw/main/exercises/gantry-pick-and-place/figure1_application_footprint.png)

## **Checklist of Requirements**

### **Mandatory Requirements**

**Backend (Python & FastAPI)**

  - [x] **Communication Framework:** Use the [`vention-communication`](https://pypi.org/project/vention-communication/) library to establish communication between the frontend and backend.
  - [x] **State Machine Integration:** Implement the robot's control logic using the [`vention-state-machine`](https://pypi.org/project/vention-state-machine/) library.
  - [x] **Robot Simulation:** Interface with the provided `robot_sim.py` class.
      - *Note:* The `move_to` method must be called repeatedly until motion is complete. This should be handled inside your state machine callbacks.
  - [x] **API Endpoints:** Create endpoints to:
      - Get/Set robot, cube, and destination positions.
      - specific commands: `Home Robot`, `Start Sequence`, `Get Status`.
      - *Note:* The "Home" operation moves the robot to its home position (default: `[0, 0, 0]`). Review `robot_sim.py` to understand the `move_home()` method and the `home_position` parameter.
  - [x] **Logic:** Implement the full Pick-and-Place sequence:
    1.  Move to Cube (Table A) $\rightarrow$ Lower $\rightarrow$ Close Gripper.
    2.  Lift $\rightarrow$ Move to Destination (Table B).
    3.  Lower $\rightarrow$ Open Gripper $\rightarrow$ Lift.

**Frontend (React & TypeScript)**

  - [x] **Dashboard:** Display real-time telemetry:
      - Current Robot Position (X, Y, Z).
      - Cube Start Position & Destination.
      - Robot Status (Gripper open/closed, moving/idle).
      - Current State of the State Machine.
  - [x] **Controls:** Allow the user to:
      - Configure the Cube's start coordinates and destination coordinates.
      - Trigger the "Home" operation (moves robot to home position, default: `[0, 0, 0]`).
      - Start the "Pick and Place" sequence.
  - [x] **Visuals:** Provide a clear visual indication of errors and operational state.

### **Bonus Points**

  - [x] **Persistence:** Use [`vention-storage`](https://pypi.org/project/vention-storage/) to save configuration (e.g., cube locations) between restarts.
  - [x] **Testing:** Write unit tests for the backend logic or component tests for the frontend.
  - [x] **Containerization:** Run the whole stack (Backend + Frontend) with a single command (e.g., Docker Compose).
  - [x] **Demo:** Include a short video recording of your solution in action. See [docs/Demo.mp4](docs/Demo.mp4).

## **Technical Resources**

**Backend Setup**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Requirements include: fastapi, vention-communication==0.3.0, vention-state-machine==0.3.1, vention-storage==0.5.4
```

**Frontend Setup**

```bash
cd frontend
npm install
npm run dev
```

## **Submission**

  - [x] Fork the repository and complete the work in your fork.
  - [x] Include a **README** documenting:
      - Setup and run instructions.
      - Design decisions, assumptions, and trade-offs.
  - [x] Push your changes and share the repository link.

-----

### **Questions?**

If you have any questions about the exercise, please contact [isaac.mills@vention.cc](mailto:isaac.mills@vention.cc). Happy coding\!
