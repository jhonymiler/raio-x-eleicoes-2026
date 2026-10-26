# benford-eleicoes-2026

Análise forense de Benford sobre os dados oficiais das eleições presidenciais
brasileiras de 2026, com controle histórico em 2022.

**[→ RELATÓRIO COM OS ACHADOS](resultados/RELATORIO.md)**
**[→ Teoria e método](docs/benford-teoria.md)**
**[→ Dossiê público da investigação de 2026](https://claude.ai/artifact/6hWk8PCf7GpwDaEsqFy3yN)**

Conclusão curta: **nenhuma evidência de fraude**. O único desvio forte é
reproduzido com três casas de precisão nas eleições de 2022, com outro
candidato — é assinatura geográfica estável, não manipulação.

---

## Estrutura

```
docs/benford-teoria.md        teoria: mantissa, invariâncias, Fourier, Nigrini
scripts/benford.py            suíte de testes (stdlib puro, sem dependências)
scripts/analisar.py           análise do CSV por seção (seção + município)
scripts/coletar_2t.py         coleta 2º turno pela API de divulgação do TSE (painel ao vivo)
scripts/totais_2t.py          totais finais do 2º turno por município (base das análises)
scripts/analisar_2t.py        análise dos totais municipais do 2º turno
scripts/controle_estrutural.py  Benford em eleitorado/comparecimento/abstenção
scripts/decomposicao.py       decomposição porte × share — o teste decisivo
scripts/historico.py          mesma bateria em 1994–2026 (papel × urna)
scripts/conferir_bu.py        boletim de urna × totalização, seção por seção
scripts/investigar.py         investigação nível 0–4 (BU × total, estados, municípios, seções)
scripts/aprofundar.py         testes de cada pista contra a hipótese inocente
scripts/idade_biometria.py    regressão biometria × idade dentro da escola
scripts/logs_urna.py          diário das urnas (amostra aleatória + suspeitas)
scripts/viradas.py            viradas municipais: linha de base e líderes locais
scripts/pistas.py             fichas das pistas (texto gerado dos resultados)
scripts/exportar_dossie.py    dados do dossiê público
scripts/dashboard.py          servidor do monitor em tempo real (+ .html)
dados/                        CSVs do TSE (não versionados, ~2,9 GB)
resultados/                   saídas em texto + RELATORIO.md
```

## Monitor em tempo real

```bash
python3 scripts/dashboard.py        # http://127.0.0.1:8765
```

Abre com uma explicação para leigos: papel × urna, 1º × 2º colocado de cada
eleição e um mapa por estado com veredito em linguagem simples. Abaixo,
mostra a totalização ao vivo e, recolhidos em “detalhes técnicos”, o primeiro dígito dos totais municipais e a
**razão de Fourier convergindo** conforme a apuração fecha, com o valor de
2022 como linha de referência. Revarre os 5.757 municípios a cada 5 minutos.

Existe um servidor porque **a API do TSE responde 403 a requisições com
cabeçalho `Origin`**: nenhuma página de navegador consegue chamá-la direto.
`dashboard.py` faz o proxy.

Nenhuma dependência externa: Python 3.11+ e stdlib. χ², Kuiper e a gama
incompleta estão implementados em `benford.py`.

---

## Reproduzir

```bash
# 1. dados do 1º turno (159 MB) e agregados por município/zona (2,4 MB)
curl -L -o dados/votacao_secao_BR_1t.zip \
  https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip
curl -L -o dados/detalhe_munzona_1t.zip \
  https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2026.zip
unzip -o dados/votacao_secao_BR_1t.zip -d dados/
unzip -o dados/detalhe_munzona_1t.zip -d dados/detalhe_munzona/

# 2. controle histórico de 2022 (271 MB)
curl -L -o dados/votacao_secao_BR_2022.zip \
  https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_BR.zip
unzip -o dados/votacao_secao_BR_2022.zip -d dados/

# 3. análises (~30 s cada)
python3 scripts/analisar.py dados/votacao_secao_2026_BR.csv "1o turno"
python3 scripts/controle_estrutural.py
python3 scripts/decomposicao.py dados/votacao_secao_2026_BR.csv 1 "2026 1T"
python3 scripts/decomposicao.py dados/votacao_secao_2022_BR.csv 1 "2022 1T"
python3 scripts/decomposicao.py dados/votacao_secao_2022_BR.csv 2 "2022 2T"

# 3b. série histórica 1994–2026 (~1,4 GB de zips, ~3 min) → resultados/historico.json
mkdir -p dados/historico
for y in 1994 1998 2002 2006 2010 2014 2018; do curl -L -o dados/historico/munzona_$y.zip \
  https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_$y.zip; done
python3 scripts/historico.py

# 3c. boletim de urna × totalização de um estado (~190 MB por UF, ~50 s)
#     URL exata em dadosabertos.tse.jus.br, conjunto "resultados-2026-boletim-de-urna"
mkdir -p dados/bu && curl -L -o dados/bu/bweb_1t_CE.zip \
  https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_CE_051020261403.zip
unzip -o dados/bu/bweb_1t_CE.zip -d dados/bu/
python3 scripts/conferir_bu.py CE

# 4. 2º turno — depois que a totalização encerrar
python3 scripts/totais_2t.py 6258
python3 scripts/analisar_2t.py 6258
```

`totais_2t.py` grava os totais finais por município, com a coluna `encerrada`.
`analisar_2t.py`, `segundo_turno.py` e `transferencia.py` leem esse arquivo e
avisam se algum município ainda não fechou: totais parciais distorcem os
dígitos por construção. `coletar_2t.py` serve só para o painel ao vivo.

Em todas as análises, os municípios do exterior (UF `ZZ`) ficam de fora, e o
porte do município é a soma dos votos válidos.

---

## O método, em uma tela

1. **Gate antes do teste.** `bf.fourier_empirico` estima |φ(2πk)| da amostra.
   X é Benford ⟺ φ_{log₁₀X}(2πk) = 0 para todo k ≠ 0. Se |φ(2π)| for muito
   maior que o ruído √(1/n), a forma do dado não é Benford e desvio nos
   dígitos não significa nada. **O gate lognormal (σ em décadas) erra por 100×
   nesses dados — não use.**

2. **Nível de agregação importa.** Votos por seção (~400 eleitores) falham o
   gate por 350×, inclusive o voto nulo. Totais por município passam.

3. **Sempre com controle.** Variáveis que ninguém manipula (eleitorado,
   comparecimento) e a mesma medição numa eleição anterior. Sem controle, um
   desvio não é interpretável.

4. **Decomposição.** `votos = porte × share`. Sob independência,
   |φ_V| = |φ_P|·|φ_S| ≤ |φ_P| — um fator independente só aproxima de Benford.
   Razão ≫ 1 localiza o acoplamento. É isso que distingue estrutura de ruído.

---

## Fontes

- [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026)
- [Boletins de urna 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna)
- [resultados.tse.jus.br](https://resultados.tse.jus.br) — API de divulgação

Códigos de eleição 2026: `6257` (Presidente 1T), `6258` (Presidente 2T),
`6259`/`6260` (Governador 1T/2T).
