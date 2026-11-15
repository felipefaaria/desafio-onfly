"""Testes adicionais: cenários do README não cobertos pelos testes fornecidos."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from helpers import PROJECT_ROOT, SRC_DIR, run_cli


def run_raw(args: list[str]) -> subprocess.CompletedProcess:
    """Executa o CLI com argumentos livres e devolve o processo (para checar o código de saída)."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + environment.get("PYTHONPATH", "")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "onfly_report", *args],
        cwd=str(PROJECT_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )


# --- Leitura -----------------------------------------------------------------------------


def test_reads_more_than_200_rows(tmp_path):
    """Todas as linhas do arquivo são lidas, sem limite fixo."""
    rows = [{"reservation_id": f"R-{i}"} for i in range(250)]
    report = run_cli(tmp_path, rows)
    assert report["summary"]["total_reservations"] == 250
    assert report["summary"]["confirmed_reservations"] == 250
    assert report["summary"]["total_amount_brl"] == "25000.00"


def test_hotel_name_with_comma_is_preserved(tmp_path):
    """Nome de hotel com vírgula (campo entre aspas no CSV) não quebra a leitura."""
    report = run_cli(tmp_path, [{"hotel_id": "H10", "hotel_name": "Hotel Madrid, Gran Vía"}])
    assert report["top_hotels"][0]["hotel_name"] == "Hotel Madrid, Gran Vía"


# --- Noites ------------------------------------------------------------------------------


def test_nights_across_year_boundary_with_multiple_rooms(tmp_path):
    """Virada de ano: 30/12 -> 02/01 = 3 noites, vezes 2 quartos = 6."""
    report = run_cli(
        tmp_path,
        [{"checkin_date": "2024-12-30", "checkout_date": "2025-01-02", "rooms": "2"}],
    )
    assert report["summary"]["total_room_nights"] == 6
    assert report["by_month"][0]["month"] == "2024-12"


def test_nights_leap_year_february(tmp_path):
    """Ano bissexto: 28/02/2024 -> 01/03/2024 = 2 noites."""
    report = run_cli(tmp_path, [{"checkin_date": "2024-02-28", "checkout_date": "2024-03-01"}])
    assert report["summary"]["total_room_nights"] == 2


# --- Status ------------------------------------------------------------------------------


def test_no_confirmed_reservations_gives_zeros(tmp_path):
    """Sem CONFIRMED: contagens preservadas, totais zerados, listas vazias, média "0.00"."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "status": "CANCELLED"},
            {"reservation_id": "R-2", "status": "NO_SHOW"},
        ],
    )
    assert report["summary"] == {
        "total_reservations": 2,
        "confirmed_reservations": 0,
        "cancelled_reservations": 1,
        "no_show_reservations": 1,
        "total_room_nights": 0,
        "total_amount_brl": "0.00",
        "average_nightly_rate_brl": "0.00",
    }
    assert report["by_month"] == []
    assert report["top_hotels"] == []


def test_non_confirmed_do_not_create_months_or_hotels(tmp_path):
    """CANCELLED/NO_SHOW não geram mês em by_month nem hotel em top_hotels."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01"},
            {
                "reservation_id": "R-2",
                "hotel_id": "H02",
                "status": "CANCELLED",
                "checkin_date": "2025-03-01",
                "checkout_date": "2025-03-02",
            },
            {
                "reservation_id": "R-3",
                "hotel_id": "H03",
                "status": "NO_SHOW",
                "checkin_date": "2025-04-01",
                "checkout_date": "2025-04-02",
            },
        ],
    )
    assert [m["month"] for m in report["by_month"]] == ["2025-01"]
    assert [h["hotel_id"] for h in report["top_hotels"]] == ["H01"]


# --- Câmbio e exatidão -------------------------------------------------------------------


def test_eur_conversion(tmp_path):
    """EUR usa a própria taxa: 150 * 5.88 = 882.00."""
    report = run_cli(tmp_path, [{"currency": "EUR", "amount": "150.00"}])
    assert report["summary"]["total_amount_brl"] == "882.00"


def test_rounding_happens_only_at_serialization(tmp_path):
    """3 x (0.01 USD * 5.42 = 0.0542) = 0.1626 -> "0.16" (arredondar cada um daria 0.15)."""
    rows = [{"reservation_id": f"R-{i}", "currency": "USD", "amount": "0.01"} for i in range(3)]
    report = run_cli(tmp_path, rows)
    assert report["summary"]["total_amount_brl"] == "0.16"


def test_rounding_is_half_up(tmp_path):
    """0.125 vira "0.13" com half-up (com half-even seria "0.12")."""
    report = run_cli(tmp_path, [{"amount": "0.125"}])
    assert report["summary"]["total_amount_brl"] == "0.13"


def test_average_nightly_rate(tmp_path):
    """Média = total / noites: 1000 / 3 = 333.333... -> "333.33"."""
    report = run_cli(tmp_path, [{"amount": "1000.00", "checkin_date": "2025-01-10", "checkout_date": "2025-01-13"}])
    assert report["summary"]["average_nightly_rate_brl"] == "333.33"


# --- Agregações e ordenação --------------------------------------------------------------


def test_by_month_uses_checkin_month_sorted_ascending(tmp_path):
    """by_month agrupa pelo mês do check-in, em ordem crescente, mesmo com o CSV fora de ordem."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "checkin_date": "2025-03-05", "checkout_date": "2025-03-06"},
            {"reservation_id": "R-2", "checkin_date": "2025-01-31", "checkout_date": "2025-02-02"},
            {"reservation_id": "R-3", "checkin_date": "2025-01-10", "checkout_date": "2025-01-11"},
        ],
    )
    assert report["by_month"] == [
        {"month": "2025-01", "reservations": 2, "room_nights": 3, "total_brl": "200.00"},
        {"month": "2025-03", "reservations": 1, "room_nights": 1, "total_brl": "100.00"},
    ]


def test_top_hotels_tie_breaks_by_hotel_id(tmp_path):
    """Empate em total_brl: desempata por hotel_id ascendente."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H03", "amount": "500.00"},
            {"reservation_id": "R-2", "hotel_id": "H01", "amount": "500.00"},
            {"reservation_id": "R-3", "hotel_id": "H02", "amount": "900.00"},
        ],
    )
    assert [h["hotel_id"] for h in report["top_hotels"]] == ["H02", "H01", "H03"]


def test_top_hotels_aggregates_multiple_reservations(tmp_path):
    """Várias reservas do mesmo hotel somam noites e valor."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "amount": "100.00"},
            {"reservation_id": "R-2", "hotel_id": "H01", "currency": "USD", "amount": "100.00", "rooms": "2"},
        ],
    )
    assert report["top_hotels"] == [
        {"hotel_id": "H01", "hotel_name": "Hotel Teste", "room_nights": 3, "total_brl": "642.00"}
    ]


def test_top_returns_fewer_when_not_enough_hotels(tmp_path):
    """--top maior que o número de hotéis devolve só os existentes."""
    report = run_cli(tmp_path, [{"hotel_id": "H01"}, {"reservation_id": "R-2", "hotel_id": "H02"}], top=10)
    assert len(report["top_hotels"]) == 2


# --- Contrato ----------------------------------------------------------------------------


def test_report_schema(tmp_path):
    """Chaves, versão, offset de generated_at e dinheiro como string com 2 casas."""
    report = run_cli(tmp_path, [{}])
    assert list(report) == ["report_version", "generated_at", "summary", "by_month", "top_hotels"]
    assert report["report_version"] == "1.0"
    assert report["generated_at"].endswith("-03:00")
    assert list(report["summary"]) == [
        "total_reservations",
        "confirmed_reservations",
        "cancelled_reservations",
        "no_show_reservations",
        "total_room_nights",
        "total_amount_brl",
        "average_nightly_rate_brl",
    ]
    assert list(report["by_month"][0]) == ["month", "reservations", "room_nights", "total_brl"]
    assert list(report["top_hotels"][0]) == ["hotel_id", "hotel_name", "room_nights", "total_brl"]
    assert report["summary"]["total_amount_brl"] == "100.00"


def test_exit_code_2_for_top_zero(tmp_path):
    process = run_raw(
        [
            "--input",
            "data/exemplo-validacao.csv",
            "--rates",
            "data/taxas_cambio.csv",
            "--output",
            str(tmp_path / "r.json"),
            "--top",
            "0",
        ]
    )
    assert process.returncode == 2


def test_exit_code_2_for_non_integer_top(tmp_path):
    process = run_raw(
        [
            "--input",
            "data/exemplo-validacao.csv",
            "--rates",
            "data/taxas_cambio.csv",
            "--output",
            str(tmp_path / "r.json"),
            "--top",
            "abc",
        ]
    )
    assert process.returncode == 2


def test_exit_code_2_for_missing_input_file(tmp_path):
    process = run_raw(
        [
            "--input",
            str(tmp_path / "nao_existe.csv"),
            "--rates",
            "data/taxas_cambio.csv",
            "--output",
            str(tmp_path / "r.json"),
        ]
    )
    assert process.returncode == 2


def test_exit_code_2_for_missing_required_argument(tmp_path):
    process = run_raw(["--input", "data/exemplo-validacao.csv"])
    assert process.returncode == 2


def test_default_top_is_5(tmp_path):
    """Sem --top, o ranking tem 5 hotéis (a amostra tem mais que isso)."""
    output = tmp_path / "r.json"
    process = run_raw(
        ["--input", "data/exemplo-validacao.csv", "--rates", "data/taxas_cambio.csv", "--output", str(output)]
    )
    assert process.returncode == 0
    assert len(json.loads(output.read_text(encoding="utf-8"))["top_hotels"]) == 5