// Serverless Analytics & License Tracking Handler
// Rajarshi Shahu Trading - Powered by Cresconic

// In-memory runtime telemetry state for serverless instance (persists across warm invocations)
let inMemoryStats = {
  downloads: 0,
  appDownloads: 0,
  visitors: 0,
  activeLicenses: 0,
  recentEvents: [],
  licenseRequests: []
};

let liveTelemetry = {
  totalQuintals: 0,
  totalDisbursed: 0,
  activeBranches: 0,
  totalInspections: 0,
  lastSyncedAt: null,
  recentEvent: null
};

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  const clientCountry = req.headers["x-vercel-ip-country"] || "IN";
  const clientCity = req.headers["x-vercel-ip-city"] || "Localhost";
  const userAgent = req.headers["user-agent"] || "Unknown";

  if (req.method === "GET") {
    return res.status(200).json({
      success: true,
      brand: "Rajarshi Shahu Trading - Powered by Cresconic",
      stats: inMemoryStats,
      liveTelemetry: liveTelemetry,
      counts: {
        download: inMemoryStats.downloads,
        download_app: inMemoryStats.appDownloads,
        active_branches: liveTelemetry.activeBranches || inMemoryStats.activeLicenses,
        total_quintals: liveTelemetry.totalQuintals,
        total_disbursed: liveTelemetry.totalDisbursed,
        total_inspections: liveTelemetry.totalInspections
      },
      clientMeta: {
        country: clientCountry,
        city: clientCity,
        ip: req.headers["x-forwarded-for"] || "127.0.0.1"
      },
      release: {
        version: "v1.0",
        releasedAt: "2026-11-02",
        releaseTag: "v1.0",
        downloadUrl: "https://github.com/cresconictechnologies/rajarshi-shahu-mandi-erp/releases/download/v1.0/Rajarshi_Shahu_Trading_Windows_x64.zip",
        githubRepo: "https://github.com/cresconictechnologies/rajarshi-shahu-mandi-erp",
        cessStatus: "0% (Zero Mandi Cess)",
        licenseEngine: "Ed25519 Cryptographic Verification"
      }
    });
  }

  if (req.method === "POST") {
    try {
      const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
      const action = body.action || body.event_type || "pageview";

      if (action === "sync_telemetry") {
        const tel = body.telemetry || body;
        if (tel.totalQuintals !== undefined) liveTelemetry.totalQuintals = Number(tel.totalQuintals) || 0;
        if (tel.totalDisbursed !== undefined) liveTelemetry.totalDisbursed = Number(tel.totalDisbursed) || 0;
        if (tel.activeBranches !== undefined) {
          liveTelemetry.activeBranches = Number(tel.activeBranches) || 0;
          inMemoryStats.activeLicenses = liveTelemetry.activeBranches;
        }
        if (tel.totalInspections !== undefined) liveTelemetry.totalInspections = Number(tel.totalInspections) || 0;
        liveTelemetry.lastSyncedAt = new Date().toISOString();

        if (tel.recentEvent) {
          liveTelemetry.recentEvent = tel.recentEvent;
          inMemoryStats.recentEvents.unshift({
            type: tel.recentEvent.type || "sync_telemetry",
            target: tel.recentEvent.summary || "APMC Yard Telemetry Sync",
            location: `${clientCity}, ${clientCountry}`,
            timestamp: tel.recentEvent.timestamp || new Date().toISOString()
          });
          if (inMemoryStats.recentEvents.length > 25) {
            inMemoryStats.recentEvents.pop();
          }
        }

        return res.status(200).json({
          success: true,
          message: "Live telemetry synced successfully",
          brand: "Rajarshi Shahu Trading - Powered by Cresconic",
          liveTelemetry
        });
      }

      if (action === "download") {
        inMemoryStats.downloads += 1;
        inMemoryStats.recentEvents.unshift({
          type: "download",
          version: body.version || "v1.0",
          os: "Windows 64-bit",
          location: `${clientCity}, ${clientCountry}`,
          timestamp: new Date().toISOString()
        });
        if (inMemoryStats.recentEvents.length > 25) {
          inMemoryStats.recentEvents.pop();
        }
        return res.status(200).json({
          success: true,
          message: "Windows download tracked",
          totalDownloads: inMemoryStats.downloads
        });
      }

      if (action === "download_app") {
        inMemoryStats.appDownloads = (inMemoryStats.appDownloads || 0) + 1;
        inMemoryStats.recentEvents.unshift({
          type: "download_app",
          target: "Mandi QC Inspector Android App",
          os: "Android PWA / WebAPK",
          location: `${clientCity}, ${clientCountry}`,
          timestamp: new Date().toISOString()
        });
        if (inMemoryStats.recentEvents.length > 25) {
          inMemoryStats.recentEvents.pop();
        }
        return res.status(200).json({
          success: true,
          message: "Android App install tracked",
          totalAppDownloads: inMemoryStats.appDownloads
        });
      }

      if (action === "license_request") {
        const newReq = {
          company: body.company || "Anonymous Trader",
          applicant: body.applicant || "Trader Owner",
          phone: body.phone || "Not provided",
          yards: body.yards || 1,
          status: "Pending Review",
          timestamp: new Date().toISOString()
        };
        inMemoryStats.licenseRequests.unshift(newReq);
        inMemoryStats.recentEvents.unshift({
          type: "license_request",
          company: newReq.company,
          branches: `${newReq.yards} Yard(s)`,
          location: `${clientCity}, ${clientCountry}`,
          timestamp: new Date().toISOString()
        });
        if (inMemoryStats.recentEvents.length > 25) {
          inMemoryStats.recentEvents.pop();
        }
        return res.status(200).json({
          success: true,
          message: "License request logged",
          totalLicenses: inMemoryStats.activeLicenses
        });
      }

      if (action === "pageview") {
        inMemoryStats.visitors += 1;
        return res.status(200).json({ success: true, visitors: inMemoryStats.visitors });
      }

      return res.status(200).json({ success: true });
    } catch (err) {
      return res.status(400).json({ success: false, error: err.message });
    }
  }

  return res.status(405).json({ error: "Method not allowed" });
}
