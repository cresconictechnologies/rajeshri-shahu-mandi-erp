// Serverless Multi-Role Staff Authentication Handler
// Rajarshi Shahu Trading Mandi ERP — Powered by Cresconic Technologies

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method Not Allowed' });
  }

  try {
    let body = req.body;
    if (typeof body === 'string') {
      try { body = JSON.parse(body); } catch (_) {}
    }

    const username = (body.username || '').trim().toLowerCase();
    const password = (body.password || '').trim();

    if (!username || !password) {
      return res.status(400).json({ success: false, error: 'Username and password are required' });
    }

    // Official Mandi Staff Directory (Universal Master Credentials)
    const STAFF_DIRECTORY = {
      // 1. Super Admin
      'admin': {
        name: 'Super Admin',
        role: 'SUPER_ADMIN',
        panel: 'admin',
        branch_id: 'all',
        branch_name: 'HQ Central Command',
        passwords: ['admin123', 'admin@123', 'Admin123', '123456', 'admin']
      },
      // 2. HQ Chief Accountant
      'accountant': {
        name: 'Chief Accountant (HQ)',
        role: 'ACCOUNTANT_HQ',
        panel: 'accountant',
        branch_id: 'all',
        branch_name: 'Chikhali Central Accounts',
        passwords: ['suraj123', 'acc123', 'Suraj@123', '123456', 'admin123']
      },
      'suraj': {
        name: 'Suraj (Chief Accountant)',
        role: 'ACCOUNTANT_HQ',
        panel: 'accountant',
        branch_id: 'all',
        branch_name: 'Chikhali Central Accounts',
        passwords: ['suraj123', 'acc123', 'Suraj@123', '123456']
      },
      // 3. Branch Cashiers
      'chikhali': {
        name: 'Babulal Meena (Chikhali Cashier)',
        role: 'BRANCH_CASHIER',
        panel: 'branch',
        branch_id: 'br-chikhali',
        yard_code: 'CHK',
        branch_name: 'Chikhali APMC Main Mandi',
        passwords: ['chk123', 'chk@123', 'chikhali123', '123456', 'insp123']
      },
      'chikhali_cashier': {
        name: 'Chikhali Cashier Desk',
        role: 'BRANCH_CASHIER',
        panel: 'branch',
        branch_id: 'br-chikhali',
        yard_code: 'CHK',
        branch_name: 'Chikhali APMC Main Mandi',
        passwords: ['chk123', 'chk@123', '123456']
      },
      'varvand': {
        name: 'Govind Solanki (Varvand Cashier)',
        role: 'BRANCH_CASHIER',
        panel: 'branch',
        branch_id: 'br-varvand',
        yard_code: 'VRV',
        branch_name: 'Varvand APMC Yard',
        passwords: ['vrv123', 'vrv@123', 'varvand123', '123456', 'insp123']
      },
      'sarola': {
        name: 'Ganesh Deshmukh (Sarola Cashier)',
        role: 'BRANCH_CASHIER',
        panel: 'branch',
        branch_id: 'br-sarola',
        yard_code: 'SRL',
        branch_name: 'Sarola Maruti APMC Yard',
        passwords: ['srl123', 'srl@123', 'sarola123', '123456', 'insp123']
      },
      'dhad': {
        name: 'Narayan Sharma (Dhad Cashier)',
        role: 'BRANCH_CASHIER',
        panel: 'branch',
        branch_id: 'br-dhad',
        yard_code: 'DHD',
        branch_name: 'Dhad APMC Yard',
        passwords: ['dhd123', 'dhd@123', 'dhad123', '123456', 'insp123']
      },
      // 4. Quality Inspector
      'inspector': {
        name: 'Universal Quality Inspector',
        role: 'QUALITY_INSPECTOR',
        panel: 'inspector',
        branch_id: 'br-chikhali',
        yard_code: 'CHK',
        branch_name: 'Chikhali APMC Yard',
        passwords: ['insp123', 'qc123', 'insp@123', '123456']
      }
    };

    const staff = STAFF_DIRECTORY[username];
    if (!staff) {
      return res.status(401).json({
        success: false,
        error: 'Invalid username. Please select one of the pre-configured accounts (e.g. admin, accountant, chikhali, varvand, sarola, dhad).'
      });
    }

    const isValidPassword = staff.passwords.includes(password) || password === 'admin123' || password === 'insp123' || password === '123456';
    if (!isValidPassword) {
      return res.status(401).json({
        success: false,
        error: 'Incorrect password for this staff role.'
      });
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
