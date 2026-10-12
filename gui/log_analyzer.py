"""
MelkorS PS5 - Automated Crash & Log Diagnostic Engine
"""

import os
import re
from typing import Dict, Any, List

class LogAnalyzer:
    @staticmethod
    def analyze_log_file(log_path: str) -> Dict[str, Any]:
        if not os.path.exists(log_path):
            return {"status": "error", "message": f"Log dosyası bulunamadı: {log_path}"}

        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        return LogAnalyzer.analyze_lines(lines)

    @staticmethod
    def analyze_lines(lines: List[str]) -> Dict[str, Any]:
        report = {
            "crashed": False,
            "root_cause": "Bilinmiyor",
            "category": "None",
            "failing_symbol": None,
            "failing_address": None,
            "recommended_action": "Detaylı log incelemesi gerekiyor.",
            "suspicious_lines": []
        }

        # Regex patterns for common PlayStation 5 / MelkorS Core translation layer failure modes
        patterns = {
            "unimplemented_syscall": re.compile(r"(?:unimplemented|unknown)\s+(?:sys(?:call)?|function)\s*[:=]?\s*(\w+)", re.IGNORECASE),
            "missing_symbol": re.compile(r"(?:undefined|missing|unresolved)\s+symbol\s*[:=]?\s*([a-zA-Z0-9_]+)", re.IGNORECASE),
            "vulkan_error": re.compile(r"(VK_ERROR_\w+|Vulkan\s+validation\s+error|failed to create \w+ pipeline)", re.IGNORECASE),
            "access_violation": re.compile(r"(access violation|segmentation fault|segfault|exception 0x[0-9a-fA-F]+)\s+(?:at\s+)?(0x[0-9a-fA-F]+)?", re.IGNORECASE),
            "missing_module": re.compile(r"(?:failed to load|cannot open module|missing library)\s*[:=]?\s*([\w\.\-]+(?:\.sprx|\.dll|\.prx))", re.IGNORECASE),
            "encrypted_elf": re.compile(r"(invalid elf magic|encrypted self|SCE\x00|not a valid ELF)", re.IGNORECASE)
        }

        for idx, line in enumerate(lines):
            line_str = line.strip()

            # Check unimplemented syscall
            m = patterns["unimplemented_syscall"].search(line_str)
            if m:
                report["crashed"] = True
                report["category"] = "UNIMPLEMENTED_SYSCALL"
                report["failing_symbol"] = m.group(1)
                report["root_cause"] = f"Eksik PlayStation 5 Sistem Çağrısı (Syscall): {m.group(1)}"
                report["recommended_action"] = (
                    f"Çekirdek C++ kodunda '{m.group(1)}' için sahte/başarılı (dummy return 0) "
                    f"bir stub fonksiyonu tanımlanmalı veya libSce modülüne eklenmeli."
                )
                report["suspicious_lines"].append(f"[Satır {idx+1}] {line_str}")
                continue

            # Check missing symbol in SPRX
            m = patterns["missing_symbol"].search(line_str)
            if m:
                report["crashed"] = True
                report["category"] = "MISSING_SYMBOL"
                report["failing_symbol"] = m.group(1)
                report["root_cause"] = f"SPRX kütüphanesinde eksik fonksiyon: {m.group(1)}"
                report["recommended_action"] = f"fakelib modülünde veya C++ export tablosunda '{m.group(1)}' sembolü implemente edilmeli."
                report["suspicious_lines"].append(f"[Satır {idx+1}] {line_str}")
                continue

            # Check Vulkan error
            m = patterns["vulkan_error"].search(line_str)
            if m:
                report["crashed"] = True
                report["category"] = "VULKAN_GPU_ERROR"
                report["failing_symbol"] = m.group(1)
                report["root_cause"] = f"Vulkan Grafik / AGC Pipeline Hatası: {m.group(1)}"
                report["recommended_action"] = (
                    "Grafik sürücüsü SPIR-V shader komutunu derleyemedi. "
                    "Vulkan Pipeline Cache temizlenmeli veya compute shader çevirici yamalanmalı."
                )
                report["suspicious_lines"].append(f"[Satır {idx+1}] {line_str}")
                continue

            # Check access violation / crash
            m = patterns["access_violation"].search(line_str)
            if m:
                report["crashed"] = True
                report["category"] = "MEMORY_CRASH"
                addr = m.group(2) if len(m.groups()) > 1 else "Bilinmiyor"
                report["failing_address"] = addr
                report["root_cause"] = f"Bellek Erişim Hatası (Segmentation Fault): {addr}"
                report["recommended_action"] = "Oyunun tahsis ettiği sanal bellek (VirtualAlloc / Direct Memory) sınırları kontrol edilmeli."
                report["suspicious_lines"].append(f"[Satır {idx+1}] {line_str}")
                continue

            # Check missing SPRX module
            m = patterns["missing_module"].search(line_str)
            if m:
                report["crashed"] = True
                report["category"] = "MISSING_SPRX_MODULE"
                report["failing_symbol"] = m.group(1)
                report["root_cause"] = f"Eksik PlayStation Sistem Modülü: {m.group(1)}"
                report["recommended_action"] = f"'{m.group(1)}' modülü oyunun 'fakelib' klasörüne eklenmeli."
                report["suspicious_lines"].append(f"[Satır {idx+1}] {line_str}")
                continue

            # Check Encrypted ELF
            m = patterns["encrypted_elf"].search(line_str)
            if m:
                report["crashed"] = True
                report["category"] = "ENCRYPTED_BINARY"
                report["root_cause"] = "Oyun eboot.bin dosyası şifreli (SELF) formatta."
                report["recommended_action"] = "Oyun dosyası şifresiz (decrypted ELF) formata dönüştürülmeli."
                report["suspicious_lines"].append(f"[Satır {idx+1}] {line_str}")
                continue

        return report
