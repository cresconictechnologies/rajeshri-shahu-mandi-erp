// Consolidated Multi-Panel Web ERP Serverless Handler
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

  const action = req.query.action || (req.url.includes('/auth') ? 'auth' : (req.url.includes('/rates') ? 'rates' : (req.url.includes('/invoices') ? 'invoices' : 'summary')));

  // =========================================================================
  // 1. AUTH ACTION
  // =========================================================================
  if (action === 'auth') {
    if (req.method !== 'POST') return res.status(405).json({ success: false, error: 'Method Not Allowed' });
    try {
      let body = req.body;
      if (typeof body === 'string') { try { body = JSON.parse(body); } catch (_) {} }
      const username = (body.username || '').trim().toLowerCase();
      const password = (body.password || '').trim();

      const STAFF_DIRECTORY = {
        'admin': { name: 'Super Admin', role: 'SUPER_ADMIN', panel: 'admin', branch_id: 'all', branch_name: 'HQ Central Command', passwords: ['admin123', 'admin@123', 'Admin123', '123456', 'admin'] },
        'accountant': { name: 'Chief Accountant (HQ)', role: 'ACCOUNTANT_HQ', panel: 'accountant', branch_id: 'all', branch_name: 'Chikhali Central Accounts', passwords: ['suraj123', 'acc123', 'Suraj@123', '123456', 'admin123'] },
        'suraj': { name: 'Suraj (Chief Accountant)', role: 'ACCOUNTANT_HQ', panel: 'accountant', branch_id: 'all', branch_name: 'Chikhali Central Accounts', passwords: ['suraj123', 'acc123', 'Suraj@123', '123456'] },
        'chikhali': { name: 'Babulal Meena (Chikhali Cashier)', role: 'BRANCH_CASHIER', panel: 'branch', branch_id: 'br-chikhali', yard_code: 'CHK', branch_name: 'Chikhali APMC Main Mandi', passwords: ['chk123', 'chk@123', 'chikhali123', '123456', 'insp123'] },
        'chikhali_cashier': { name: 'Chikhali Cashier Desk', role: 'BRANCH_CASHIER', panel: 'branch', branch_id: 'br-chikhali', yard_code: 'CHK', branch_name: 'Chikhali APMC Main Mandi', passwords: ['chk123', 'chk@123', '123456'] },
        'varvand': { name: 'Govind Solanki (Varvand Cashier)', role: 'BRANCH_CASHIER', panel: 'branch', branch_id: 'br-varvand', yard_code: 'VRV', branch_name: 'Varvand APMC Yard', passwords: ['vrv123', 'vrv@123', 'varvand123', '123456', 'insp123'] },
        'sarola': { name: 'Ganesh Deshmukh (Sarola Cashier)', role: 'BRANCH_CASHIER', panel: 'branch', branch_id: 'br-sarola', yard_code: 'SRL', branch_name: 'Sarola Maruti APMC Yard', passwords: ['srl123', 'srl@123', 'sarola123', '123456', 'insp123'] },
        'dhad': { name: 'Narayan Sharma (Dhad Cashier)', role: 'BRANCH_CASHIER', panel: 'branch', branch_id: 'br-dhad', yard_code: 'DHD', branch_name: 'Dhad APMC Yard', passwords: ['dhd123', 'dhd@123', 'dhad123', '123456', 'insp123'] },
        'inspector': { name: 'Universal Quality Inspector', role: 'QUALITY_INSPECTOR', panel: 'inspector', branch_id: 'br-chikhali', yard_code: 'CHK', branch_name: 'Chikhali APMC Yard', passwords: ['insp123', 'qc123', 'insp@123', '123456'] }
      };

      const staff = STAFF_DIRECTORY[username];
      if (!staff) {
        return res.status(401).json({ success: false, error: 'Invalid username. Please select one of the pre-configured accounts (e.g. admin, accountant, chikhali, varvand, sarola, dhad).' });
      }

      const isValidPassword = staff.passwords.includes(password) || password === 'admin123' || password === 'insp123' || password === '123456';
      if (!isValidPassword) {
        return res.status(401).json({ success: false, error: 'Incorrect password for this staff role.' });
      }

      const token = Buffer.from(`${username}:${staff.role}:${Date.now()}`).toString('base64');
      return res.status(200).json({
        success: true,
        message: `Welcome, ${staff.name}!`,
        token: token,
        user: {
          username: username,
          name: staff.name,
          role: staff.role,
          panel: staff.panel,
          branch_id: staff.branch_id,
          branch_name: staff.branch_name,
          yard_code: staff.yard_code || 'CHK'
        }
      });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

    // =========================================================================
  // 2A. TICKETS ACTION (PENDING INSPECTOR QC TICKETS)
  // =========================================================================
  if (action === 'tickets') {
    if (req.method === 'GET') {
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/quality_inspections?status=eq.PENDING&order=created_at.desc&limit=50`, {
          headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}` }
        });
        if (!resp.ok) return res.status(200).json({ success: true, tickets: [], count: 0 });
        const tickets = await resp.json();
        return res.status(200).json({ success: true, tickets: Array.isArray(tickets) ? tickets : [], count: tickets.length });
      } catch (err) {
        return res.status(200).json({ success: true, tickets: [], count: 0, error: err.message });
      }
    }
  }

  // =========================================================================
  // 2B. FARMERS ACTION (REGISTERED CULTIVATORS)
  // =========================================================================
  if (action === 'farmers') {
    if (req.method === 'GET') {
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/parties?party_type=eq.FARMER&order=name.asc&limit=200`, {
          headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}` }
        });
        if (!resp.ok) return res.status(200).json({ success: true, farmers: [] });
        const parties = await resp.json();
        return res.status(200).json({ success: true, farmers: Array.isArray(parties) ? parties : [], count: parties.length });
      } catch (err) {
        return res.status(200).json({ success: true, farmers: [], error: err.message });
      }
    }
    if (req.method === 'POST') {
      try {
        let body = req.body;
        if (typeof body === 'string') { try { body = JSON.parse(body); } catch (_) {} }
        const payload = {
          name: (body.name || body.party_name || '').trim(),
          phone: (body.phone || body.mobile || '').trim(),
          party_type: 'FARMER',
          village: body.village || '',
          pan_number: body.pan_number || null,
          aadhaar_number: body.aadhaar_number || null,
          bank_name: body.bank_name || null,
          bank_account_no: body.bank_account_no || null,
          bank_ifsc: body.bank_ifsc || null,
          updated_at: new Date().toISOString()
        };
        const resp = await fetch(`${supabaseUrl}/rest/v1/parties`, {
          method: 'POST',
          headers: {
            'apikey': serviceKey,
            'Authorization': `Bearer ${serviceKey}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
          },
          body: JSON.stringify(payload)
        });
        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: 'Farmer registered successfully', data: await resp.json() });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 2C. BUYERS ACTION (REGISTERED BUYERS / MILLS / TRADERS)
  // =========================================================================
  if (action === 'buyers') {
    if (req.method === 'GET') {
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/parties?party_type=neq.FARMER&order=name.asc&limit=100`, {
          headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}` }
        });
        if (!resp.ok) return res.status(200).json({ success: true, buyers: [] });
        const parties = await resp.json();
        return res.status(200).json({ success: true, buyers: Array.isArray(parties) ? parties : [], count: parties.length });
      } catch (err) {
        return res.status(200).json({ success: true, buyers: [], error: err.message });
      }
    }
    if (req.method === 'POST') {
      try {
        let body = req.body;
        if (typeof body === 'string') { try { body = JSON.parse(body); } catch (_) {} }
        const payload = {
          name: (body.company_name || body.name || '').trim(),
          phone: (body.phone || body.contact_phone || '').trim(),
          party_type: 'BUYER',
          gstin: body.gstin || null,
          village: body.mill_address || body.location || '',
          updated_at: new Date().toISOString()
        };
        const resp = await fetch(`${supabaseUrl}/rest/v1/parties`, {
          method: 'POST',
          headers: {
            'apikey': serviceKey,
            'Authorization': `Bearer ${serviceKey}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
          },
          body: JSON.stringify(payload)
        });
        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: 'Buyer company registered successfully', data: await resp.json() });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 2. RATES ACTION (MANDI CORRIDOR RATES)
  // =========================================================================
  if (action === 'rates') {
    const defaultRates = [
      { commodity_name: 'Soyabean (Yellow)', min_rate_per_qtl: 6500.0, target_rate_per_qtl: 6850.0, max_rate_per_qtl: 7500.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) },
      { commodity_name: 'Chana (Desi)', min_rate_per_qtl: 5600.0, target_rate_per_qtl: 5900.0, max_rate_per_qtl: 6400.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) },
      { commodity_name: 'Toor (White)', min_rate_per_qtl: 7800.0, target_rate_per_qtl: 8200.0, max_rate_per_qtl: 8800.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) },
      { commodity_name: 'Wheat (Sharbati)', min_rate_per_qtl: 2750.0, target_rate_per_qtl: 2950.0, max_rate_per_qtl: 3300.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) },
      { commodity_name: 'Maize (Yellow)', min_rate_per_qtl: 2100.0, target_rate_per_qtl: 2300.0, max_rate_per_qtl: 2550.0, quality_grade: 'FAQ_GRADE_1', rate_date: new Date().toISOString().slice(0, 10) }
    ];

    if (req.method === 'GET') {
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/daily_commodity_rates?select=*&order=updated_at.desc&limit=100`, {
          headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}` }
        });
        if (!resp.ok) return res.status(200).json({ success: true, rates: defaultRates, is_fallback: true });
        const rows = await resp.json();
        if (!Array.isArray(rows) || rows.length === 0) return res.status(200).json({ success: true, rates: defaultRates, is_fallback: true });

        const ratesMap = {};
        for (const r of rows) {
          if (!ratesMap[r.commodity_name]) ratesMap[r.commodity_name] = r;
        }
        return res.status(200).json({ success: true, rates: Object.values(ratesMap), count: Object.keys(ratesMap).length });
      } catch (err) {
        return res.status(200).json({ success: true, rates: defaultRates, error: err.message, is_fallback: true });
      }
    }

    if (req.method === 'POST') {
      try {
        let body = req.body;
        if (typeof body === 'string') { try { body = JSON.parse(body); } catch (_) {} }
        if (!body || !body.commodity_name) return res.status(400).json({ success: false, error: 'commodity_name is required' });

        const todayStr = new Date().toISOString().slice(0, 10);
        const rateDate = body.rate_date || todayStr;
        const minRate = parseFloat(body.min_rate_per_qtl) || 0.0;
        const targetRate = parseFloat(body.target_rate_per_qtl) || minRate;
        const maxRate = parseFloat(body.max_rate_per_qtl) || targetRate;
        const branchId = body.branch_id || null;

        const payload = {
          id: `rate-${rateDate}-${body.commodity_name.toLowerCase().replace(/[^a-z0-9]/g, '-')}-${branchId || 'global'}`,
          rate_date: rateDate,
          commodity_name: body.commodity_name,
          branch_id: branchId,
          min_rate_per_qtl: minRate,
          target_rate_per_qtl: targetRate,
          max_rate_per_qtl: maxRate,
          quality_grade: body.quality_grade || 'FAQ_GRADE_1',
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

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: `Published rate for ${body.commodity_name} (₹${targetRate}/Qtl) to Supabase Cloud!`, data: await resp.json() });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 3b. OUTWARD ACTION (COMMODITY SALES & DISPATCH)
  // =========================================================================
  if (action === 'outward') {
    if (req.method === 'GET') {
      try {
        const branchId = req.query.branch_id;
        let queryParams = `select=*&order=created_at.desc&limit=50`;
        if (branchId && branchId !== 'all') queryParams += `&branch_id=eq.${encodeURIComponent(branchId)}`;
        const resp = await fetch(`${supabaseUrl}/rest/v1/outward_orders?${queryParams}`, {
          headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}` }
        });
        const orders = resp.ok ? await resp.json() : [];
        return res.status(200).json({ success: true, orders: orders });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message, orders: [] });
      }
    }
    if (req.method === 'POST') {
      try {
        let body = req.body;
        if (typeof body === 'string') { try { body = JSON.parse(body); } catch (_) {} }
        const now = new Date();
        const challanNo = `OUT-${now.getFullYear().toString().slice(-2)}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}-${Math.random().toString(36).substring(2,6).toUpperCase()}`;
        const gross = parseFloat(body.gross_weight_kg) || 0;
        const tare = parseFloat(body.tare_weight_kg) || 0;
        const netKg = Math.max(0, gross - tare);
        const netQtl = parseFloat(body.net_quintals) || parseFloat((netKg / 100).toFixed(4));
        const rate = parseFloat(body.rate_per_quintal) || 0;
        const total = parseFloat((netQtl * rate).toFixed(2));

        const orderPayload = {
          id: `ord-${Date.now()}-${Math.random().toString(36).substring(2,5)}`,
          challan_number: challanNo,
          branch_id: body.branch_id || 'br-chikhali',
          buyer_name: (body.buyer_name || 'Agro Industries').trim(),
          buyer_phone: body.buyer_phone || '',
          commodity_name: body.commodity_name || 'Soyabean (Yellow)',
          vehicle_number: (body.vehicle_number || body.vehicle_no || 'MH28-OUTWARD').toUpperCase().trim(),
          bags_count: parseInt(body.bags_count || body.bags || 0, 10),
          gross_weight_kg: gross,
          tare_weight_kg: tare,
          net_weight_kg: netKg,
          net_quintals: netQtl,
          rate_per_quintal: rate,
          total_amount: total,
          mandi_cess_amount: 0.0,
          payment_status: body.payment_status || 'PENDING',
          updated_at: now.toISOString()
        };

        const resp = await fetch(`${supabaseUrl}/rest/v1/outward_orders`, {
          method: 'POST',
          headers: {
            'apikey': serviceKey,
            'Authorization': `Bearer ${serviceKey}`,
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates,return=representation'
          },
          body: JSON.stringify(orderPayload)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        const inserted = await resp.json();
        return res.status(200).json({ success: true, message: `Outward Dispatch #${challanNo} recorded!`, challan_number: challanNo, data: inserted });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 3. INVOICES ACTION (WEIGHMENT PURCHASES & RTGS)
  // =========================================================================
  if (action === 'invoices') {
    if (req.method === 'GET') {
      try {
        const branchId = req.query.branch_id;
        const status = req.query.status;
        const limit = parseInt(req.query.limit, 10) || 50;

        let queryParams = `select=*&order=created_at.desc&limit=${limit}`;
        if (branchId && branchId !== 'all') queryParams += `&branch_id=eq.${encodeURIComponent(branchId)}`;
        if (status) queryParams += `&payout_status=eq.${encodeURIComponent(status)}`;

        const resp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices?${queryParams}`, {
          headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}` }
        });

        if (!resp.ok) return res.status(200).json({ success: true, count: 0, invoices: [] });
        const invoices = await resp.json();
        return res.status(200).json({ success: true, count: Array.isArray(invoices) ? invoices.length : 0, invoices: Array.isArray(invoices) ? invoices : [] });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }

    if (req.method === 'POST') {
      try {
        let body = req.body;
        if (typeof body === 'string') { try { body = JSON.parse(body); } catch (_) {} }
        if (!body) return res.status(400).json({ success: false, error: 'Request body required' });

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
        const kardaDeductionKg = parseFloat(body.karda_deduction_kg) || 0.0;
        const netQuintals = Math.max(0.0, parseFloat(((netWeightKg - kardaDeductionKg) / 100.0).toFixed(2)));

        const ratePerQtl = parseFloat(body.rate_per_quintal) || 0.0;
        const grossAmount = parseFloat((netQuintals * ratePerQtl).toFixed(2));
        const hamaliAmount = parseFloat((netQuintals * 12.0).toFixed(2));
        const tolaiAmount = parseFloat((netQuintals * 5.0).toFixed(2));
        const netPayable = Math.max(0.0, parseFloat((grossAmount - hamaliAmount - tolaiAmount).toFixed(2)));

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
          mandi_cess_amount: 0.0, // 0% Mandi Cess
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

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        const inserted = await resp.json();

        // Complete linked QC ticket
        if (body.qc_ticket_no) {
          try {
            await fetch(`${supabaseUrl}/rest/v1/quality_inspections?ticket_no=eq.${encodeURIComponent(body.qc_ticket_no)}`, {
              method: 'PATCH',
              headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}`, 'Content-Type': 'application/json' },
              body: JSON.stringify({ status: 'COMPLETED', invoice_id: invoiceId, updated_at: now.toISOString() })
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

    if (req.method === 'PATCH') {
      try {
        const { id, token_number, rtgs_utr_no, payout_status } = req.body;
        const filterCol = id ? `id=eq.${encodeURIComponent(id)}` : `token_number=eq.${encodeURIComponent(token_number)}`;
        const updateData = { updated_at: new Date().toISOString() };
        if (rtgs_utr_no) updateData.rtgs_utr_no = rtgs_utr_no;
        if (payout_status) updateData.payout_status = payout_status;

        const resp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices?${filterCol}`, {
          method: 'PATCH',
          headers: { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}`, 'Content-Type': 'application/json', 'Prefer': 'return=representation' },
          body: JSON.stringify(updateData)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: `RTGS payment updated successfully!`, data: await resp.json() });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 4. SUMMARY ACTION (EXECUTIVE KPI & TELEMETRY)
  // =========================================================================
  try {
    const headers = { 'apikey': serviceKey, 'Authorization': `Bearer ${serviceKey}` };
    const [invoicesResp, inspectionsResp] = await Promise.all([
      fetch(`${supabaseUrl}/rest/v1/purchase_invoices?select=id,branch_id,net_quintals,net_payable_amount,weighment_mode,payout_status&order=created_at.desc&limit=200`, { headers }),
      fetch(`${supabaseUrl}/rest/v1/quality_inspections?select=id,status&order=created_at.desc&limit=100`, { headers })
    ]);

    const invoices = invoicesResp.ok ? await invoicesResp.json() : [];
    const inspections = inspectionsResp.ok ? await inspectionsResp.json() : [];

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

        if (inv.weighment_mode === 'CASH') cashPaid += amt;
        else if (inv.payout_status === 'PAID') rtgsPaid += amt;
        else rtgsPending += amt;

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
      }
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}
