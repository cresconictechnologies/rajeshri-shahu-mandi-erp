export default function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(200).json({
    success: true,
    app_name: "Rajarshi Shahu Trading — Mandi ERP",
    branding: "Powered by Cresconic Technologies",
    version: "v2.5",
    build_date: "2026-11-04",
    build_timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19) + " UTC",
    master_host: "mandi-erp-tracker.vercel.app",
    cloud_pwa_url: "https://mandi-erp-tracker.vercel.app/app",
    status: "OPERATIONAL",
    engine_version: "Multi-Spectral Norm-Chroma Assayer v3.0 (Win7-Ready)",
    update_available: true,
    download_url: "https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp/releases/download/v1.0/Rajarshi_Shahu_Trading_Windows_x64.zip",
    updater_script_url: "https://mandi-erp-tracker.vercel.app/Update_Software.bat",
    latest_patch: "Windows 7 KERNEL32 PackageIdFromFullName fix, 60s Fast-Socket probe, Instant Supabase Cloud Rate Corridor Sync, 3 Official Branches (Chikhali, Varvand, Sarola Maruti)"
  });
}
