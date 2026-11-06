// Serverless QC Inspection Ticket Submission Handler
// Rajarshi Shahu Trading Mandi ERP (Commercial Mandi ERP v1.0)
// Powered by Cresconic Technologies

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const projectRef = process.env.SUPABASE_PROJECT_REF || 'dbhcpebchoyjyffqjgih';
  const supabaseUrl = process.env.SUPABASE_URL || `https://${projectRef}.supabase.co`;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY || process.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRiaGNwZWJjaG95anlmZnFqZ2loIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MzIwODA1NywiZXhwIjoyMTA4Nzg0MDU3fQ.X3zOVSoIDOsp6ppSJ4SvgQFfQTVJnBmPeKclXnzRaS0';

  if (req.method === 'GET') {
    // Return pending inspections from Supabase
    try {
      const branchId = req.query.branch_id;
      let url = `${supabaseUrl}/rest/v1/quality_inspections?status=eq.PENDING&order=created_at.desc&limit=50`;
      if (branchId) {
        url += `&branch_id=eq.${encodeURIComponent(branchId)}`;
      }

      const resp = await fetch(url, {
        headers: {
          'apikey': serviceKey,
          'Authorization': `Bearer ${serviceKey}`
        }
      });
      const data = await resp.json();
      return res.status(200).json({ success: true, count: Array.isArray(data) ? data.length : 0, tickets: data });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  // DELETE or void unverified QC ticket
  if (req.method === 'DELETE' || (req.method === 'POST' && (req.body?.action === 'delete' || req.query?.action === 'delete'))) {
    try {
      let body = req.body || {};
      if (typeof body === 'string') {
        try { body = JSON.parse(body); } catch(e) {}
      }
      const ticketNo = body.ticket_no || req.query.ticket_no || body.id || req.query.id;
      if (!ticketNo) {
        return res.status(400).json({ success: false, error: 'Ticket number or ID is required.' });
      }

      // Check if attached to purchase_invoices
      const chkResp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices?qc_ticket_no=eq.${encodeURIComponent(ticketNo)}&select=id`, {
        headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}` }
      });
      if (chkResp.ok) {
        const rows = await chkResp.json();
        if (Array.isArray(rows) && rows.length > 0) {
          return res.status(400).json({ success: false, error: `Cannot delete QC Ticket #${ticketNo} because it has already been invoiced and settled.` });
        }
      }

      // Delete from quality_inspections
      const delResp = await fetch(`${supabaseUrl}/rest/v1/quality_inspections?ticket_no=eq.${encodeURIComponent(ticketNo)}`, {
        method: 'DELETE',
        headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}` }
      });

      if (!delResp.ok) {
        return res.status(delResp.status).json({ success: false, error: await delResp.text() });
      }

      return res.status(200).json({ success: true, message: `QC Ticket #${ticketNo} deleted permanently.` });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  if (req.method === 'POST') {
    try {
      let body = req.body;
      if (typeof body === 'string') {
        try { body = JSON.parse(body); } catch(e) {}
      }

      if (!body || typeof body !== 'object') {
        return res.status(400).json({ success: false, error: 'Invalid JSON request body.' });
      }

      // Generate ticket number if missing
      const now = new Date();
      const dateStr = now.toISOString().slice(2, 10).replace(/-/g, '');
      const yardCode = (body.yard_code || body.branch_id || 'CHK').toUpperCase().replace(/BR-/, '').slice(0, 3);
      const randHex = Math.random().toString(16).substring(2, 6).toUpperCase();
      const ticketNo = body.ticket_no || `QC-${yardCode}-${dateStr}-${randHex}`;

      // Map branch_id from yard code if needed
      let branchId = body.branch_id || 'br-chikhali';
      if (branchId === 'CHK' || branchId === 'chikhali') branchId = 'br-chikhali';
      if (branchId === 'VRV' || branchId === 'varvand') branchId = 'br-varvand';
      if (branchId === 'DHD' || branchId === 'dhad') branchId = 'br-dhad';

      const payload = {
        id: body.id || `qc-${ticketNo.toLowerCase().replace(/[^a-z0-9]/g, '-')}`,
        ticket_no: ticketNo,
        branch_id: branchId,
        inspector_id: body.inspector_id || null,
        inspector_name: body.inspector_name || 'Yard Inspector',
        vehicle_no: (body.vehicle_no || 'UNKNOWN').toUpperCase().trim(),
        farmer_name: (body.farmer_name || 'Walk-in Farmer').trim(),
        farmer_phone: body.farmer_phone || '',
        farmer_village: body.farmer_village || body.village || '',
        commodity_name: body.commodity_name || 'Soyabean (Yellow)',
        moisture_pct: parseFloat(body.moisture_pct) || 10.0,
        moisture_cut_kg: parseFloat(body.moisture_cut_kg) || 0.0,
        karda_pct: parseFloat(body.karda_pct) || 0.0,
        damaged_pct: parseFloat(body.damaged_pct) || 0.0,
        green_seeds_pct: parseFloat(body.green_seeds_pct) || 0.0,
        broken_split_pct: parseFloat(body.broken_split_pct) || 0.0,
        shriveled_pct: parseFloat(body.shriveled_pct) || 0.0,
        uniformity_index: parseFloat(body.uniformity_index) || 95.0,
        dominant_breed: body.dominant_breed || 'Standard',
        breed_purity_pct: parseFloat(body.breed_purity_pct) || 96.0,
        admixture_pct: parseFloat(body.admixture_pct) || 0.0,
        breed_status: body.breed_status || 'PURE_BREED',
        faq_grade: body.faq_grade || 'FAQ_GRADE_1',
        grade_label: body.grade_label || 'Grade 1 (Premium FAQ)',
        suggested_rate_cut_per_qtl: parseFloat(body.suggested_rate_cut_per_qtl) || 0.0,
        corridor_min_rate: parseFloat(body.corridor_min_rate) || 0.0,
        corridor_target_rate: parseFloat(body.corridor_target_rate) || 0.0,
        corridor_max_rate: parseFloat(body.corridor_max_rate) || 0.0,
        suggested_buying_rate_per_qtl: parseFloat(body.suggested_buying_rate_per_qtl) || 0.0,
        sample_weight_grams: parseFloat(body.sample_weight_grams) || 250.0,
        total_seeds_analyzed: parseInt(body.total_seeds_analyzed, 10) || 500,
        meter_photo_path: body.meter_photo_path || null,
        grain_photo_path: body.grain_photo_path || null,
        inspector_signature: body.inspector_signature || null,
        sortex_clean_yield_pct: parseFloat(body.sortex_clean_yield_pct) || 94.0,
        sortex_reject_pct: parseFloat(body.sortex_reject_pct) || 6.0,
        sortex_grade: body.sortex_grade || 'SORTEX Grade B (Commercial Trading Standard)',
        status: 'PENDING',
        inspection_notes: body.inspection_notes || 'Mobile App Assayed'
      };

      // Post to Supabase PostgREST
      const resp = await fetch(`${supabaseUrl}/rest/v1/quality_inspections`, {
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
        return res.status(resp.status).json({
          success: false,
          error: `Supabase insert failed: ${errText}`
        });
      }

      const inserted = await resp.json();
      return res.status(200).json({
        success: true,
        ticket_no: ticketNo,
        data: inserted,
        message: `QC Ticket #${ticketNo} created and synced to Supabase Cloud!`
      });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  return res.status(405).json({ success: false, error: 'Method Not Allowed' });
}
