export default {
  group: "P4",
  componentType: "slider",
  units: 1,
  limits: { min: 10, max: 90 },
  statusFlags: [{ bit: 3, label: "pump" }],
  use: {
    v: { pool: "P4", chan: "v", idx: 1 },
    u: { pool: "P4", chan: "u", idx: 1 },
    s: [{ pool: "P5", chan: "s", idx: 40 }],
    n: { pool: "P4", chan: "n", idx: 1 },
    x: { pool: "P4", chan: "x", idx: 1 }
  }
};
