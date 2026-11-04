// Serverless API for Mandi Daily Rates (Supabase Cloud)
// Rajarshi Shahu Trading Mandi ERP — Powered by Cresconic Technologies

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const projectRef = process.env.SUPABASE_PROJECT_REF || 'dbhcpebchoyjyffqjgih';
  const supabaseUrl = process.env.SUPABASE_URL || `https://${projectRef}.supabase.co`;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY || process.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRiaGNwZWJjaG95anlmZnFqZ2loIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MzIwODA1NywiZXhwIjoyMTA4Nzg0MDU3fQ.X3zOVSoIDOsp6ppSJ4SvgQFfQTVJnBmPeKclXnzRaS0';

  const defaultRates = [
    { commodity_name: 'Soyabean (Yellow)', min_rate_per_qtl: 6500.0, target_rate_per_qtl: 6850.0, max_rate_per_qtl: 7500.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) },
    { commodity_name: 'Chana (Desi)', min_rate_per_qtl: 5600.0, target_rate_per_qtl: 5900.0, max_rate_per_qtl: 6400.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) },
    { commodity_name: 'Toor (White)', min_rate_per_qtl: 7800.0, target_rate_per_qtl: 8200.0, max_rate_per_qtl: 8800.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) },
    { commodity_name: 'Wheat (Sharbati)', min_rate_per_qtl: 2750.0, target_rate_per_qtl: 2950.0, max_rate_per_qtl: 3300.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) },
    { commodity_name: 'Maize (Yellow)', min_rate_per_qtl: 2100.0, target_rate_per_qtl: 2300.0, max_rate_per_qtl: 2550.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) }
  ];

  if (req.method === 'GET') {
    try {
      const branchId = req.query.branch_id;
      let url = `${supabaseUrl}/rest/v1/daily_commodity_rates?select=*&order=updated_at.desc&limit=100`;

      const resp = await fetch(url, {
        headers: {
          'apikey': serviceKey,
          'Authorization': `Bearer ${serviceKey}`
        }
      });

      if (!resp.ok) {
        return res.status(200).json({ success: true, rates: defaultRates, is_fallback: true });
      }

      const rows = await resp.json();
      if (!Array.isArray(rows) || rows.length === 0) {
        return res.status(200).json({ success: true, rates: defaultRates, is_fallback: true });
      }

      // Deduplicate by commodity_name (keeping newest updated_at)
      const ratesMap = {};
      for (const r of rows) {
        const comm = r.commodity_name;
        if (!ratesMap[comm]) {
          ratesMap[comm] = r;
        }
      }

      return res.status(200).json({
        success: true,
        rates: Object.values(ratesMap),
        count: Object.keys(ratesMap).length
      });
    } catch (err) {
      return res.status(200).json({ success: true, rates: defaultRates, error: err.message, is_fallback: true });
    }
  }

  if (req.method === 'POST') {
    try {
      let body = req.body;
      if (typeof body === 'string') {
        try { body = JSON.parse(body); } catch (_) {}
      }

      if (!body || !body.commodity_name) {
        return res.status(400).json({ success: false, error: 'commodity_name is required' });
      }

      const todayStr = new Date().toISOString().slice(0, 10);
      const rateDate = body.rate_date || todayStr;
      const minRate = parseFloat(body.min_rate_per_qtl) || 0.0;
      const targetRate = parseFloat(body.target_rate_per_qtl) || minRate;
      const maxRate = parseFloat(body.max_rate_per_qtl) || targetRate;
      const grade = body.quality_grade || 'FAQ_GRADE_1';
      const branchId = body.branch_id || null;

      const recordId = `rate-${rateDate}-${body.commodity_name.toLowerCase().replace(/[^a-z0-9]/g, '-')}-${branchId || 'global'}`;

      const payload = {
        id: recordId,
        rate_date: rateDate,
        commodity_name: body.commodity_name,
        branch_id: branchId,
        min_rate_per_qtl: minRate,
        target_rate_per_qtl: targetRate,
        max_rate_per_qtl: maxRate,
        quality_grade: grade,
        updated_at: new Date().toISOString()
      };

      const resp = await fetch(`${supabaseUrl}/rest/v1/daily_commodity_rates`, {
        method: 'POST',
        headers: {
          'apikey': serviceKey,
          'Authorization': `Bearer ${serviceKey}`,
          'Content-Type': 'application/json',
          'Prefer': 'resolution=merge-duplicates,return=representation'
        },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) {
        const errText = await resp.text();
        return res.status(resp.status).json({ success: false, error: errText });
      }

      const inserted = await resp.json();
      return res.status(200).json({
        success: true,
        message: `Successfully published rate for ${body.commodity_name} (₹${targetRate}/Qtl) to Supabase Cloud!`,
        data: inserted
      });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  return res.status(405).json({ success: false, error: 'Method Not Allowed' });
}
