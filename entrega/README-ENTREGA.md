# Consolidador de reservas de hotel

O CLI rodava sem erro, mas os números estavam errados. Na amostra ele devolvia -33 noites e R$5962.41, quando o esperado era 28 noites e R$7566.00. Eram cinco defeitos. Quatro deles os testes fornecidos já acusavam, o quinto foi encontrado no arquivo real.

## Defeitos corrigidos

### 1. Status: NO_SHOW entrava nos totais

`status_policy.py`

```python
return status != "CANCELLED"     # antes
return status == "CONFIRMED"     # depois
```

Causa: a regra excluía só `CANCELLED`, então `NO_SHOW` era tratado como faturável. É por isso que `test_status_rules` deu 120.00 em vez de 100.00.

### 2. Noites: subtraía o dia do mês, não as datas

`stay_calculator.py`

```python
return (checkout.day - checkin.day) * rooms      # antes
return (checkout - checkin).days * rooms         # depois
```

Causa: a conta usava `.day` e não a diferença entre as datas, o que quebra na virada de mês.

### 3. Câmbio: dividia pela taxa e usava float

`currency_converter.py`

```python
return Decimal(str(float(amount) / float(rate)))   # antes
return amount * rates[currency]                    # depois
```

Causa: a operação estava invertida e usava `float`, o que viola a regra. Por isso 100 USD virava 18.45 em vez de 542.00.

### 4. Top hotéis: ordem crescente

`report_builder.py`

```python
sorted(hotels.items(), key=lambda item: (item[1]["amount"], item[0]))   # antes

ranked_hotels = sorted(hotels.items(), key=lambda item: item[0])        # depois
ranked_hotels.sort(key=lambda item: item[1]["amount"], reverse=True)
```

Causa raiz: a ordenação era crescente por valor, então os hotéis mais baratos apareciam primeiro. Com a correção, o desempate por `hotel_id` crescente continua valendo.

### 5. Leitura do CSV parava em 200 linhas

`repositories/csv_reservation_repository.py`

```python
if len(rows) == 200:
    break          # linhas removidas
```

Causa: um limite fixo de 200 linhas descartava reservas sem avisar. O `data/reservas_hoteis.csv` tem 300, então `total_reservations` e todos os totais do relatório principal saíam errados. O caso passou a ser coberto em `tests/test_extra.py`.

## Testes adicionados

`tests/test_extra.py` tem 20 testes para cenários que os fornecidos não cobrem, como leitura de mais de 200 linhas, virada de mês e de ano, ano bissexto, arquivo sem nenhuma reserva confirmada, empate no ranking e erros de argumento do CLI. Os testes fornecidos não foram alterados.

## Como validar:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

pytest -q

$env:PYTHONPATH="src"; python -m onfly_report --input data/exemplo-validacao.csv --rates data/taxas_cambio.csv --output output/exemplo.json
$env:PYTHONPATH="src"; python -m onfly_report --input data/reservas_hoteis.csv --rates data/taxas_cambio.csv --output output/report.json --top 5
```

Saída esperada:

Amostra: `Reservas: 12 | Confirmadas: 9 | Noites: 28 | Total BRL: 7566.00`

Arquivo principal: `Reservas: 300 | Confirmadas: 235 | Noites: 1347 | Total BRL: 396170.00`

Resultado do `pytest`: `25 passed`, sendo 5 fornecidos e 20 adicionados.
