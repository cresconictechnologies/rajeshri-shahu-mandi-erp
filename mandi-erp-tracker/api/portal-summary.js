// Serverless Multi-Branch Executive KPI & Telemetry Summary
// Rajarshi Shahu Trading Mandi ERP — Powered by Cresconic Technologies

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
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY || process.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRiaGNwZWJjaG95anlmZnFqZ2loIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MzIwODA1NywiZXhwIjoyMTA4Nzg0MDU3fQ.X3zOVSoIDOsp6ppSJ4SvgQFfQTVJnBmPeKclXnzRaS0';

  const headers = {
    'apikey': serviceKey,
    'Authorization': `Bearer ${serviceKey}`
  };

  try {
    const [invoicesResp, inspectionsResp, ratesResp] = await Promise.all([
      fetch(`${supabaseUrl}/rest/v1/purchase_invoices?select=id,branch_id,net_quintals,net_payable_amount,weighment_mode,payout_status,commodity_name,invoice_date&order=created_at.desc&limit=200`, { headers }),
      fetch(`${supabaseUrl}/rest/v1/quality_inspections?select=id,ticket_no,branch_id,status,moisture_pct,commodity_name,created_at&order=created_at.desc&limit=100`, { headers }),
      fetch(`${supabaseUrl}/rest/v1/daily_commodity_rates?select=commodity_name,target_rate_per_qtl,min_rate_per_qtl,max_rate_per_qtl,rate_date&order=updated_at.desc&limit=20`, { headers })
    ]);

    const invoices = invoicesResp.ok ? await invoicesResp.json() : [];
    const inspections = inspectionsResp.ok ? await inspectionsResp.json() : [];
    const rates = ratesResp.ok ? await ratesResp.json() : [];

    let totalQuintals = 0.0;
    let totalPayable = 0.0;
    let cashPaid = 0.0;
    let rtgsPending = 0.0;
    let rtgsPaid = 0.0;

    const branchTotals = {
      'br-chikhali': { name: 'Chikhali APMC Main Mandi', quintals: 0, amount: 0, invoices: 0 },
      'br-varvand': { name: 'Varvand APMC Yard', quintals: 0, amount: 0, invoices: 0 },
      'br-sarola': { name: 'Sarola Maruti APMC Yard', quintals: 0, amount: 0, invoices: 0 },
      'br-dhad': { name: 'Dhad APMC Yard', quintals: 0, amount: 0, invoices: 0 }
    };

    if (Array.isArray(invoices)) {
      for (const inv of invoices) {
        const qtl = parseFloat(inv.net_quintals) || 0.0;
        const amt = parseFloat(inv.net_payable_amount) || 0.0;
        totalQuintals += qtl;
        totalPayable += amt;

        if (inv.weighment_mode === 'CASH') {
          cashPaid += amt;
        } else {
          if (inv.payout_status === 'PAID') {
            rtgsPaid += amt;
          } else {
            rtgsPending += amt;
          }
        }

        const bId = inv.branch_id || 'br-chikhali';
        if (branchTotals[bId]) {
          branchTotals[bId].quintals += qtl;
          branchTotals[bId].amount += amt;
          branchTotals[bId].invoices += 1;
        }
      }
    }

    const pendingQC = Array.isArray(inspections) ? inspections.filter(i => i.status === 'PENDING').length : 0;

    return res.status(200).json({
      success: true,
      timestamp: new Date().toISOString(),
      summary: {
        total_invoices: Array.isArray(invoices) ? invoices.length : 0,
        total_quintals: parseFloat(totalQuintals.toFixed(2)),
        total_metric_tons: parseFloat((totalQuintals / 10.0).toFixed(2)),
        total_payable_amount: parseFloat(totalPayable.toFixed(2)),
        cash_disbursed: parseFloat(cashPaid.toFixed(2)),
        rtgs_pending_amount: parseFloat(rtgsPending.toFixed(2)),
        rtgs_paid_amount: parseFloat(rtgsPaid.toFixed(2)),
        total_inspections: Array.isArray(inspections) ? inspections.length : 0,
        pending_qc_count: pendingQC,
        branch_breakdown: branchTotals
      },
      recent_rates: Array.isArray(rates) ? rates.slice(0, 5) : []
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}
