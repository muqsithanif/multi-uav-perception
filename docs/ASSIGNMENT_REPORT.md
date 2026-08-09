# Gate 8 priority and assignment report

Priority is a YAML-configured scenario policy: class, zone, speed, heading
change, reacquisition, and confidence components form a bounded `[0, 1]`
score. It is not a universal risk score.

`assign_targets(uavs, targets, config)` provides Greedy and SciPy Hungarian
implementations with identical target/UAV inputs. Both enforce minimum
confidence/priority, lost targets, unavailable UAVs, forbidden pairs, one
target per UAV, and a configured switching penalty. The cost combines normalized
2D simulation distance, load, priority, confidence, waiting, and switching.

Run the recorded comparison with:

```bash
.venv/bin/python scripts/run_assignment_comparison.py \
  --output results/day5/A01_20260809_001/summary.json --repetitions 50
```

The measured overloaded scenario assigned the critical target in both methods.
Greedy total cost was `0.704795`; Hungarian total cost was `0.511247`. Mean
compute time was `0.016221 ms` for Greedy and `0.018583 ms` for Hungarian.
These are 50 in-process repetitions on the stated local environment, not a
real-time, network, or physical-UAV performance claim. See the full
[machine-readable artifact](../results/day5/A01_20260809_001/summary.json).

Mission-state transitions, 2D dynamics, reassignment over time, and ROS use of
these algorithms remain Gate 9 work.
