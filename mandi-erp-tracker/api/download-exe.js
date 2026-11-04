// Vercel Serverless Function: Direct Windows Single EXE Download
module.exports = (req, res) => {
    const TARGET_URL = "https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp/releases/download/v1.0/Rajarshi_Shahu_Trading.exe";
    
    res.setHeader('Content-Type', 'application/x-msdownload');
    res.setHeader('Content-Disposition', 'attachment; filename="Rajarshi_Shahu_Trading.exe"');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    
    res.writeHead(302, { Location: TARGET_URL });
    res.end();
};
