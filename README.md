# 👁️ MelkorS PS5 - Next-Gen PlayStation 5 & PS4 Control Center

<p align="center">
  <img src="gui/melkors_icon.ico" alt="MelkorS PS5 Logo" width="128" height="128" />
  <br>
  <b>Modern, Hybrid Dual-Core PlayStation 5 & PlayStation 4 PC Runtime & Emulator Manager</b><br>
  <i>Native Vulkan 1.3 AGC Pipeline • x86-64 Prospero Translation Layer • 1-Click Ultra Performance</i>
</p>

<p align="center">
  <a href="#english">English</a> •
  <a href="#türkçe">Türkçe</a>
</p>

---

<a name="english"></a>
# English

## 🌟 Overview

**MelkorS PS5** is a high-performance, modern PlayStation runtime manager designed for PC. Built with an intelligent hybrid dual-core engine, it seamlessly runs next-generation **PlayStation 5 (PS5)** titles as well as legacy **PlayStation 4 (PS4)** titles from a single unified control center.

### 🚀 Key Features

- **Smart Dual-Core Routing:**
  - **MelkorS PS5 Core:** Tailored for next-gen PS5 ELF binaries with optimized AGC Vulkan pipeline.
  - **MelkorS PS4 Core:** Full backwards compatibility engine for PS4 ELF and PRX modules.
  - Automatically selects and launches the correct core engine based on Title ID (`PPSA...` vs `CUSA...`).
- **Silent Low-Overhead I/O:**
  - Eliminates stdout bottlenecks by keeping guest logging minimal and silent, preventing audio buffer underruns (crackling) and CPU thread stalls.
- **⚡ 1-Click Ultra Performance Profile:**
  - One-click preset applying 720p scaling, `Immediate` presentation mode (V-Sync off, zero queue latency), aggressive SPIR-V shader compiler optimizations, and GPU readback bypass.
- **Advanced Gamepad Integration:**
  - Plug-and-play support for Sony PlayStation DualSense and all XInput (Xbox / generic) controllers.
  - Adjustable stick deadzone and haptic vibration testing.
- **Seamless Game Window Integration:**
  - Native Windows game title bar integration showing live status and built-in hotkeys:
    - **`[F1]`** — Safely exit game and return to Launcher Library
    - **`[F10]`** — Real-time FPS Counter
    - **`[F11]`** — Toggle Fullscreen / Windowed Mode

---

## 🎮 Verified Working Games

The following titles have been tested and verified to boot and run on MelkorS PS5:

| Game Title | Title ID | Platform | Core Engine | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Harmony's Odyssey** | `PPSA16827` | **PS5** | MelkorS PS5 Core | ✅ Playable |
| **Enotria: The Last Song** | `PPSA20515` | **PS5** | MelkorS PS5 Core | 🟡 Main Menu |
| **God of War: Sons of Sparta** | *Community Dump* | **PS5 / PS4** | MelkorS Core | ✅ Playable |
| **Pocket Bravery** | `CUSA41703` | **PS4** | MelkorS PS4 Core | ✅ Playable |

*(More titles will be added as community compatibility tests continue.)*

---

## 📥 Getting Started & Usage Guide

1. **Download & Extract:**
   - Grab the latest `MelkorSPS5-v1.0.0-Windows-x64.zip` release from the [Releases](https://github.com/spiritkiller/MelkorsEmuPS5/releases) tab.
   - Extract the contents to any folder on your computer.
2. **Add Your Games:**
   - Place your decrypted PS5 or PS4 game folders (or `.pkg` packages) into the `games/` folder:
     - Example: `games/HarmonysOdyssey-PPSA16827/eboot.bin`
     - Example: `games/PocketBravery-CUSA41703/eboot.bin`
     - Example: `games/GodOfWarSonsOfSparta/eboot.bin`
3. **Launch:**
   - Run `MelkorSPS5.exe`.
   - Your games will automatically populate in the **🎮 Game Library** tab.
   - Select your game and click **▶ LAUNCH GAME**.
4. **In-Game Controls:**
   - Press **`F1`** at any time to smoothly terminate the game and bring the control center back to focus.

---

## ⚙️ Performance Tips

- For maximum FPS, go to **⚙️ Graphics & Engine** and click **⚡ 1-Click Apply Ultra Performance Profile**.
- Ensure you have the latest graphics drivers installed with Vulkan 1.3 support.

---

## 💖 Support & Contributions (Donations)

MelkorS PS5 is an independent, community-driven project. If you would like to support ongoing development, new game compatibility patches, and engine optimizations, donations are gratefully accepted via cryptocurrency:

* **Bitcoin (BTC):**
  `15nzhjDB6meaGNUtiTvZSKHHEsHVzZ1T6S`

* **Tether (USDT):**
  - **TRC20:** `TV7GLKkrkN94dYwtaxzoubnygJvz9BRCsG`
  - **BEP20 (BSC):** `0x542bc68515a34e15610cef9322464c4bcced6f75`
  - **ERC20 (ETH):** `0x542bc68515a34e15610cef9322464c4bcced6f75`

*(Thank you for supporting open emulation development!)*

---

<a name="türkçe"></a>
# Türkçe

## 🌟 Genel Bakış

**MelkorS PS5**, PC için geliştirilmiş hibrit çift çekirdekli bir PlayStation emülatör yürütücüsüdür. Hem yeni nesil **PlayStation 5 (PS5)** başlıklarını hem de geriye dönük uyumlulukla **PlayStation 4 (PS4)** oyunlarını tek bir modern arayüzden çalıştırır.

### 🚀 Temel Özellikler

- **Akıllı Çift Çekirdek Yönlendirmesi:** `Title ID` değerine göre (`PPSA...` veya `CUSA...`) PS5 veya PS4 motoruna otomatik yönlendirme.
- **Sessiz I/O ve Kesintisiz Ses:** Misafir bellek tahsis loglarını sessize alarak ses cızırtısını ve FPS düşüşünü önler.
- **⚡ 1-Tıkla Ultra Performans Profili:** 720p çözünürlük, V-Sync kapalı `Immediate` sunum ve agresif shader optimizasyonunu tek tıkla uygular.
- **DualSense & XInput Desteği:** Titreşim ve analog ölü bölge ayarlı tak-çalıştır oyun kolu desteği.
- **Oyun İçi Kısayollar:** `[F1]` Ana ekrana dönüş, `[F10]` FPS sayacı, `[F11]` Tam ekran.

### 🎮 Doğrulanmış Çalışan Oyunlar

- **Harmony's Odyssey** (`PPSA16827` - PS5) — ✅ Çalışıyor
- **Enotria: The Last Song** (`PPSA20515` - PS5) — 🟡 Ana Menü / Giriş (Main Menu)
- **God of War: Sons of Sparta** — ✅ Çalışıyor
- **Pocket Bravery** (`CUSA41703` - PS4) — ✅ Çalışıyor

### 💖 Bağış ve Destek

Geliştirme sürecine destek olmak isterseniz:
* **Bitcoin (BTC):**
  `15nzhjDB6meaGNUtiTvZSKHHEsHVzZ1T6S`
* **Tether (USDT):**
  - **TRC20:** `TV7GLKkrkN94dYwtaxzoubnygJvz9BRCsG`
  - **BEP20 (BSC):** `0x542bc68515a34e15610cef9322464c4bcced6f75`
  - **ERC20 (ETH):** `0x542bc68515a34e15610cef9322464c4bcced6f75`

---

## 📜 Disclaimer / Yasal Uyarı

*MelkorS PS5 is an independent educational research project and is not affiliated with, endorsed by, or sponsored by Sony Interactive Entertainment Inc. PlayStation, PS5, and PS4 are registered trademarks of Sony Interactive Entertainment Inc.*
