# Faza 1: Demo — Drukarnia DNJ

> [cite_start]Przygotowanie środowiska Odoo 17 Community pod system zarządzania produkcją i Shop Floor Kiosk[cite: 143, 148].

## Infrastruktura
* **Serwer:** 77.42.20.195
* [cite_start]**Środowisko:** Docker Compose (Odoo 17.0, PostgreSQL 15) [cite: 148]
* **Baza danych:** dnj_demo

## Konfiguracja Odoo (Baza dla Kiosku)
1. **Moduły:** Zainstalowano podstawowy moduł `Produkcja` (MRP).
2. **Ustawienia:** Włączono `Zlecenia pracy` (Work Orders) w celu rozbicia produkcji na etapy i umożliwienia routingu na konkretne maszyny.
3. [cite_start]**Gniazda produkcyjne:** Utworzono wirtualną maszynę `Heidelberg Speedmaster` (reprezentuje 1 z 16 fizycznych maszyn drukarni [cite: 26]).
4. **Produkty i Technologia (BoM):**
   * Produkt testowy: `Ulotka A4` (Typ: Produkt rejestrowany).
   * Zestawienie materiałowe: Przypisano operację `Druk` do gniazda `Heidelberg Speedmaster`.

## Symulacja Procesu (Działanie Kiosku)
[cite_start]Przygotowano logikę pod zastąpienie obecnego Excel-TZ[cite: 40]:
* Utworzono testowe Zamówienie produkcji (`WH/MO/00001`).
* System poprawnie wygenerował zadanie (Zlecenie operacji) dla maszyny `Heidelberg Speedmaster`.
* [cite_start]Przetestowano cykl życia zadania operatora (Start / Stop timer) z poziomu backendu Odoo, co stanowi fundament pod docelowy interfejs tabletowy bez przeładowania strony (OWL)[cite: 148].
