export default function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(200).json({
    success: true,
    app_name: "Rajarshi Shahu Trading — Mandi ERP",
    branding: "Powered by Cresconic Technologies",
    version: "v1.0",
    build_date: "2026-11-02",
    build_timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19) + " UTC",
    master_host: "192.168.0.140:8080",
    cloud_pwa_url: "https://mandi-erp-tracker.vercel.app/app",
    status: "OPERATIONAL",
    engine_version: "Multi-Spectral Norm-Chroma Assayer v3.0",
    update_available: false,
    latest_patch: "Instant Rate Corridor Sync & Terminal OTA Updates"
  });
}
