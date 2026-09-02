// Range SPA bundle. Both values below are FAKE canary strings planted for the
// secret/path detectors - they authenticate nothing and route nowhere real.
const CONFIG = {
  apiKey: "sk-range-FAKECANARY-000000000000000000",
  adminMetrics: "/internal/admin/metrics",
};
console.log("range app booted", CONFIG.adminMetrics);
