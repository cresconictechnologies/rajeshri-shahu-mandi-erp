// Serverless Invoices & Weighment API for Web ERP Portal (Supabase Cloud)
// Rajarshi Shahu Trading Mandi ERP — Powered by Cresconic Technologies

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const projectRef = process.env.SUPABASE_PROJECT_REF || 'dbhcpebchoyjyffqjgih';
  const supabaseUrl = process.env.SUPABASE_URL || `https://${projectRef}.supabase.co`;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY || process.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRiaGNwZWJjaG95anlmZnFqZ2loIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MzIwODA1NywiZXhwIjoyMTA4Nzg0MDU3fQ.X3zOVSoIDOsp6ppSJ4SvgQFfQTVJnBmPeKclXnzRaS0';

  // GET: Fetch recent invoices (branch-specific or cross-branch)
  if (req.method === 'GET') {
    try {
      const branchId = req.query.branch_id;
      const status = req.query.status;
      const limit = parseInt(req.query.limit, 10) || 50;

      let queryParams = `select=*&order=created_at.desc&limit=${limit}`;
      if (branchId && branchId !== 'all') {
        queryParams += `&branch_id=eq.${encodeURIComponent(branchId)}`;
      }
      if (status) {
        queryParams += `&payout_status=eq.${encodeURIComponent(status)}`;
      }

      const resp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices?${queryParams}`, {
        headers: {
          'apikey': serviceKey,
          'Authorization': `Bearer ${serviceKey}`
        }
      });

      if (!resp.ok) {
        return res.status(200).json({ success: true, count: 0, invoices: [] });
      }

      const invoices = await resp.json();
      return res.status(200).json({
        success: true,
        count: Array.isArray(invoices) ? invoices.length : 0,
        invoices: Array.isArray(invoices) ? invoices : []
      });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  // POST: Create Inward Weighment Purchase Invoice
  if (req.method === 'POST') {
    try {
      let body = req.body;
      if (typeof body === 'string') {
        try { body = JSON.parse(body); } catch (_) {}
      }

      if (!body) {
        return res.status(400).json({ success: false, error: 'Request body required' });
      }

      const branchId = body.branch_id || 'br-chikhali';
      const now = new Date();
      const dateStr = now.toISOString().slice(2, 10).replace(/-/g, '');
      const yardCode = (body.yard_code || branchId.replace('br-', '')).toUpperCase().slice(0, 3);
      const randHex = Math.random().toString(16).substring(2, 6).toUpperCase();
      const tokenNumber = body.token_number || `INV-${yardCode}-${dateStr}-${randHex}`;
      const invoiceId = `inv-${tokenNumber.toLowerCase().replace(/[^a-z0-9]/g, '-')}`;

      const grossWeight = parseFloat(body.gross_weight_kg) || 0.0;
      const tareWeight = parseFloat(body.tare_weight_kg) || 0.0;
      const netWeightKg = Math.max(0.0, grossWeight - tareWeight);
      const grossQuintals = parseFloat((netWeightKg / 100.0).toFixed(2));
      
      const moistureCutKg = parseFloat(body.moisture_cut_kg) || 0.0;
      const kardaDeductionKg = parseFloat(body.karda_deduction_kg) || 0.0;
      const totalDeductionKg = moistureCutKg + kardaDeductionKg;
      const netQuintals = Math.max(0.0, parseFloat(((netWeightKg - totalDeductionKg) / 100.0).toFixed(2)));

      const ratePerQtl = parseFloat(body.rate_per_quintal) || 0.0;
      const grossAmount = parseFloat((netQuintals * ratePerQtl).toFixed(2));

      // Statutory deductions
      const hamaliRate = 12.0; // ₹12/qtl
      const tolaiRate = 5.0;   // ₹5/qtl
      const hamaliAmount = parseFloat((netQuintals * hamaliRate).toFixed(2));
      const tolaiAmount = parseFloat((netQuintals * tolaiRate).toFixed(2));
      const mandiCess = 0.0; // 100% Zero Mandi Cess Invariant
      const totalDeductions = hamaliAmount + tolaiAmount;
      const netPayable = Math.max(0.0, parseFloat((grossAmount - totalDeductions).toFixed(2)));

      // Section 269ST Income Tax Compliance check: Cash payment strictly capped at ₹1,99,999
      let weighmentMode = (body.weighment_mode || 'CASH').toUpperCase();
      let payoutStatus = 'PAID';
      if (weighmentMode === 'RTGS' || netPayable >= 200000.0) {
        weighmentMode = 'RTGS';
        payoutStatus = 'RTGS_PENDING';
      }

      const invoicePayload = {
        id: invoiceId,
        token_number: tokenNumber,
        branch_id: branchId,
        invoice_date: body.invoice_date || now.toISOString().slice(0, 10),
        party_name: (body.farmer_name || 'Walk-in Farmer').trim(),
        farmer_phone: body.farmer_phone || '',
        farmer_village: body.farmer_village || body.village || '',
        commodity_name: body.commodity_name || 'Soyabean (Yellow)',
        vehicle_number: (body.vehicle_number || body.vehicle_no || 'MH28-DIRECT').toUpperCase().trim(),
        gross_weight_kg: grossWeight,
        tare_weight_kg: tareWeight,
        net_weight_kg: netWeightKg,
        net_quintals: netQuintals,
        rate_per_quintal: ratePerQtl,
        gross_amount: grossAmount,
        mandi_cess_amount: mandiCess,
        hamali_amount: hamaliAmount,
        tolai_amount: tolaiAmount,
        net_payable_amount: netPayable,
        weighment_mode: weighmentMode,
        payout_status: payoutStatus,
        qc_ticket_no: body.qc_ticket_no || null,
        rtgs_bank_name: body.rtgs_bank_name || null,
        rtgs_account_no: body.rtgs_account_no || null,
        rtgs_ifsc_code: body.rtgs_ifsc_code || null,
        rtgs_utr_no: body.rtgs_utr_no || null,
        updated_at: now.toISOString()
      };

      const resp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices`, {
        method: 'POST',
        headers: {
          'apikey': serviceKey,
          'Authorization': `Bearer ${serviceKey}`,
          'Content-Type': 'application/json',
          'Prefer': 'resolution=merge-duplicates,return=representation'
        },
        body: JSON.stringify(invoicePayload)
      });

      if (!resp.ok) {
        const errText = await resp.text();
        return res.status(resp.status).json({ success: false, error: errText });
      }

      const inserted = await resp.json();

      // If QC ticket was linked, mark it COMPLETED in Supabase
      if (body.qc_ticket_no) {
        try {
          await fetch(`${supabaseUrl}/rest/v1/quality_inspections?ticket_no=eq.${encodeURIComponent(body.qc_ticket_no)}`, {
            method: 'PATCH',
            headers: {
              'apikey': serviceKey,
              'Authorization': `Bearer ${serviceKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              status: 'COMPLETED',
              invoice_id: invoiceId,
              updated_at: now.toISOString()
            })
          });
        } catch (_) {}
      }

      return res.status(200).json({
        success: true,
        message: `Invoice #${tokenNumber} generated and synced to Supabase Cloud!`,
        token_number: tokenNumber,
        net_payable_amount: netPayable,
        weighment_mode: weighmentMode,
        payout_status: payoutStatus,
        data: inserted
      });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  // PATCH: Update RTGS UTR or Payout Status
  if (req.method === 'PATCH') {
    try {
      const { id, token_number, rtgs_utr_no, payout_status } = req.body;
      if (!id && !token_number) {
        return res.status(400).json({ success: false, error: 'id or token_number is required' });
      }

      const filterCol = id ? `id=eq.${encodeURIComponent(id)}` : `token_number=eq.${encodeURIComponent(token_number)}`;
      const updateData = {
        updated_at: new Date().toISOString()
      };
      if (rtgs_utr_no) updateData.rtgs_utr_no = rtgs_utr_no;
      if (payout_status) updateData.payout_status = payout_status;

      const resp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices?${filterCol}`, {
        method: 'PATCH',
        headers: {
          'apikey': serviceKey,
          'Authorization': `Bearer ${serviceKey}`,
          'Content-Type': 'application/json',
          'Prefer': 'return=representation'
        },
        body: JSON.stringify(updateData)
      });

      if (!resp.ok) {
        const errText = await resp.text();
        return res.status(resp.status).json({ success: false, error: errText });
      }

      const updated = await resp.json();
      return res.status(200).json({
        success: true,
        message: `RTGS payment updated successfully!`,
        data: updated
      });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  return res.status(405).json({ success: false, error: 'Method Not Allowed' });
}
