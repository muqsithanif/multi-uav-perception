# Gate 9 simulation evidence (in progress)

The simulator uses abstract 2D units only. It has no calibration or physical
UAV interpretation. Six deterministic scenarios are configured: fewer/equal/
more targets, critical arrival, unavailable UAV, and lost/reacquired target.

The first Hungarian run saved [summary metrics](../results/day6/SIM01_20260809_001/summary.json),
[six-state image](../results/day6/SIM01_20260809_001/scenario_final_states.png),
and a 5-second `critical_arrival.mp4` preview (ignored from Git as large media).
The preview is an implementation artifact, not the final 2–4 minute demo.

Gate 9 remains open until the simulator consumes the project ROS assignment and
mission stream end-to-end, records those messages, and provides the required
integration evidence.
