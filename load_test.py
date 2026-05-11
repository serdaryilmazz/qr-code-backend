"""
🔥 QR Code Backend - Load Test / Stress Test Script
=====================================================
200 eşzamanlı kullanıcı simülasyonu ile backend performans testi.

Test edilen metrikler:
  - Response time (min, max, avg, p50, p95, p99)
  - Başarılı / Başarısız istek sayısı
  - Timeout oranı
  - Veritabanı yazma kaybı kontrolü
  - Throughput (istek/saniye)

Kullanım:
  pip install aiohttp
  python load_test.py
"""

import asyncio
import aiohttp
import time
import random
import statistics
import json
from dataclasses import dataclass, field
from typing import Optional


BASE_URL = "http://xtnwrsn6hsq27ix98oeekon1.68.183.217.1.sslip.io/" 
CONCURRENT_USERS = 200              # Eşzamanlı kullanıcı sayısı
TIMEOUT_SECONDS = 30                # İstek başına timeout süresi
RAMP_UP_SECONDS = 2                 # Kullanıcıların kademeli başlama süresi


# Soru cevap şablonları
ANSWER_TEMPLATES = {
    1: lambda: str(random.randint(18, 65)),                                             # Yaş
    2: lambda: random.choice(["Erkek", "Kadın"]),                                       # Cinsiyet
    3: lambda: random.choice([
        "Bilgisayar Mühendisliği", "Yazılım Mühendisliği",
        "Elektrik Elektronik Mühendisliği", "Diğer"
    ]),                                                                                  # Bölüm
    4: lambda: random.choice([
        "Yapay Zeka / Makine Öğrenmesi", "Web / Mobil Geliştirme",
        "Siber Güvenlik", "Veri Bilimi", "Diğer"
    ]),                                                                                  # İlgi alanı
}


# Sonuç veri sınıfı
@dataclass
class RequestResult:
    user_id: int
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    success: bool = False
    error: Optional[str] = None
    timed_out: bool = False


@dataclass
class TestReport:
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    timed_out: int = 0
    response_times: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    total_duration: float = 0.0
    answers_before: int = 0
    answers_after: int = 0


# Yardımcı fonksiyonlar
def generate_answers() -> dict:
    """Rastgele anket cevapları üretir."""
    answers = []
    for qid, generator in ANSWER_TEMPLATES.items():
        answers.append({
            "question_id": qid,
            "answer_text": generator()
        })
    return {"answers": answers}


def print_header(text: str):
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {text}")
    print(f"{'=' * width}")


def print_bar(label: str, value: float, max_value: float, width: int = 30):
    """Basit ASCII bar chart."""
    filled = int((value / max_value) * width) if max_value > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    print(f"  {label:<12} {bar} {value:.1f}ms")


# Ana test fonksiyonları
async def get_answer_count(session: aiohttp.ClientSession) -> int:
    """Veritabanındaki mevcut cevap sayısını döndürür."""
    try:
        async with session.get(f"{BASE_URL}/api/answers", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json()
            return len(data)
    except Exception:
        return -1


async def check_health(session: aiohttp.ClientSession) -> bool:
    """Backend'in ayakta olup olmadığını kontrol eder."""
    try:
        async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
            return resp.status == 200
    except Exception:
        return False


async def simulate_user(session: aiohttp.ClientSession, user_id: int) -> RequestResult:
    """Tek bir kullanıcının anket gönderimini simüle eder."""
    result = RequestResult(user_id=user_id)
    payload = generate_answers()

    start = time.perf_counter()
    try:
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with session.post(
            f"{BASE_URL}/api/submit",
            json=payload,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        ) as resp:
            elapsed = (time.perf_counter() - start) * 1000  # ms
            result.status_code = resp.status
            result.response_time_ms = elapsed
            result.success = resp.status == 200

            if not result.success:
                body = await resp.text()
                result.error = f"HTTP {resp.status}: {body[:200]}"

    except asyncio.TimeoutError:
        elapsed = (time.perf_counter() - start) * 1000
        result.response_time_ms = elapsed
        result.timed_out = True
        result.error = f"TIMEOUT ({TIMEOUT_SECONDS}s)"

    except aiohttp.ClientConnectorError as e:
        elapsed = (time.perf_counter() - start) * 1000
        result.response_time_ms = elapsed
        result.error = f"CONNECTION ERROR: {str(e)[:200]}"

    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        result.response_time_ms = elapsed
        result.error = f"{type(e).__name__}: {str(e)[:200]}"

    return result


async def run_load_test():
    """Ana load test fonksiyonu."""

    print_header("🔥 QR Code Backend - Load Test")
    print(f"  Hedef:              {BASE_URL}")
    print(f"  Eşzamanlı kullanıcı: {CONCURRENT_USERS}")
    print(f"  Timeout:            {TIMEOUT_SECONDS}s")
    print(f"  Ramp-up:            {RAMP_UP_SECONDS}s")

    # ── 1) Health check ──────────────────────────────
    print_header("1️⃣  Health Check")
    connector = aiohttp.TCPConnector(limit=0, limit_per_host=0)
    async with aiohttp.ClientSession(connector=connector) as session:

        healthy = await check_health(session)
        if not healthy:
            print("  ❌ Backend ulaşılabilir değil! URL'i kontrol et.")
            print(f"     → {BASE_URL}/health")
            return
        print("  ✅ Backend ayakta ve sağlıklı.")

        # ── 2) Test öncesi cevap sayısı ──────────────
        print_header("2️⃣  Test Öncesi Durum")
        answers_before = await get_answer_count(session)
        if answers_before >= 0:
            print(f"  📊 Mevcut cevap sayısı: {answers_before}")
        else:
            print("  ⚠️  Cevap sayısı alınamadı, yine de devam ediliyor.")
            answers_before = 0

        # ── 3) LOAD TEST ────────────────────────────
        print_header("3️⃣  Load Test Başlıyor!")
        print(f"  → {CONCURRENT_USERS} kullanıcı aynı anda istek gönderiyor...")
        print()

        report = TestReport(answers_before=answers_before)
        results: list[RequestResult] = []

        # Kademeli başlatma (ramp-up)
        delay_per_user = RAMP_UP_SECONDS / CONCURRENT_USERS
        tasks = []

        overall_start = time.perf_counter()

        for i in range(CONCURRENT_USERS):
            task = asyncio.create_task(simulate_user(session, i + 1))
            tasks.append(task)
            if delay_per_user > 0:
                await asyncio.sleep(delay_per_user)

        results = await asyncio.gather(*tasks)
        overall_end = time.perf_counter()
        report.total_duration = overall_end - overall_start

        # ── 4) Sonuçları analiz et ───────────────────
        for r in results:
            report.total_requests += 1
            if r.success:
                report.successful += 1
            else:
                report.failed += 1
                if r.error:
                    report.errors.append(f"User #{r.user_id}: {r.error}")
            if r.timed_out:
                report.timed_out += 1
            report.response_times.append(r.response_time_ms)

        # ── 5) Test sonrası cevap sayısı ─────────────
        await asyncio.sleep(1)  # DB yazımlarının tamamlanmasını bekle
        answers_after = await get_answer_count(session)
        report.answers_after = answers_after if answers_after >= 0 else 0

    # ── 6) RAPOR ─────────────────────────────────────
    print_report(report, results)


def print_report(report: TestReport, results: list[RequestResult]):
    """Detaylı test raporunu yazdırır."""

    times = sorted(report.response_times)

    print_header("📊 TEST RAPORU")

    # Genel özet
    print("\n  ┌─────────────────────────────────────────┐")
    print(f"  │  Toplam istek:          {report.total_requests:>6}           │")
    print(f"  │  ✅ Başarılı:            {report.successful:>6}           │")
    print(f"  │  ❌ Başarısız:           {report.failed:>6}           │")
    print(f"  │  ⏱️  Timeout:             {report.timed_out:>6}           │")
    print(f"  │  Toplam süre:           {report.total_duration:>6.2f}s         │")
    print("  └─────────────────────────────────────────┘")

    # Başarı oranı
    success_rate = (report.successful / report.total_requests * 100) if report.total_requests > 0 else 0
    print(f"\n  🎯 Başarı oranı: {success_rate:.1f}%")

    if success_rate == 100:
        print("     → Mükemmel! Tüm istekler başarılı.")
    elif success_rate >= 95:
        print("     → İyi, ama bazı istekler başarısız oldu.")
    elif success_rate >= 80:
        print("     → Dikkat! Önemli sayıda başarısız istek var.")
    else:
        print("     → ⚠️ Kritik! Çoğu istek başarısız oldu.")

    # Throughput
    if report.total_duration > 0:
        throughput = report.successful / report.total_duration
        print(f"  📈 Throughput: {throughput:.1f} başarılı istek/saniye")

    # Response time istatistikleri
    if times:
        avg = statistics.mean(times)
        p50 = times[int(len(times) * 0.50)]
        p95 = times[int(len(times) * 0.95)]
        p99 = times[int(len(times) * 0.99)]
        min_t = min(times)
        max_t = max(times)

        print_header("⏱️  Response Time Dağılımı")
        max_val = max_t
        print_bar("Min", min_t, max_val)
        print_bar("Avg", avg, max_val)
        print_bar("P50", p50, max_val)
        print_bar("P95", p95, max_val)
        print_bar("P99", p99, max_val)
        print_bar("Max", max_t, max_val)

        # Değerlendirme
        print()
        if avg < 200:
            print("  ✅ Ortalama response time mükemmel (< 200ms)")
        elif avg < 500:
            print("  ⚠️ Ortalama response time kabul edilebilir (200-500ms)")
        elif avg < 1000:
            print("  🔶 Ortalama response time yüksek (500ms-1s)")
        else:
            print("  ❌ Ortalama response time çok yüksek (> 1s)")

        if p95 < 1000:
            print("  ✅ P95 response time iyi (< 1s)")
        elif p95 < 3000:
            print("  ⚠️ P95 response time yüksek (1-3s)")
        else:
            print("  ❌ P95 response time çok yüksek (> 3s)")

    # Veritabanı yazma kontrolü
    print_header("💾 Veritabanı Yazma Kontrolü")
    expected_new = report.successful * len(ANSWER_TEMPLATES)  # Her başarılı istek N cevap yazar
    actual_new = report.answers_after - report.answers_before

    print(f"  Test öncesi cevap sayısı:  {report.answers_before}")
    print(f"  Test sonrası cevap sayısı: {report.answers_after}")
    print(f"  Beklenen yeni cevap:       {expected_new}")
    print(f"  Gerçek yeni cevap:         {actual_new}")

    if actual_new == expected_new:
        print("  ✅ Tüm cevaplar başarıyla kaydedildi! Veri kaybı yok.")
    elif actual_new > 0:
        loss = expected_new - actual_new
        loss_pct = (loss / expected_new * 100) if expected_new > 0 else 0
        print(f"  ⚠️ {loss} cevap kaybolmuş olabilir ({loss_pct:.1f}% kayıp)")
    else:
        print("  ❌ Cevap sayısı alınamadı veya hiç yazılmamış!")

    # Hata detayları
    if report.errors:
        print_header("❌ Hata Detayları")
        unique_errors = {}
        for err in report.errors:
            key = err.split(": ", 1)[-1] if ": " in err else err
            unique_errors[key] = unique_errors.get(key, 0) + 1

        for err, count in sorted(unique_errors.items(), key=lambda x: -x[1]):
            print(f"  [{count}x] {err[:80]}")

    # Sonuç ve öneriler
    print_header("📋 Sonuç ve Öneriler")

    issues = []
    if success_rate < 100:
        issues.append("❌ Başarısız istekler var → Worker sayısını artırmayı dene (uvicorn --workers 4)")
    if report.timed_out > 0:
        issues.append("⏱️ Timeout'lar var → Connection pool veya DB bağlantı limiti yetersiz olabilir")
    if times and statistics.mean(times) > 500:
        issues.append("🐢 Response time yüksek → DB connection pooling (pgbouncer) veya async driver düşün")
    if actual_new != expected_new and actual_new >= 0:
        issues.append("💾 Veri kaybı var → Transaction yönetimini kontrol et")

    if not issues:
        print("  🎉 Backend testi başarıyla geçti!")
        print("  → 200 eşzamanlı kullanıcıyı sorunsuz karşılayabiliyor.")
    else:
        print("  İyileştirme önerileri:")
        for issue in issues:
            print(f"    • {issue}")

    print()


# ============================================================
# Çalıştır
# ============================================================
if __name__ == "__main__":
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   QR Code Backend - Stress Test Tool     ║")
    print("  ╚══════════════════════════════════════════╝")
    asyncio.run(run_load_test())
