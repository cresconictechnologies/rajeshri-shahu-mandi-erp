"""
Comprehensive Design Audit Suite for Mandi & Commodity Procurement ERP
Verifies Card-First UI, Light-to-Colourful Theme, Typography, Responsiveness, and Multi-Tier Consistency.
"""

import os
import re
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import app

class TestMandiDesignAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        client = TestClient(app)
        cls.pages = {
            "hub": client.get("/?hub=1").text,
            "admin": client.get("/admin/dashboard").text,
            "accounts": client.get("/accounts/dashboard").text,
            "branch": client.get("/branch/dashboard?branch_id=br-chikhali").text,
        }
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "theme.css"), "r", encoding="utf-8") as f:
            cls.css = f.read()

    def test_01_all_pages_link_to_master_theme_css(self):
        """Every portal must link to the single unified static/theme.css stylesheet."""
        for name, html in self.pages.items():
            self.assertIn("/static/theme.css", html, f"Page {name} must link to /static/theme.css")

    def test_02_card_first_architecture_encapsulation(self):
        """Every single page must encapsulate content in .card, .stat-card, .portal-card, or .header-card."""
        for name, html in self.pages.items():
            total_cards = len(re.findall(r'class="[^"]*\b(card|stat-card|portal-card|header-card|commodity-card)\b[^"]*"', html))
            self.assertGreater(total_cards, 5, f"Page {name} must have card-first structure (found {total_cards})")
            # Ensure no uncarded tables directly under body
            self.assertNotIn("<body><table", html.replace(" ", "").replace("\n", ""))

    def test_03_light_theme_color_tokens(self):
        """Master CSS must define pure white cards and soft slate canvas tokens."""
        self.assertIn("--canvas-bg: #f8fafc;", self.css)
        self.assertIn("--card-bg: #ffffff;", self.css)
        self.assertIn("--card-border: #e2e8f0;", self.css)
        self.assertIn("--text-primary: #0f172a;", self.css)

    def test_04_tier_identity_gradients(self):
        """Master CSS must provide distinct colorful gradients for all 3 tiers."""
        # Level 1 Super Admin: Sapphire Blue / Indigo
        self.assertIn("--admin-gradient: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);", self.css)
        # Level 2 Central Accounts: Emerald / Teal
        self.assertIn("--accounts-gradient: linear-gradient(135deg, #059669 0%, #0d9488 100%);", self.css)
        # Level 3 Branch Operations: Harvest Amber / Orange
        self.assertIn("--branch-gradient: linear-gradient(135deg, #d97706 0%, #ea580c 100%);", self.css)

    def test_05_interactive_commodity_cards_grid(self):
        """Both Central Accounts and Branch Operations must display interactive commodity cards."""
        for page_name in ["accounts", "branch"]:
            html = self.pages[page_name]
            self.assertIn("commodity-cards-grid", html)
            self.assertIn("commodity-card", html)
            self.assertIn("Soyabean (Yellow)", html)
            self.assertIn("Wheat (Lokwan)", html)
            self.assertIn("Chana (Desi)", html)
            self.assertIn("Mustard (Rayda)", html)
            self.assertIn("Maize (Makka)", html)

    def test_06_commodity_card_click_reactivity(self):
        """Commodity cards must have click handlers that dynamically populate form rates and banners."""
        # Branch terminal
        self.assertIn("selectCommodityCard(this)", self.pages["branch"])
        self.assertIn("function selectCommodityCard", self.pages["branch"])
        self.assertIn("bannerLimits", self.pages["branch"])
        # Accounts desk
        self.assertIn("selectAccountCommodity(this)", self.pages["accounts"])
        self.assertIn("function selectAccountCommodity", self.pages["accounts"])

    def test_07_status_badge_and_color_pills(self):
        """Pages must use semantic status badges (green, amber, red, blue)."""
        for name, html in self.pages.items():
            has_badge = ("badge-pill" in html) or ("brand-badge" in html)
            self.assertTrue(has_badge, f"Page {name} must feature colorful status badges")

    def test_08_modal_card_design(self):
        """Modals (Cashier Payout Desk & Farmer Registration) must be styled as elevated cards."""
        branch_html = self.pages["branch"]
        self.assertIn("modal-overlay", branch_html)
        self.assertIn('class="modal"', branch_html)
        self.assertIn("Cashier Payout & Denomination Tally", branch_html)
        self.assertIn("Register New Farmer / Cultivator", branch_html)

    def test_09_responsive_mobile_and_grid_css(self):
        """Master CSS must include media queries for mobile/tablet responsive layout."""
        self.assertIn("@media (max-width: 1024px)", self.css)
        self.assertIn("@media (max-width: 768px)", self.css)
        self.assertIn("grid-template-columns: 1fr;", self.css)

    def test_10_port_8080_isolation_confirmed(self):
        """All pages must reference Port 8080 and maintain strict isolation from restaurant app on Port 8000."""
        for name, html in self.pages.items():
            self.assertIn("Port 8080", html, f"Page {name} must indicate Port 8080 active")
            self.assertNotIn(":8000", html, f"Page {name} must never contain hardcoded port 8000")


if __name__ == "__main__":
    unittest.main()
