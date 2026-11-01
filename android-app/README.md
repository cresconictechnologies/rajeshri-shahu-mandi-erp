# Mandi QC Inspector — Native Android Application
**Rajeshri Shahu Market Committee ERP v2.6**
*Package: `com.rajeshri.mandierp.inspector`*

---

## Overview

The **Mandi QC Inspector Android App** is a native Android application built for APMC Mandi Quality Inspectors. It connects directly to the local yard weighbridge server (or cloud deployment) and provides full hardware camera integration for:
1. Digital 7-Segment Moisture Meter Screen Optical Recognition (OCR).
2. Grain Sample Photography for 8-Factor Refraction Assaying.
3. Tamper-Proof Digital QC Ticket issuance.

---

## Key Native Features

- **Hardware Camera Bridge:** Uses Android `FileProvider` and `WebChromeClient.onShowFileChooser` to trigger real-time camera captures with autofocus and LED torch support.
- **Yard Server IP Selector:** Includes a dedicated Server Configuration Dialog allowing inspectors to connect to local yard Wi-Fi servers (e.g., `http://192.168.1.10:8080/inspector/portal`) or cloud endpoints.
- **Offline Resilience:** Swipe-to-refresh (`SwipeRefreshLayout`) and clear offline retry screens with connectivity diagnostics.
- **Role Isolation:** Inspectors log in with their yard-specific credentials provisioned by the Accountant; branch hopping is blocked.

---

## Build & Installation Instructions

### Option 1: Open in Android Studio (Recommended)
1. Launch **Android Studio** (Hedgehog, Iguana, Jellyfish, or newer).
2. Select **Open** and choose the `commoditi software/android-app` folder.
3. Allow Gradle to sync.
4. Click **Build > Build Bundle(s) / APK(s) > Build APK(s)**.
5. The signed debug/release APK will be generated at `app/build/outputs/apk/debug/app-debug.apk`.
6. Transfer the `.apk` to any Android phone via USB, WhatsApp, or local network.

### Option 2: Command Line (Gradle Wrapper)
```bash
cd "commoditi software/android-app"
gradle assembleDebug
```
or on Windows with Gradle installed:
```powershell
gradle assembleRelease
```
