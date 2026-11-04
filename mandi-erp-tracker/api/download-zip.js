// Vercel Serverless Function: Ultra-Fast High-Speed CDN Download (Bypasses GitHub ISP throttling)
module.exports = (req, res) => {
    // 302 Redirect directly to static asset on Vercel High-Speed Edge CDN (Mumbai/Delhi Pop)
    res.setHeader('Cache-Control', 'public, max-age=3600');
    res.writeHead(302, { Location: '/Rajarshi_Shahu_Trading_Windows_x64.zip' });
    res.end();
};
