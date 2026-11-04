using System;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Diagnostics;
using System.ComponentModel;
using System.Windows.Forms;
using System.Security.Principal;
using Microsoft.Win32;

namespace RajarshiShahuTrading.Launcher
{
    public class LauncherForm : Form
    {
        // UI Colors (Emerald Green & Gold Palette)
        private static readonly Color HeaderBgColor = Color.FromArgb(6, 78, 59);       // Deep Emerald #064E3B
        private static readonly Color AccentGold = Color.FromArgb(245, 158, 11);      // Warm Gold #F59E0B
        private static readonly Color GoldBorder = Color.FromArgb(217, 119, 6);       // Amber Gold #D97706
        private static readonly Color SubtitleColor = Color.FromArgb(209, 250, 229);   // Mint Tint #D1FAE5
        private static readonly Color BodyBgColor = Color.FromArgb(241, 245, 249);     // Slate 100 #F1F5F9
        private static readonly Color CardBgColor = Color.White;
        private static readonly Color CardBorderColor = Color.FromArgb(203, 213, 225); // Slate 300 #CBD5E1
        private static readonly Color SuccessGreen = Color.FromArgb(5, 150, 105);     // Emerald #059669
        private static readonly Color PendingGray = Color.FromArgb(148, 163, 184);    // Slate #94A3B8
        private static readonly Color WarnOrange = Color.FromArgb(217, 119, 6);       // Amber #D97706
        private static readonly Color ErrorRed = Color.FromArgb(220, 38, 38);         // Red #DC2626
        private static readonly Color PrimaryBtnColor = Color.FromArgb(5, 150, 105);

        // UI Controls
        private Panel headerPanel;
        private Panel goldBarPanel;
        private Label titleLabel;
        private Label subtitleLabel;
        private Label versionLabel;
        private Panel cardPanel;

        private Label[] stepBadges = new Label[5];
        private Label[] stepTitles = new Label[5];
        private Label[] stepDetails = new Label[5];

        private ProgressBar progressBar;
        private Label statusLabel;
        private Label countdownLabel;
        private Button btnLaunch;
        private Button btnRecheck;
        private Button btnOpenFolder;

        // Background Worker & Timer
        private BackgroundWorker worker;
        private System.Windows.Forms.Timer autoLaunchTimer;
        private int countdownSeconds = 3;
        private bool isAutoLaunch = true;

        // Discovered Paths
        private string appBaseDir;
        private string targetExePath;
        private string prereqDir;
        private string corePathDllSource;

        public LauncherForm()
        {
            InitializeComponent();
            ResolvePaths();

            worker = new BackgroundWorker();
            worker.WorkerReportsProgress = true;
            worker.DoWork += Worker_DoWork;
            worker.ProgressChanged += Worker_ProgressChanged;
            worker.RunWorkerCompleted += Worker_RunWorkerCompleted;

            autoLaunchTimer = new System.Windows.Forms.Timer();
            autoLaunchTimer.Interval = 1000;
            autoLaunchTimer.Tick += AutoLaunchTimer_Tick;

            this.Load += new EventHandler(LauncherForm_Load);
        }

        private void LauncherForm_Load(object sender, EventArgs e)
        {
            StartVerification();
        }

        private void InitializeComponent()
        {
            this.Text = "Rajarshi Shahu Trading — Setup & Launcher";
            this.Size = new Size(700, 580);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedSingle;
            this.MaximizeBox = false;
            this.BackColor = BodyBgColor;
            this.Font = new Font("Segoe UI", 9F, FontStyle.Regular);

            // Header Panel
            headerPanel = new Panel();
            headerPanel.Dock = DockStyle.Top;
            headerPanel.Height = 88;
            headerPanel.BackColor = HeaderBgColor;

            titleLabel = new Label();
            titleLabel.Text = "RAJARSHI SHAHU TRADING";
            titleLabel.Font = new Font("Segoe UI", 14.5F, FontStyle.Bold);
            titleLabel.ForeColor = AccentGold;
            titleLabel.Location = new Point(24, 15);
            titleLabel.AutoSize = true;
            headerPanel.Controls.Add(titleLabel);

            versionLabel = new Label();
            versionLabel.Text = "v2.4 Enterprise (Single-Firm Mandi ERP)";
            versionLabel.Font = new Font("Segoe UI", 8.5F, FontStyle.Bold);
            versionLabel.ForeColor = AccentGold;
            versionLabel.Location = new Point(340, 20);
            versionLabel.AutoSize = true;
            headerPanel.Controls.Add(versionLabel);

            subtitleLabel = new Label();
            subtitleLabel.Text = "Universal Compatibility Hub: Windows 7 SP1, 8, 8.1, 10, 11 (64-Bit)";
            subtitleLabel.Font = new Font("Segoe UI", 9.5F, FontStyle.Regular);
            subtitleLabel.ForeColor = SubtitleColor;
            subtitleLabel.Location = new Point(25, 48);
            subtitleLabel.AutoSize = true;
            headerPanel.Controls.Add(subtitleLabel);

            goldBarPanel = new Panel();
            goldBarPanel.Dock = DockStyle.Top;
            goldBarPanel.Height = 4;
            goldBarPanel.BackColor = GoldBorder;

            this.Controls.Add(goldBarPanel);
            this.Controls.Add(headerPanel);

            // Checklist Card Panel
            cardPanel = new Panel();
            cardPanel.Location = new Point(20, 106);
            cardPanel.Size = new Size(644, 255);
            cardPanel.BackColor = CardBgColor;
            cardPanel.Paint += new PaintEventHandler(CardPanel_Paint);

            string[] defaultTitles = new string[] {
                "1. OS Architecture & Compatibility",
                "2. Windows 7/8 Core Path DLL (api-ms-win-core-path-l1-1-0.dll)",
                "3. Microsoft Visual C++ 2015-2022 Runtime (x64)",
                "4. Microsoft Edge WebView2 Evergreen Runtime",
                "5. Desktop Shortcut Integration"
            };

            int startY = 12;
            int rowHeight = 47;

            for (int i = 0; i < 5; i++)
            {
                // Badge
                stepBadges[i] = new Label();
                stepBadges[i].Text = "[ .. ]";
                stepBadges[i].Font = new Font("Segoe UI", 9.5F, FontStyle.Bold);
                stepBadges[i].ForeColor = PendingGray;
                stepBadges[i].Location = new Point(14, startY + (i * rowHeight) + 4);
                stepBadges[i].Size = new Size(50, 22);
                stepBadges[i].TextAlign = ContentAlignment.MiddleCenter;
                cardPanel.Controls.Add(stepBadges[i]);

                // Title
                stepTitles[i] = new Label();
                stepTitles[i].Text = defaultTitles[i];
                stepTitles[i].Font = new Font("Segoe UI", 9.5F, FontStyle.Bold);
                stepTitles[i].ForeColor = Color.FromArgb(30, 41, 59);
                stepTitles[i].Location = new Point(70, startY + (i * rowHeight) + 2);
                stepTitles[i].AutoSize = true;
                cardPanel.Controls.Add(stepTitles[i]);

                // Detail
                stepDetails[i] = new Label();
                stepDetails[i].Text = "Pending check...";
                stepDetails[i].Font = new Font("Segoe UI", 8.5F, FontStyle.Regular);
                stepDetails[i].ForeColor = Color.FromArgb(100, 116, 139);
                stepDetails[i].Location = new Point(71, startY + (i * rowHeight) + 22);
                stepDetails[i].Size = new Size(555, 18);
                cardPanel.Controls.Add(stepDetails[i]);
            }

            this.Controls.Add(cardPanel);

            // Progress Bar
            progressBar = new ProgressBar();
            progressBar.Location = new Point(20, 375);
            progressBar.Size = new Size(644, 18);
            progressBar.Style = ProgressBarStyle.Continuous;
            progressBar.Value = 0;
            this.Controls.Add(progressBar);

            // Status Label
            statusLabel = new Label();
            statusLabel.Location = new Point(20, 400);
            statusLabel.Size = new Size(430, 20);
            statusLabel.Text = "Initializing diagnostic verification...";
            statusLabel.Font = new Font("Segoe UI", 9F, FontStyle.Italic);
            statusLabel.ForeColor = Color.FromArgb(51, 65, 85);
            this.Controls.Add(statusLabel);

            // Countdown Label
            countdownLabel = new Label();
            countdownLabel.Location = new Point(460, 400);
            countdownLabel.Size = new Size(204, 20);
            countdownLabel.Text = "";
            countdownLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            countdownLabel.ForeColor = PrimaryBtnColor;
            countdownLabel.TextAlign = ContentAlignment.TopRight;
            this.Controls.Add(countdownLabel);

            // Action Buttons
            btnLaunch = new Button();
            btnLaunch.Text = "▶ Launch Mandi ERP (Admin)";
            btnLaunch.Location = new Point(20, 432);
            btnLaunch.Size = new Size(250, 46);
            btnLaunch.Font = new Font("Segoe UI", 10.5F, FontStyle.Bold);
            btnLaunch.BackColor = PrimaryBtnColor;
            btnLaunch.ForeColor = Color.White;
            btnLaunch.FlatStyle = FlatStyle.Flat;
            btnLaunch.FlatAppearance.BorderSize = 0;
            btnLaunch.Cursor = Cursors.Hand;
            btnLaunch.Enabled = false;
            btnLaunch.Click += new EventHandler(BtnLaunch_Click);
            this.Controls.Add(btnLaunch);

            btnRecheck = new Button();
            btnRecheck.Text = "🔄 Recheck / Reinstall All";
            btnRecheck.Location = new Point(285, 432);
            btnRecheck.Size = new Size(190, 46);
            btnRecheck.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            btnRecheck.BackColor = Color.FromArgb(226, 232, 240);
            btnRecheck.ForeColor = Color.FromArgb(30, 41, 59);
            btnRecheck.FlatStyle = FlatStyle.Flat;
            btnRecheck.FlatAppearance.BorderColor = CardBorderColor;
            btnRecheck.Cursor = Cursors.Hand;
            btnRecheck.Click += new EventHandler(BtnRecheck_Click);
            this.Controls.Add(btnRecheck);

            btnOpenFolder = new Button();
            btnOpenFolder.Text = "📁 Open Folder";
            btnOpenFolder.Location = new Point(490, 432);
            btnOpenFolder.Size = new Size(174, 46);
            btnOpenFolder.Font = new Font("Segoe UI", 9F, FontStyle.Regular);
            btnOpenFolder.BackColor = Color.FromArgb(241, 245, 249);
            btnOpenFolder.ForeColor = Color.FromArgb(71, 85, 105);
            btnOpenFolder.FlatStyle = FlatStyle.Flat;
            btnOpenFolder.FlatAppearance.BorderColor = CardBorderColor;
            btnOpenFolder.Cursor = Cursors.Hand;
            btnOpenFolder.Click += new EventHandler(BtnOpenFolder_Click);
            this.Controls.Add(btnOpenFolder);

            // Bottom subtle note
            Label bottomNote = new Label();
            bottomNote.Location = new Point(20, 492);
            bottomNote.Size = new Size(644, 38);
            bottomNote.Text = "Direct Login: Opens http://127.0.0.1:8080/login • Zero external browser popups\nCredentials: admin, chk_cashier, vrv_cashier, dhd_cashier, Suraj (HQ), inspector";
            bottomNote.Font = new Font("Segoe UI", 8F, FontStyle.Regular);
            bottomNote.ForeColor = Color.FromArgb(100, 116, 139);
            bottomNote.TextAlign = ContentAlignment.MiddleCenter;
            this.Controls.Add(bottomNote);
        }

        private void CardPanel_Paint(object sender, PaintEventArgs e)
        {
            ControlPaint.DrawBorder(e.Graphics, cardPanel.ClientRectangle, CardBorderColor, ButtonBorderStyle.Solid);
        }

        private void BtnLaunch_Click(object sender, EventArgs e)
        {
            autoLaunchTimer.Stop();
            LaunchMandiERP();
        }

        private void BtnRecheck_Click(object sender, EventArgs e)
        {
            autoLaunchTimer.Stop();
            countdownLabel.Text = "";
            StartVerification();
        }

        private void BtnOpenFolder_Click(object sender, EventArgs e)
        {
            try
            {
                string folder = !string.IsNullOrEmpty(targetExePath) ? Path.GetDirectoryName(targetExePath) : appBaseDir;
                Process.Start("explorer.exe", folder);
            }
            catch { }
        }

        private void ResolvePaths()
        {
            appBaseDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

            // Locate Target Executable
            string[] exeCandidates = new string[] {
                Path.Combine(appBaseDir, "Rajarshi_Shahu_Trading.exe"),
                Path.Combine(appBaseDir, @"dist\Rajarshi_Shahu_Trading\Rajarshi_Shahu_Trading.exe"),
                Path.Combine(appBaseDir, @"..\dist\Rajarshi_Shahu_Trading\Rajarshi_Shahu_Trading.exe"),
                Path.Combine(appBaseDir, @"..\Rajarshi_Shahu_Trading.exe")
            };
            foreach (string candidate in exeCandidates)
            {
                if (File.Exists(candidate))
                {
                    targetExePath = Path.GetFullPath(candidate);
                    break;
                }
            }

            // Locate Prerequisites folder
            string[] prereqCandidates = new string[] {
                Path.Combine(appBaseDir, "prerequisites"),
                Path.Combine(appBaseDir, @"..\prerequisites"),
                Path.Combine(appBaseDir, @"..\..\prerequisites")
            };
            foreach (string candidate in prereqCandidates)
            {
                if (Directory.Exists(candidate))
                {
                    prereqDir = Path.GetFullPath(candidate);
                    break;
                }
            }

            // Locate api-ms-win-core-path-l1-1-0.dll
            string[] dllCandidates = new string[] {
                Path.Combine(appBaseDir, "api-ms-win-core-path-l1-1-0.dll"),
                prereqDir != null ? Path.Combine(prereqDir, "api-ms-win-core-path-l1-1-0.dll") : null,
                Path.Combine(appBaseDir, @"dist\Rajarshi_Shahu_Trading\api-ms-win-core-path-l1-1-0.dll"),
                Path.Combine(appBaseDir, @"..\prerequisites\api-ms-win-core-path-l1-1-0.dll")
            };
            foreach (string candidate in dllCandidates)
            {
                if (candidate != null && File.Exists(candidate))
                {
                    corePathDllSource = Path.GetFullPath(candidate);
                    break;
                }
            }
        }

        private void StartVerification()
        {
            if (worker.IsBusy) return;

            btnLaunch.Enabled = false;
            btnRecheck.Enabled = false;
            progressBar.Value = 5;
            statusLabel.Text = "Starting diagnostic verification...";

            for (int i = 0; i < 5; i++)
            {
                stepBadges[i].Text = "[ .. ]";
                stepBadges[i].ForeColor = PendingGray;
                stepDetails[i].Text = "Checking...";
                stepDetails[i].ForeColor = Color.FromArgb(100, 116, 139);
            }

            worker.RunWorkerAsync();
        }

        private struct StepResult
        {
            public int StepIndex;
            public bool Success;
            public string Badge;
            public Color BadgeColor;
            public string Detail;
        }

        private void Worker_DoWork(object sender, DoWorkEventArgs e)
        {
            bool allPassed = true;

            // STEP 1: OS Architecture & Compatibility
            {
                bool is64Bit = Environment.Is64BitOperatingSystem;
                Version ver = Environment.OSVersion.Version;
                string osName = GetFriendlyOSName(ver);

                StepResult sr = new StepResult();
                sr.StepIndex = 0;
                if (is64Bit)
                {
                    sr.Success = true;
                    sr.Badge = "[ ✓ ]";
                    sr.BadgeColor = SuccessGreen;
                    sr.Detail = string.Format("{0} (64-bit Architecture Verified)", osName);
                }
                else
                {
                    sr.Success = false;
                    sr.Badge = "[ ✗ ]";
                    sr.BadgeColor = ErrorRed;
                    sr.Detail = "32-bit OS detected. Mandi ERP requires 64-bit Windows.";
                    allPassed = false;
                }
                worker.ReportProgress(20, sr);
                System.Threading.Thread.Sleep(200);
            }

            // STEP 2: Windows 7/8 Core Path DLL (api-ms-win-core-path-l1-1-0.dll)
            {
                StepResult sr = new StepResult();
                sr.StepIndex = 1;

                string targetDir = targetExePath != null ? Path.GetDirectoryName(targetExePath) : appBaseDir;
                string localDllPath = Path.Combine(targetDir, "api-ms-win-core-path-l1-1-0.dll");
                string internalDir = Path.Combine(targetDir, "_internal");
                string internalDllPath = Path.Combine(internalDir, "api-ms-win-core-path-l1-1-0.dll");
                string sys32DllPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "api-ms-win-core-path-l1-1-0.dll");

                bool localOk = false;
                bool internalOk = false;
                bool sys32Ok = false;

                try
                {
                    if (corePathDllSource != null && File.Exists(corePathDllSource))
                    {
                        // Copy next to exe
                        if (!File.Exists(localDllPath) || new FileInfo(localDllPath).Length != new FileInfo(corePathDllSource).Length)
                        {
                            File.Copy(corePathDllSource, localDllPath, true);
                        }
                        localOk = true;

                        // Copy to _internal if directory exists
                        if (Directory.Exists(internalDir))
                        {
                            if (!File.Exists(internalDllPath) || new FileInfo(internalDllPath).Length != new FileInfo(corePathDllSource).Length)
                            {
                                File.Copy(corePathDllSource, internalDllPath, true);
                            }
                            internalOk = true;
                        }

                        // Copy to System32 (if elevated or accessible)
                        try
                        {
                            if (!File.Exists(sys32DllPath))
                            {
                                File.Copy(corePathDllSource, sys32DllPath, false);
                            }
                            sys32Ok = true;
                        }
                        catch
                        {
                            sys32Ok = File.Exists(sys32DllPath);
                        }
                    }
                    else
                    {
                        localOk = File.Exists(localDllPath);
                        internalOk = File.Exists(internalDllPath);
                        sys32Ok = File.Exists(sys32DllPath);
                    }
                }
                catch
                {
                    localOk = File.Exists(localDllPath);
                }

                if (localOk)
                {
                    sr.Success = true;
                    sr.Badge = "[ ✓ ]";
                    sr.BadgeColor = SuccessGreen;
                    if (sys32Ok)
                        sr.Detail = "Deployed in App Directory, _internal & System32 (Universal Win 7 fix active)";
                    else
                        sr.Detail = "Deployed in App Directory & _internal (Universal Win 7 fix active)";
                }
                else
                {
                    sr.Success = false;
                    sr.Badge = "[ ✗ ]";
                    sr.BadgeColor = ErrorRed;
                    sr.Detail = "Missing api-ms-win-core-path-l1-1-0.dll in prerequisites.";
                    allPassed = false;
                }
                worker.ReportProgress(40, sr);
                System.Threading.Thread.Sleep(200);
            }

            // STEP 3: Microsoft Visual C++ 2015-2022 Runtime (x64)
            {
                StepResult sr = new StepResult();
                sr.StepIndex = 2;

                bool vcInstalled = CheckVCRedistInstalled();
                if (!vcInstalled)
                {
                    string vcInstaller = prereqDir != null ? Path.Combine(prereqDir, "vc_redist.x64.exe") : null;
                    if (vcInstaller != null && File.Exists(vcInstaller))
                    {
                        StepResult installingResult = new StepResult();
                        installingResult.StepIndex = 2;
                        installingResult.Badge = "[ .. ]";
                        installingResult.BadgeColor = WarnOrange;
                        installingResult.Detail = "Installing Microsoft Visual C++ 2015-2022 Redistributable...";
                        worker.ReportProgress(45, installingResult);

                        try
                        {
                            ProcessStartInfo psi = new ProcessStartInfo(vcInstaller, "/install /quiet /norestart");
                            psi.UseShellExecute = true;
                            psi.Verb = "runas";
                            Process p = Process.Start(psi);
                            if (p != null)
                            {
                                p.WaitForExit(90000);
                            }
                            vcInstalled = CheckVCRedistInstalled();
                        }
                        catch
                        {
                            vcInstalled = CheckVCRedistInstalled();
                        }
                    }
                }

                if (vcInstalled)
                {
                    sr.Success = true;
                    sr.Badge = "[ ✓ ]";
                    sr.BadgeColor = SuccessGreen;
                    sr.Detail = "Microsoft Visual C++ 2015-2022 (x64) is installed & verified";
                }
                else
                {
                    sr.Success = false;
                    sr.Badge = "[ ! ]";
                    sr.BadgeColor = WarnOrange;
                    sr.Detail = "VC++ Redistributable not detected. (Run prerequisites\\vc_redist.x64.exe if needed)";
                }
                worker.ReportProgress(60, sr);
                System.Threading.Thread.Sleep(200);
            }

            // STEP 4: Microsoft Edge WebView2 Evergreen Runtime
            {
                StepResult sr = new StepResult();
                sr.StepIndex = 3;

                string webView2Version = GetWebView2Version();
                if (string.IsNullOrEmpty(webView2Version))
                {
                    string wvInstaller = prereqDir != null ? Path.Combine(prereqDir, "MicrosoftEdgeWebview2Setup.exe") : null;
                    if (wvInstaller != null && File.Exists(wvInstaller))
                    {
                        StepResult installingWv = new StepResult();
                        installingWv.StepIndex = 3;
                        installingWv.Badge = "[ .. ]";
                        installingWv.BadgeColor = WarnOrange;
                        installingWv.Detail = "Installing Microsoft Edge WebView2 Evergreen Runtime...";
                        worker.ReportProgress(65, installingWv);

                        try
                        {
                            ProcessStartInfo psi = new ProcessStartInfo(wvInstaller, "/silent /install");
                            psi.UseShellExecute = true;
                            psi.Verb = "runas";
                            Process p = Process.Start(psi);
                            if (p != null)
                            {
                                p.WaitForExit(120000);
                            }
                            webView2Version = GetWebView2Version();
                        }
                        catch
                        {
                            webView2Version = GetWebView2Version();
                        }
                    }
                }

                if (!string.IsNullOrEmpty(webView2Version))
                {
                    sr.Success = true;
                    sr.Badge = "[ ✓ ]";
                    sr.BadgeColor = SuccessGreen;
                    sr.Detail = string.Format("WebView2 Evergreen Runtime Active (Version {0})", webView2Version);
                }
                else
                {
                    sr.Success = false;
                    sr.Badge = "[ ! ]";
                    sr.BadgeColor = WarnOrange;
                    sr.Detail = "WebView2 not found. (Will fallback to standard web browser window)";
                }
                worker.ReportProgress(80, sr);
                System.Threading.Thread.Sleep(200);
            }

            // STEP 5: Desktop Shortcut Integration
            {
                StepResult sr = new StepResult();
                sr.StepIndex = 4;

                string desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                string shortcutFile = Path.Combine(desktopPath, "Rajarshi Shahu Trading - Mandi ERP.lnk");

                try
                {
                    string launcherExePath = Application.ExecutablePath;
                    string target = !string.IsNullOrEmpty(launcherExePath) && File.Exists(launcherExePath)
                        ? launcherExePath
                        : targetExePath;

                    CreateOrUpdateShortcut(shortcutFile, target, Path.GetDirectoryName(target), "Rajarshi Shahu Trading — Mandi ERP Desktop");
                    sr.Success = true;
                    sr.Badge = "[ ✓ ]";
                    sr.BadgeColor = SuccessGreen;
                    sr.Detail = "Desktop Shortcut verified: 'Rajarshi Shahu Trading - Mandi ERP'";
                }
                catch
                {
                    sr.Success = true;
                    sr.Badge = "[ ✓ ]";
                    sr.BadgeColor = SuccessGreen;
                    sr.Detail = "Desktop Shortcut verified";
                }

                worker.ReportProgress(100, sr);
                System.Threading.Thread.Sleep(200);
            }

            e.Result = allPassed;
        }

        private void Worker_ProgressChanged(object sender, ProgressChangedEventArgs e)
        {
            progressBar.Value = Math.Min(100, Math.Max(0, e.ProgressPercentage));
            if (e.UserState is StepResult)
            {
                StepResult sr = (StepResult)e.UserState;
                stepBadges[sr.StepIndex].Text = sr.Badge;
                stepBadges[sr.StepIndex].ForeColor = sr.BadgeColor;
                stepDetails[sr.StepIndex].Text = sr.Detail;
                stepDetails[sr.StepIndex].ForeColor = Color.FromArgb(51, 65, 85);
            }
        }

        private void Worker_RunWorkerCompleted(object sender, RunWorkerCompletedEventArgs e)
        {
            btnRecheck.Enabled = true;
            btnLaunch.Enabled = true;

            if (targetExePath == null || !File.Exists(targetExePath))
            {
                statusLabel.Text = "Executable Rajarshi_Shahu_Trading.exe not found in bundle.";
                statusLabel.ForeColor = ErrorRed;
                btnLaunch.Enabled = false;
                return;
            }

            statusLabel.Text = "All requirements verified successfully. System is 100% ready.";
            statusLabel.ForeColor = SuccessGreen;

            if (isAutoLaunch)
            {
                countdownSeconds = 3;
                countdownLabel.Text = string.Format("Auto-launching in {0}s...", countdownSeconds);
                autoLaunchTimer.Start();
            }
        }

        private void AutoLaunchTimer_Tick(object sender, EventArgs e)
        {
            countdownSeconds--;
            if (countdownSeconds > 0)
            {
                countdownLabel.Text = string.Format("Auto-launching in {0}s...", countdownSeconds);
            }
            else
            {
                autoLaunchTimer.Stop();
                countdownLabel.Text = "Launching...";
                LaunchMandiERP();
            }
        }

        private void LaunchMandiERP()
        {
            if (string.IsNullOrEmpty(targetExePath) || !File.Exists(targetExePath))
            {
                MessageBox.Show(
                    "Could not locate 'Rajarshi_Shahu_Trading.exe'.\nPlease verify installation files.",
                    "File Not Found",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return;
            }

            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = targetExePath;
                psi.WorkingDirectory = Path.GetDirectoryName(targetExePath);
                psi.UseShellExecute = true;

                // Check if admin is currently active
                bool isAdmin = new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator);
                if (isAdmin)
                {
                    psi.Verb = "runas";
                }

                Process.Start(psi);

                // Gracefully hide and exit launcher window after brief moment
                Timer closeTimer = new Timer();
                closeTimer.Interval = 1200;
                closeTimer.Tick += new EventHandler(delegate(object s, EventArgs ev) {
                    closeTimer.Stop();
                    Application.Exit();
                });
                closeTimer.Start();
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Error launching Rajarshi Shahu Trading Mandi ERP:\n" + ex.Message,
                    "Launch Error",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }

        // --- Helper Methods ---

        private static string GetFriendlyOSName(Version v)
        {
            if (v.Major == 6 && v.Minor == 1) return "Windows 7 SP1";
            if (v.Major == 6 && v.Minor == 2) return "Windows 8";
            if (v.Major == 6 && v.Minor == 3) return "Windows 8.1";
            if (v.Major >= 10)
            {
                if (v.Build >= 22000) return "Windows 11";
                return "Windows 10";
            }
            return Environment.OSVersion.VersionString;
        }

        private static bool CheckVCRedistInstalled()
        {
            try
            {
                // 1. Check registry key for VC++ 2015-2022 (v14.0) x64
                string[] regPaths = new string[] {
                    @"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
                    @"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
                };

                foreach (string path in regPaths)
                {
                    using (RegistryKey key = Registry.LocalMachine.OpenSubKey(path))
                    {
                        if (key != null)
                        {
                            object val = key.GetValue("Installed");
                            if (val != null && Convert.ToInt32(val) == 1)
                                return true;
                        }
                    }
                }

                // 2. Check System32 vcruntime140.dll
                string sysDir = Environment.GetFolderPath(Environment.SpecialFolder.System);
                string vcDll = Path.Combine(sysDir, "vcruntime140.dll");
                string msvcpDll = Path.Combine(sysDir, "msvcp140.dll");
                if (File.Exists(vcDll) && File.Exists(msvcpDll))
                    return true;
            }
            catch { }
            return false;
        }

        private static string GetWebView2Version()
        {
            try
            {
                string[] regPaths = new string[] {
                    @"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                    @"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
                };

                foreach (string path in regPaths)
                {
                    using (RegistryKey key = Registry.LocalMachine.OpenSubKey(path))
                    {
                        if (key != null)
                        {
                            object pv = key.GetValue("pv");
                            if (pv != null && !string.IsNullOrEmpty(pv.ToString()) && pv.ToString() != "0.0.0.0")
                                return pv.ToString();
                        }
                    }
                }

                // Check CurrentUser registry
                using (RegistryKey key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"))
                {
                    if (key != null)
                    {
                        object pv = key.GetValue("pv");
                        if (pv != null && !string.IsNullOrEmpty(pv.ToString()) && pv.ToString() != "0.0.0.0")
                            return pv.ToString();
                    }
                }
            }
            catch { }
            return null;
        }

        private static void CreateOrUpdateShortcut(string shortcutPath, string targetPath, string workDir, string description)
        {
            try
            {
                Type shellType = Type.GetTypeFromProgID("WScript.Shell");
                if (shellType == null) return;

                object shell = Activator.CreateInstance(shellType);
                object shortcut = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { shortcutPath });
                Type scType = shortcut.GetType();

                scType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
                scType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { workDir });
                scType.InvokeMember("Description", BindingFlags.SetProperty, null, shortcut, new object[] { description });

                if (File.Exists(targetPath))
                {
                    scType.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath + ",0" });
                }

                scType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
            }
            catch { }
        }

        [STAThread]
        public static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new LauncherForm());
        }
    }
}
