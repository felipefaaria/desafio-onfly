# Declaração de uso de IA

Ferramenta e modelo: Claude Sonnet 5.5.

## Onde usei IA

**Lógica de ordenação do top de hotéis** (`services/report_builder.py`). Fiquei com dúvida de como ordenar por valor decrescente sem perder o desempate por `hotel_id` crescente. Eu tinha pensado em resolver com `reversed(...)`, mas não funcionou ja que o valor fica decrescente, mas o hotel_id também inverte. Os empates passam a sair em ordem decrescente, e a regra pede hotel_id ascendente. então pedi ajuda à IA para chegar na lógica correta. A solução final ordena primeiro por `hotel_id` e depois por valor com `reverse=True`.

**Testes extras** (`tests/test_extra.py`). Usei a IA para pensar em cenários que os testes fornecidos não cobrem e para escrever o arquivo.

## O que fiz sem IA

Todo o resto. Rodei o CLI e o `pytest`, investiguei os resultados errados e corrigi os demais defeitos do código por conta própria.
