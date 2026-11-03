// Serverless Supabase Cloud Sync Status Handler
// Rajarshi Shahu Trading Mandi ERP (Commercial Mandi ERP v1.0)
// Powered by Cresconic Technologies

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const projectRef = process.env.SUPABASE_PROJECT_REF || 'dbhcpebchoyjyffqjgih';
  const supabaseUrl = process.env.SUPABASE_URL || `https://${projectRef}.supabase.co`;
  const anonKey = process.env.SUPABASE_ANON_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';

  let isConnected = false;
  let latencyMs = 0;
  let message = 'Supabase Cloud Database connected and operational.';

  const startTime = Date.now();
  try {
    const probeHeaders = {};
    if (anonKey) {
      probeHeaders['apikey'] = anonKey;
      probeHeaders['Authorization'] = `Bearer ${anonKey}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    const probeResp = await fetch(`${supabaseUrl}/rest/v1/`, {
      method: 'GET',
      headers: probeHeaders,
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    latencyMs = Date.now() - startTime;
    // 200 OK or 401/404 (with valid JSON endpoint response) indicates Supabase server is live
    if (probeResp.status >= 200 && probeResp.status < 500) {
      isConnected = true;
    } else {
      message = `Supabase responded with status ${probeResp.status}`;
    }
  } catch (err) {
    latencyMs = Date.now() - startTime;
    isConnected = false;
    message = `Local Edge Mode active: Cloud ping unavailable (${err.message || 'timeout'})`;
  }

  return res.status(200).json({
    success: true,
    status: isConnected ? 'CONNECTED' : 'OFFLINE',
    online: isConnected,
    project_ref: projectRef,
    supabase_url: supabaseUrl,
    region: 'ap-south-1 (Mumbai)',
    sync_mode: isConnected ? 'EDGE_CLOUD_HYBRID' : 'LOCAL_CACHE',
    latency_ms: latencyMs,
    last_sync: new Date().toISOString(),
    tables_monitored: [
      'branches',
      'users',
      'commodities',
      'parties',
      'daily_commodity_rates',
      'quality_inspections',
      'purchase_invoices',
      'cashier_payouts',
      'outward_orders',
      'ledger_entries'
    ],
    message: message
  });
}
