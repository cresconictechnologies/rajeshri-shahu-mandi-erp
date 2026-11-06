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

  let action = req.query.action;
  if (!action) {
    if (req.url.includes('/auth')) action = 'auth';
    else if (req.url.includes('/rates')) action = 'rates';
    else if (req.url.includes('/invoices')) action = 'invoices';
    else if (req.url.includes('/branches')) action = 'branches';
    else if (req.url.includes('/users')) action = 'users';
    else if (req.url.includes('/commodities')) action = 'commodities';
    else if (req.url.includes('/inspectors')) action = 'inspectors';
    else if (req.url.includes('/tickets') || req.url.includes('/inspections')) action = 'tickets';
    else if (req.url.includes('/overrides')) action = 'overrides';
    else if (req.url.includes('/outward')) action = 'outward';
    else if (req.url.includes('/admin/data')) action = 'admin_data';
    else if (req.url.includes('/accounts/data')) action = 'accounts_data';
    else action = 'summary';
  }

  const headers = {
    'apikey': serviceKey,
    'Authorization': `Bearer ${serviceKey}`,
    'Content-Type': 'application/json'
  };

  // Helper to parse body
  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch (_) {}
  }
  body = body || {};

  // =========================================================================
  // 1. AUTH ACTION
  // =========================================================================
  if (action === 'auth') {
    if (req.method !== 'POST') return res.status(405).json({ success: false, error: 'Method Not Allowed' });
    try {
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

      if (STAFF_DIRECTORY[username]) {
        const staff = STAFF_DIRECTORY[username];
        if (staff.passwords.includes(password)) {
          return res.status(200).json({
            success: true,
            user: {
              username,
              name: staff.name,
              role: staff.role,
              panel: staff.panel,
              branch_id: staff.branch_id,
              branch_name: staff.branch_name,
              yard_code: staff.yard_code || 'HQ',
              mandi_license: 'MH/STATE/ERP-PRO',
              token: 'jwt-session-' + Date.now()
            }
          });
        }
      }

      // Check Supabase users table
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/users?username=ilike.${encodeURIComponent(username)}&limit=1`, { headers });
        if (resp.ok) {
          const rows = await resp.json();
          if (Array.isArray(rows) && rows.length > 0) {
            const u = rows[0];
            return res.status(200).json({
              success: true,
              user: {
                username: u.username,
                name: u.full_name,
                role: u.role,
                panel: u.role === 'SUPER_ADMIN' ? 'admin' : (u.role === 'ACCOUNTANT_HQ' ? 'accountant' : (u.role === 'QUALITY_INSPECTOR' ? 'inspector' : 'branch')),
                branch_id: u.branch_id || 'br-chikhali',
                branch_name: u.branch_name || 'Assigned Yard',
                yard_code: u.branch_id ? u.branch_id.replace('br-', '').toUpperCase() : 'HQ',
                mandi_license: 'MH/STATE/ERP-PRO',
                token: 'jwt-session-' + Date.now()
              }
            });
          }
        }
      } catch (_) {}

      return res.status(401).json({ success: false, error: 'Invalid terminal credentials.' });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  // =========================================================================
  // 2. RATES ACTION (PRICE CORRIDORS)
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
        const resp = await fetch(`${supabaseUrl}/rest/v1/daily_commodity_rates?select=*&order=updated_at.desc&limit=100`, { headers });
        if (!resp.ok) return res.status(200).json({ success: true, rates: defaultRates });
        const rows = await resp.json();
        if (!Array.isArray(rows) || rows.length === 0) return res.status(200).json({ success: true, rates: defaultRates });

        const ratesMap = {};
        for (const r of rows) {
          if (!ratesMap[r.commodity_name]) ratesMap[r.commodity_name] = r;
        }
        return res.status(200).json({ success: true, rates: Object.values(ratesMap), count: Object.keys(ratesMap).length });
      } catch (err) {
        return res.status(200).json({ success: true, rates: defaultRates, error: err.message });
      }
    }

    if (req.method === 'POST') {
      try {
        if (!body.commodity_name) return res.status(400).json({ success: false, error: 'commodity_name is required' });
        const todayStr = new Date().toISOString().slice(0, 10);
        const rateDate = body.rate_date || todayStr;
        const minRate = parseFloat(body.min_rate || body.min_rate_per_qtl) || 0.0;
        const targetRate = parseFloat(body.target_rate || body.target_rate_per_qtl) || minRate;
        const maxRate = parseFloat(body.max_rate || body.max_rate_per_qtl) || targetRate;
        const branchId = body.branch_id || null;

        const payload = {
          id: `rate-${rateDate}-${body.commodity_name.toLowerCase().replace(/[^a-z0-9]/g, '-')}-${branchId || 'global'}`,
          rate_date: rateDate,
          commodity_name: body.commodity_name,
          branch_id: branchId,
          min_rate_per_qtl: minRate,
          target_rate_per_qtl: targetRate,
          max_rate_per_qtl: maxRate,
          quality_grade: body.quality_grade || 'STANDARD',
          updated_at: new Date().toISOString()
        };

        const resp = await fetch(`${supabaseUrl}/rest/v1/daily_commodity_rates`, {
          method: 'POST',
          headers: { ...headers, 'Prefer': 'resolution=merge-duplicates,return=representation' },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: `Price Corridor for ${body.commodity_name} published successfully!`, rate: payload });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 3. INVOICES ACTION (CROSS-BRANCH INWARD PURCHASES)
  // =========================================================================
  if (action === 'invoices') {
    if (req.method === 'GET') {
      try {
        const branchFilter = req.query.branch_id && req.query.branch_id !== 'all' ? `&branch_id=eq.${encodeURIComponent(req.query.branch_id)}` : '';
        const targetDate = req.query.target_date ? `&invoice_date=eq.${encodeURIComponent(req.query.target_date)}` : '';
        const resp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices?select=*${branchFilter}${targetDate}&order=created_at.desc&limit=150`, { headers });
        if (!resp.ok) return res.status(200).json({ success: true, invoices: [] });
        const rows = await resp.json();
        return res.status(200).json({ success: true, invoices: Array.isArray(rows) ? rows : [] });
      } catch (err) {
        return res.status(200).json({ success: true, invoices: [], error: err.message });
      }
    }

    if (req.method === 'POST') {
      try {
        const branchId = body.branch_id || 'br-chikhali';
        const now = new Date();
        const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
        const randomNum = Math.floor(1000 + Math.random() * 9000);
        const prefix = branchId.replace('br-', '').toUpperCase();
        const tokenNumber = body.token_number || `${prefix}-${dateStr}-${randomNum}`;
        const invoiceId = body.id || `inv-${Date.now()}-${randomNum}`;

        const grossKg = parseFloat(body.gross_weight_kg) || 0.0;
        const tareKg = parseFloat(body.tare_weight_kg) || 0.0;
        const grossWeight = parseFloat(body.gross_weight) || (grossKg > 0 ? grossKg : 0.0);
        const netWeight = grossWeight - tareKg;
        const netQuintals = parseFloat(body.net_quintals) || (netWeight / 100.0);
        const ratePerQtl = parseFloat(body.rate_per_quintal) || 0.0;
        const grossPayable = netQuintals * ratePerQtl;
        const hamali = parseFloat(body.hamali_deduction) || 0.0;
        const weighbridge = parseFloat(body.weighbridge_deduction) || 0.0;
        const totalDeductions = hamali + weighbridge;
        const netPayable = parseFloat(body.net_payable_amount) || (grossPayable - totalDeductions);
        const weighmentMode = (body.weighment_mode || 'CASH').toUpperCase();
        const payoutStatus = weighmentMode === 'CASH' ? 'PAID' : (body.payout_status || 'PENDING');

        const invoicePayload = {
          id: invoiceId,
          branch_id: branchId,
          branch_name: body.branch_name || (branchId === 'br-chikhali' ? 'Chikhali APMC Main Mandi' : (branchId === 'br-varvand' ? 'Varvand APMC Yard' : (branchId === 'br-sarola' ? 'Sarola Maruti APMC Yard' : 'Dhad APMC Yard'))),
          token_number: tokenNumber,
          party_id: body.party_id || `farmer-${Date.now()}`,
          party_name: body.party_name || 'Farmer',
          party_type: (body.party_type || 'FARMER').toUpperCase(),
          party_phone: body.party_phone || null,
          commodity_id: body.commodity_id || 'comm-soya',
          commodity_name: body.commodity_name || 'Soyabean (Yellow)',
          gross_weight_kg: grossWeight,
          tare_weight_kg: tareKg,
          net_weight_kg: netWeight,
          net_quintals: netQuintals,
          rate_per_quintal: ratePerQtl,
          gross_amount: grossPayable,
          hamali_deduction: hamali,
          weighbridge_deduction: weighbridge,
          total_deductions: totalDeductions,
          net_payable_amount: netPayable,
          weighment_mode: weighmentMode,
          payout_status: payoutStatus,
          cashier_user_id: body.cashier_user_id || 'cashier-1',
          cashier_name: body.cashier_name || 'Branch Cashier',
          qc_ticket_no: body.qc_ticket_no || null,
          invoice_date: body.invoice_date || now.toISOString().slice(0, 10),
          created_at: now.toISOString(),
          rtgs_bank_name: body.rtgs_bank_name || null,
          rtgs_account_no: body.rtgs_account_no || null,
          rtgs_ifsc_code: body.rtgs_ifsc_code || null,
          rtgs_beneficiary_name: body.rtgs_beneficiary_name || body.party_name || null,
          rtgs_utr_no: body.rtgs_utr_no || body.bank_utr_no || null,
          updated_at: now.toISOString()
        };

        const resp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices`, {
          method: 'POST',
          headers: { ...headers, 'Prefer': 'resolution=merge-duplicates,return=representation' },
          body: JSON.stringify(invoicePayload)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: `Invoice #${tokenNumber} registered!`, data: await resp.json() });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }

    if (req.method === 'PATCH') {
      try {
        const { id, invoice_id, token_number, rtgs_utr_no, bank_utr_no, payout_status } = body;
        const utr = rtgs_utr_no || bank_utr_no;
        const invId = id || invoice_id;
        const filterCol = invId ? `id=eq.${encodeURIComponent(invId)}` : `token_number=eq.${encodeURIComponent(token_number)}`;
        const updateData = { updated_at: new Date().toISOString() };
        if (utr) {
          updateData.rtgs_utr_no = utr;
          updateData.payout_status = 'PAID';
        }
        if (payout_status) updateData.payout_status = payout_status;

        const resp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices?${filterCol}`, {
          method: 'PATCH',
          headers: { ...headers, 'Prefer': 'return=representation' },
          body: JSON.stringify(updateData)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: `RTGS settlement processed successfully!`, data: await resp.json() });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 4. BRANCHES ACTION
  // =========================================================================
  if (action === 'branches') {
    if (req.method === 'GET') {
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/branches?select=*&order=created_at.asc`, { headers });
        if (!resp.ok) return res.status(200).json({ success: true, branches: [] });
        const rows = await resp.json();
        return res.status(200).json({ success: true, branches: Array.isArray(rows) ? rows : [] });
      } catch (err) {
        return res.status(200).json({ success: true, branches: [], error: err.message });
      }
    }

    if (req.method === 'POST') {
      try {
        if (body.action === 'delete' || body.delete_branch || req.method === 'DELETE') {
          const bId = body.branch_id || req.query.branch_id || body.id || req.query.id;
          const chk = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices?branch_id=eq.${encodeURIComponent(bId)}&select=id`, { headers });
          if (chk.ok) {
            const rows = await chk.json();
            if (Array.isArray(rows) && rows.length > 0) {
              return res.status(400).json({ success: false, error: `Cannot delete branch ${bId} with existing purchase transactions.` });
            }
          }
          const delResp = await fetch(`${supabaseUrl}/rest/v1/branches?id=eq.${encodeURIComponent(bId)}`, { method: 'DELETE', headers });
          if (!delResp.ok) return res.status(delResp.status).json({ success: false, error: await delResp.text() });
          return res.status(200).json({ success: true, message: `Branch ${bId} deleted successfully.` });
        }

        if (body.branch_id && !body.name) {
          // Toggle action
          const resp = await fetch(`${supabaseUrl}/rest/v1/branches?id=eq.${encodeURIComponent(body.branch_id)}`, { headers });
          if (resp.ok) {
            const current = (await resp.json())[0];
            const newStatus = current ? !current.is_active : true;
            await fetch(`${supabaseUrl}/rest/v1/branches?id=eq.${encodeURIComponent(body.branch_id)}`, {
              method: 'PATCH',
              headers,
              body: JSON.stringify({ is_active: newStatus, updated_at: new Date().toISOString() })
            });
            return res.status(200).json({ success: true, message: 'Branch status toggled!' });
          }
        }

        const bCode = (body.branch_code || '').trim().toUpperCase();
        const payload = {
          id: `br-${bCode.toLowerCase().replace(/[^a-z0-9]/g, '-')}`,
          branch_code: bCode,
          name: body.name,
          mandi_license_no: body.mandi_license_no || 'MH/APMC-GEN',
          address: body.address || '',
          phone: body.phone || '',
          is_active: true,
          created_at: new Date().toISOString()
        };

        const resp = await fetch(`${supabaseUrl}/rest/v1/branches`, {
          method: 'POST',
          headers: { ...headers, 'Prefer': 'resolution=merge-duplicates,return=representation' },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: `Branch ${body.name} provisioned!`, branch: payload });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 5. USERS ACTION
  // =========================================================================
  if (action === 'users') {
    if (req.method === 'GET') {
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/users?select=*&order=created_at.asc`, { headers });
        if (!resp.ok) return res.status(200).json({ success: true, users: [] });
        const rows = await resp.json();
        return res.status(200).json({ success: true, users: Array.isArray(rows) ? rows : [] });
      } catch (err) {
        return res.status(200).json({ success: true, users: [], error: err.message });
      }
    }

    if (req.method === 'POST') {
      try {
        if (body.action === 'delete' || body.delete_user || req.method === 'DELETE') {
          const uId = body.user_id || req.query.user_id || body.id || req.query.id;
          if (uId === 'usr-admin' || uId === 'admin') {
            return res.status(400).json({ success: false, error: 'Cannot delete primary SUPER_ADMIN user.' });
          }
          const delResp = await fetch(`${supabaseUrl}/rest/v1/users?id=eq.${encodeURIComponent(uId)}`, { method: 'DELETE', headers });
          if (!delResp.ok) return res.status(delResp.status).json({ success: false, error: await delResp.text() });
          return res.status(200).json({ success: true, message: `User ${uId} deleted successfully.` });
        }

        if (body.user_id && !body.username) {
          // Toggle user status
          const resp = await fetch(`${supabaseUrl}/rest/v1/users?id=eq.${encodeURIComponent(body.user_id)}`, { headers });
          if (resp.ok) {
            const current = (await resp.json())[0];
            const newStatus = current ? !current.is_active : true;
            await fetch(`${supabaseUrl}/rest/v1/users?id=eq.${encodeURIComponent(body.user_id)}`, {
              method: 'PATCH',
              headers,
              body: JSON.stringify({ is_active: newStatus, updated_at: new Date().toISOString() })
            });
            return res.status(200).json({ success: true, message: 'User status toggled!' });
          }
        }

        const username = (body.username || '').trim().toLowerCase();
        const payload = {
          id: `usr-${username}`,
          username: username,
          full_name: body.full_name,
          role: body.role,
          phone: body.phone || '',
          branch_id: body.branch_id || null,
          is_active: true,
          created_at: new Date().toISOString()
        };

        const resp = await fetch(`${supabaseUrl}/rest/v1/users`, {
          method: 'POST',
          headers: { ...headers, 'Prefer': 'resolution=merge-duplicates,return=representation' },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: `User ${body.username} created!`, user: payload });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 6. COMMODITIES ACTION
  // =========================================================================
  if (action === 'commodities') {
    if (req.method === 'GET') {
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/commodities?select=*&order=name.asc`, { headers });
        if (!resp.ok) return res.status(200).json({ success: true, commodities: [] });
        const rows = await resp.json();
        return res.status(200).json({ success: true, commodities: Array.isArray(rows) ? rows : [] });
      } catch (err) {
        return res.status(200).json({ success: true, commodities: [], error: err.message });
      }
    }

    if (req.method === 'POST') {
      try {
        const name = (body.name || '').trim();
        const payload = {
          id: `comm-${name.toLowerCase().replace(/[^a-z0-9]/g, '-')}`,
          name: name,
          hsn_code: body.hsn_code || '1201',
          standard_moisture_pct: parseFloat(body.standard_moisture_pct) || 10.0,
          is_active: 1,
          created_at: new Date().toISOString()
        };

        const resp = await fetch(`${supabaseUrl}/rest/v1/commodities`, {
          method: 'POST',
          headers: { ...headers, 'Prefer': 'resolution=merge-duplicates,return=representation' },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });

        // Auto-publish initial price corridor if provided
        if (body.target_rate || body.min_rate) {
          const ratePayload = {
            commodity_name: name,
            quality_grade: body.quality_grade || 'STANDARD',
            min_rate_per_qtl: parseFloat(body.min_rate) || 0,
            target_rate_per_qtl: parseFloat(body.target_rate) || 0,
            max_rate_per_qtl: parseFloat(body.max_rate) || 0,
            rate_date: body.rate_date || new Date().toISOString().slice(0, 10),
            updated_at: new Date().toISOString()
          };
          try {
            await fetch(`${supabaseUrl}/rest/v1/daily_commodity_rates`, {
              method: 'POST',
              headers: { ...headers, 'Prefer': 'resolution=merge-duplicates,return=representation' },
              body: JSON.stringify(ratePayload)
            });
          } catch (_) {}
        }

        return res.status(200).json({ success: true, message: `Commodity ${name} created successfully!`, commodity: payload });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }

    if (req.method === 'DELETE' || (req.method === 'POST' && (body.action === 'delete' || req.query.action === 'delete'))) {
      try {
        const commId = body.id || body.commodity_id || req.query.id;
        if (!commId) return res.status(400).json({ success: false, error: 'commodity id required' });
        const resp = await fetch(`${supabaseUrl}/rest/v1/commodities?id=eq.${encodeURIComponent(commId)}`, {
          method: 'DELETE',
          headers
        });
        return res.status(200).json({ success: true, message: `Commodity ${commId} removed` });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 7. INSPECTORS ACTION
  // =========================================================================
  if (action === 'inspectors') {
    if (req.method === 'GET') {
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/inspectors?select=*&order=name.asc`, { headers });
        if (!resp.ok) return res.status(200).json({ success: true, inspectors: [] });
        const rows = await resp.json();
        return res.status(200).json({ success: true, inspectors: Array.isArray(rows) ? rows : [] });
      } catch (err) {
        return res.status(200).json({ success: true, inspectors: [], error: err.message });
      }
    }

    if (req.method === 'POST') {
      try {
        if (body.action === 'delete' || body.delete_inspector || req.method === 'DELETE') {
          const insId = body.inspector_id || req.query.inspector_id || body.id || req.query.id;
          const delResp = await fetch(`${supabaseUrl}/rest/v1/inspectors?id=eq.${encodeURIComponent(insId)}`, { method: 'DELETE', headers });
          if (!delResp.ok) return res.status(delResp.status).json({ success: false, error: await delResp.text() });
          return res.status(200).json({ success: true, message: `Inspector ${insId} deleted successfully.` });
        }

        const id = body.inspector_id || `ins-${Date.now()}`;
        const payload = {
          id: id,
          name: body.name,
          designation: body.designation || 'Yard Assayer',
          phone: body.phone || '',
          branch_id: body.branch_id || 'br-chikhali',
          username: body.username || id,
          is_active: true,
          updated_at: new Date().toISOString()
        };

        const resp = await fetch(`${supabaseUrl}/rest/v1/inspectors`, {
          method: 'POST',
          headers: { ...headers, 'Prefer': 'resolution=merge-duplicates,return=representation' },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: `Inspector ${body.name} saved!`, inspector: payload });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 7B. QC TICKETS ACTION (INSPECTIONS & DELETION)
  // =========================================================================
  if (action === 'tickets' || action === 'pending_tickets' || action === 'delete_ticket') {
    // Handle ticket deletion
    if (req.method === 'DELETE' || action === 'delete_ticket' || (req.method === 'POST' && (body.action === 'delete' || req.query.action === 'delete'))) {
      try {
        const ticketNo = body.ticket_no || req.query.ticket_no || body.id || req.query.id;
        if (!ticketNo) {
          return res.status(400).json({ success: false, error: 'Ticket number or ID is required.' });
        }

        // Verify ticket is not linked to a settled purchase invoice
        try {
          const chkResp = await fetch(`${supabaseUrl}/rest/v1/purchase_invoices?qc_ticket_no=eq.${encodeURIComponent(ticketNo)}&limit=1`, { headers });
          if (chkResp.ok) {
            const rows = await chkResp.json();
            if (Array.isArray(rows) && rows.length > 0) {
              return res.status(400).json({ success: false, error: `Cannot delete QC Ticket #${ticketNo} because it has already been invoiced and settled.` });
            }
          }
        } catch (_) {}

        // Delete from quality_inspections
        const delResp = await fetch(`${supabaseUrl}/rest/v1/quality_inspections?ticket_no=eq.${encodeURIComponent(ticketNo)}`, {
          method: 'DELETE',
          headers
        });

        if (!delResp.ok) {
          return res.status(delResp.status).json({ success: false, error: await delResp.text() });
        }

        return res.status(200).json({ success: true, message: `QC Ticket #${ticketNo} deleted permanently.` });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }

    // Handle ticket fetching
    if (req.method === 'GET') {
      try {
        const branchId = req.query.branch_id;
        const status = req.query.status || 'PENDING';
        let url = `${supabaseUrl}/rest/v1/quality_inspections?order=created_at.desc&limit=100`;
        if (status && status !== 'all') {
          url += `&status=eq.${encodeURIComponent(status)}`;
        }
        if (branchId && branchId !== 'all') {
          url += `&branch_id=eq.${encodeURIComponent(branchId)}`;
        }

        const resp = await fetch(url, { headers });
        if (!resp.ok) {
          return res.status(200).json({ success: true, count: 0, tickets: [] });
        }
        const rows = await resp.json();
        const tickets = Array.isArray(rows) ? rows : [];
        return res.status(200).json({ success: true, count: tickets.length, tickets: tickets });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message, tickets: [] });
      }
    }
  }

  // =========================================================================
  // 8. OUTWARD ACTION (DISPATCH RECEIVABLES)
  // =========================================================================
  if (action === 'outward') {
    if (req.method === 'GET') {
      try {
        const resp = await fetch(`${supabaseUrl}/rest/v1/outward_orders?select=*&order=created_at.desc&limit=100`, { headers });
        if (!resp.ok) return res.status(200).json({ success: true, orders: [] });
        const rows = await resp.json();
        return res.status(200).json({ success: true, orders: Array.isArray(rows) ? rows : [] });
      } catch (err) {
        return res.status(200).json({ success: true, orders: [], error: err.message });
      }
    }

    if (req.method === 'POST') {
      try {
        // Record payment settlement
        if (body.challan_id || body.order_id) {
          const id = body.challan_id || body.order_id;
          const updateData = {
            payment_status: 'PAID',
            payment_mode: body.payment_mode || 'RTGS',
            receipt_date: body.receipt_date || new Date().toISOString().slice(0, 10),
            bank_utr_no: body.bank_utr_no || null,
            receiving_branch_id: body.receiving_branch_id || null,
            payment_notes: body.payment_notes || null,
            updated_at: new Date().toISOString()
          };

          const resp = await fetch(`${supabaseUrl}/rest/v1/outward_orders?id=eq.${encodeURIComponent(id)}`, {
            method: 'PATCH',
            headers: { ...headers, 'Prefer': 'return=representation' },
            body: JSON.stringify(updateData)
          });

          if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
          return res.status(200).json({ success: true, message: 'Outward payment recorded successfully!' });
        }

        // Create new dispatch challan
        const now = new Date();
        const challanNo = body.challan_number || `CH-${now.toISOString().slice(0,10).replace(/-/g,'')}-${Math.floor(100+Math.random()*900)}`;
        const netQtl = parseFloat(body.net_quintals) || 0.0;
        const rate = parseFloat(body.rate_per_quintal) || 0.0;
        const billAmt = parseFloat(body.total_bill_amount) || (netQtl * rate);

        const payload = {
          id: `out-${Date.now()}`,
          challan_number: challanNo,
          branch_id: body.branch_id || 'br-chikhali',
          buyer_id: body.buyer_id || `buyer-${Date.now()}`,
          buyer_name: body.buyer_name || 'Buyer Mill',
          commodity_name: body.commodity_name || 'Soyabean',
          vehicle_number: body.vehicle_number || '',
          driver_name: body.driver_name || '',
          net_quintals: netQtl,
          rate_per_quintal: rate,
          total_bill_amount: billAmt,
          payment_mode: body.payment_mode || 'RTGS',
          payment_status: 'PENDING',
          order_date: now.toISOString().slice(0, 10),
          created_at: now.toISOString()
        };

        const resp = await fetch(`${supabaseUrl}/rest/v1/outward_orders`, {
          method: 'POST',
          headers: { ...headers, 'Prefer': 'resolution=merge-duplicates,return=representation' },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) return res.status(resp.status).json({ success: false, error: await resp.text() });
        return res.status(200).json({ success: true, message: `Challan #${challanNo} generated!`, challan: payload });
      } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
      }
    }
  }

  // =========================================================================
  // 9. AGGREGATED ADMIN DATA ACTION
  // =========================================================================
  if (action === 'admin_data') {
    try {
      const [invoicesResp, inspectionsResp, branchesResp, usersResp, commoditiesResp] = await Promise.all([
        fetch(`${supabaseUrl}/rest/v1/purchase_invoices?select=*&order=created_at.desc&limit=150`, { headers }),
        fetch(`${supabaseUrl}/rest/v1/quality_inspections?select=*&order=created_at.desc&limit=100`, { headers }),
        fetch(`${supabaseUrl}/rest/v1/branches?select=*&order=created_at.asc`, { headers }),
        fetch(`${supabaseUrl}/rest/v1/users?select=*&order=created_at.asc`, { headers }),
        fetch(`${supabaseUrl}/rest/v1/commodities?select=*&order=name.asc`, { headers })
      ]);

      const invoices = invoicesResp.ok ? await invoicesResp.json() : [];
      const inspections = inspectionsResp.ok ? await inspectionsResp.json() : [];
      const branches = branchesResp.ok ? await branchesResp.json() : [];
      const users = usersResp.ok ? await usersResp.json() : [];
      const commodities = commoditiesResp.ok ? await commoditiesResp.json() : [];

      let totalQuintals = 0.0;
      let totalDisbursed = 0.0;
      let totalPnl = 0.0;

      for (const inv of invoices) {
        const qtl = parseFloat(inv.net_quintals) || 0.0;
        const amt = parseFloat(inv.net_payable_amount) || 0.0;
        totalQuintals += qtl;
        totalDisbursed += amt;
      }

      return res.status(200).json({
        success: true,
        stats: {
          branches_active: branches.filter(b => b.is_active).length,
          total_quintals: totalQuintals,
          total_disbursed: totalDisbursed,
          total_pnl: totalPnl,
          total_pnl_pct: '0.0',
          users_active: users.filter(u => u.is_active).length
        },
        invoices: invoices,
        inspections: inspections,
        branches: branches,
        users: users,
        commodities: commodities
      });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  // =========================================================================
  // 10. AGGREGATED ACCOUNTS DATA ACTION
  // =========================================================================
  if (action === 'accounts_data') {
    try {
      const [ratesResp, invoicesResp, outwardResp, inspectorsResp, commoditiesResp, ledgersResp] = await Promise.all([
        fetch(`${supabaseUrl}/rest/v1/daily_commodity_rates?select=*&order=updated_at.desc&limit=100`, { headers }),
        fetch(`${supabaseUrl}/rest/v1/purchase_invoices?select=*&order=created_at.desc&limit=200`, { headers }),
        fetch(`${supabaseUrl}/rest/v1/outward_orders?select=*&order=created_at.desc&limit=100`, { headers }),
        fetch(`${supabaseUrl}/rest/v1/inspectors?select=*&order=name.asc`, { headers }),
        fetch(`${supabaseUrl}/rest/v1/commodities?select=*&order=name.asc`, { headers }),
        fetch(`${supabaseUrl}/rest/v1/ledger_entries?select=*&order=created_at.desc&limit=100`, { headers })
      ]);

      const rawRates = ratesResp.ok ? await ratesResp.json() : [];
      const invoices = invoicesResp.ok ? await invoicesResp.json() : [];
      const outwardOrders = outwardResp.ok ? await outwardResp.json() : [];
      const inspectors = inspectorsResp.ok ? await inspectorsResp.json() : [];
      const commodities = commoditiesResp.ok ? await commoditiesResp.json() : [];
      const ledgers = ledgersResp.ok ? await ledgersResp.json() : [];

      // Deduplicate rates: keep only latest row per commodity
      const latestRatesMap = {};
      for (const r of (Array.isArray(rawRates) ? rawRates : [])) {
        if (!r.commodity_name) continue;
        const normKey = r.commodity_name.trim().toLowerCase();
        if (!latestRatesMap[normKey]) {
          latestRatesMap[normKey] = r;
        }
      }

      // Benchmark rate defaults for commodities not yet published
      const baselineDefaults = {
        'soya': { min: 6500, target: 6850, max: 7500 },
        'chana': { min: 5600, target: 5900, max: 6400 },
        'toor': { min: 7800, target: 8200, max: 8800 },
        'tur': { min: 7800, target: 8200, max: 8800 },
        'wheat': { min: 2750, target: 2950, max: 3300 },
        'maize': { min: 2100, target: 2300, max: 2550 },
        'mustard': { min: 4800, target: 5100, max: 5500 },
        'cotton': { min: 6800, target: 7100, max: 7500 },
        'groundnut': { min: 5800, target: 6100, max: 6600 },
        'moong': { min: 7400, target: 7800, max: 8400 },
        'urad': { min: 7200, target: 7600, max: 8200 },
        'masoor': { min: 5700, target: 6000, max: 6500 },
        'rajma': { min: 8200, target: 8700, max: 9400 },
        'jowar': { min: 2800, target: 3050, max: 3350 },
        'bajra': { min: 2150, target: 2350, max: 2600 }
      };

      for (const c of (Array.isArray(commodities) ? commodities : [])) {
        if (!c.name) continue;
        const normKey = c.name.trim().toLowerCase();
        if (!latestRatesMap[normKey]) {
          let b = { min: 3500, target: 4000, max: 4500 };
          for (const [k, v] of Object.entries(baselineDefaults)) {
            if (normKey.includes(k)) { b = v; break; }
          }
          latestRatesMap[normKey] = {
            id: `rate-${c.id || normKey}`,
            commodity_name: c.name,
            min_rate_per_qtl: b.min,
            target_rate_per_qtl: b.target,
            max_rate_per_qtl: b.max,
            quality_grade: 'STANDARD',
            rate_date: new Date().toISOString().slice(0, 10),
            standard_moisture_pct: c.standard_moisture_pct || 10.0,
            hsn_code: c.hsn_code || '1201'
          };
        }
      }

      const rates = Object.values(latestRatesMap);

      // Pending overrides
      const pendingOverrides = invoices.filter(inv => inv.rate_override_status === 'PENDING' || inv.is_backdated);

      // Pending RTGS
      const pendingRtgs = invoices.filter(inv => inv.weighment_mode === 'RTGS' && inv.payout_status !== 'PAID');

      // Outward metrics
      let totalOutwardBilled = 0.0;
      let totalOutwardReceived = 0.0;
      let totalOutwardPending = 0.0;
      let pendingOutwardCount = 0;

      for (const o of outwardOrders) {
        const amt = parseFloat(o.total_bill_amount) || 0.0;
        totalOutwardBilled += amt;
        if (o.payment_status === 'PAID') {
          totalOutwardReceived += amt;
        } else {
          totalOutwardPending += amt;
          pendingOutwardCount++;
        }
      }

      return res.status(200).json({
        success: true,
        rates: rates,
        pending_overrides: pendingOverrides,
        pending_rtgs: pendingRtgs,
        outward_orders: outwardOrders,
        inspectors: inspectors,
        commodities: commodities,
        ledgers: ledgers,
        metrics: {
          total_outward_billed: totalOutwardBilled,
          total_outward_received: totalOutwardReceived,
          total_outward_pending: totalOutwardPending,
          pending_outward_count: pendingOutwardCount
        }
      });
    } catch (err) {
      return res.status(500).json({ success: false, error: err.message });
    }
  }

  // =========================================================================
  // DEFAULT: SUMMARY ACTION
  // =========================================================================
  try {
    const [invoicesResp, branchesResp] = await Promise.all([
      fetch(`${supabaseUrl}/rest/v1/purchase_invoices?select=id,branch_id,net_quintals,net_payable_amount,weighment_mode,payout_status&limit=200`, { headers }),
      fetch(`${supabaseUrl}/rest/v1/branches?select=id,name,branch_code,is_active`, { headers })
    ]);

    const invoices = invoicesResp.ok ? await invoicesResp.json() : [];
    const branches = branchesResp.ok ? await branchesResp.json() : [];

    let totalQuintals = 0.0;
    let totalPayable = 0.0;
    for (const inv of invoices) {
      totalQuintals += parseFloat(inv.net_quintals) || 0.0;
      totalPayable += parseFloat(inv.net_payable_amount) || 0.0;
    }

    return res.status(200).json({
      success: true,
      timestamp: new Date().toISOString(),
      summary: {
        total_procurement_quintals: totalQuintals,
        total_payout_disbursed: totalPayable,
        active_branches_count: branches.filter(b => b.is_active).length,
        invoices_count: invoices.length
      }
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}
