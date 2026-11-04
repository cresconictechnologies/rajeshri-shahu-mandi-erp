// Vercel Serverless Function: Streamlined Direct Windows Package Download
module.exports = (req, res) => {
    const TARGET_URL = "https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp/releases/download/v1.0/Rajarshi_Shahu_Trading_Windows_x64.zip";
    
    res.setHeader('Content-Type', 'application/octet-stream');
    res.setHeader('Content-Disposition', 'attachment; filename="Rajarshi_Shahu_Trading_Windows_x64.zip"');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    
    res.writeHead(302, { Location: TARGET_URL });
    res.end();
};
