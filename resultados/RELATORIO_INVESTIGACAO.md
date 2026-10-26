# Relatório da investigação — Eleição presidencial de 2026

**Período coberto:** sessões de 25/10/2026 (noite do 2º turno) a 26/10/2026, 00h25 BRT
**Fontes:** Portal de Dados Abertos do TSE, API de divulgação (`resultados.tse.jus.br`),
boletins de urna (BU), logs assinados das urnas, perfil do eleitorado, estimativa populacional do IBGE.
**Complementa:** [RELATORIO.md](RELATORIO.md) (análise de Benford 1º/2º turno e controle 2022) e
o dossiê público <https://claude.ai/artifact/6hWk8PCf7GpwDaEsqFy3yN>.

---

## Conclusão

**Nenhum sinal de fraude foi encontrado.** Cada pista levantada ou teve uma causa inocente
identificada e testada, ou tem tamanho pequeno demais para mudar o resultado
(margem do 2º turno: **4.430.191 votos**).

| Nível | O que foi testado | Resultado |
|---|---|---|
| 0 · Integridade | BU × totalização, voto a voto, nas 499.206 seções (27 UFs + exterior), SHA-512 conferido | **0 diferenças** em 3.800.511 registros |
| 1 · Estados | Mudança desde 2022, último dígito, Klimek, biometria, horários, Benford histórico | Nenhum estado fora do padrão (o mais distante, GO, z = 2,4, se explica pelo Caiado) |
| 2 · Municípios | Viradas desde 2022, crescimento do eleitorado, eleitores × moradores, migração 1T→2T | Sinais de **cadastro**, não de urna; impacto máximo bem abaixo da margem |
| 3–4 · Seções e urnas | Seção × vizinhas da mesma escola; logs de 988 urnas (e 10.800 no 1T) | Logs batem com o BU; nenhuma rajada de votos nem liberações em massa no fim do dia |
| Fora do alcance | A urna gravou o voto que o eleitor digitou? | **Não verificável com dados públicos** |

O ponto cego é real: sem registro em papel conferido pelo eleitor, um erro ou adulteração
**dentro** da urna, antes da impressão do boletim, não aparece em nenhum dado publicado.

---

## 1. Hipótese "Benford funcionava no papel (1994) e quebrou com a urna"

Script: [scripts/historico.py](../scripts/historico.py) → [historico.txt](historico.txt).
Primeiro dígito do total por município, presidente, 1994–2026.

| | Papel (1994) | Urna (2002–2026) |
|---|---|---|
| MAD mediano, candidatos com ≥ 1% dos votos | 0,0044 | 0,0054 |
| Testes por estado (1º e 2º colocado) com "desvio" | 13% (4 de 30) | 12% (17 de 147) |
| Candidatos em "não conformidade" | 0 de 8 | 24 de 70, **todos com < 0,2% dos votos** |

- O cálculo do Enéas em 1994 está certo (MAD 0,0038), mas **FHC, no papel, desviou** (MAD 0,0108,
  p = 10⁻⁸) — praticamente o mesmo desvio de Bolsonaro na urna em 2022 (0,0098).
- Os 4 desvios estaduais de 1994 são todos de FHC (MA, PE, PR, RN).
- A aparente piora pós-2002 vem de **nanicos** com 1–9 votos por município, que não seguem Benford.
- O controle (total de votos por município) fica em 0,009–0,011 em todos os anos, 1994 incluído.
- 2º dígito (Mebane) e últimos dígitos (Beber & Scacco): sem sinal consistente em nenhum ano.

**Veredito:** o desvio acompanha o perfil geográfico do candidato, não o meio de votação.

---

## 2. Boletins de urna × resultado oficial

Script: [scripts/conferir_bu.py](../scripts/conferir_bu.py).

- **Ceará** (onde o Lula aparecia com "desvio"): 23.765 seções, 167.164 registros, **0 diferenças**
  ([conferencia_bu_CE_1t.txt](conferencia_bu_CE_1t.txt)). O total de votos dos municípios do CE,
  que ninguém manipula, desvia **mais** que o voto do Lula (MAD 0,0315 × 0,0280): o Lula teve
  47–84% em todos os 184 municípios e herda a forma do tamanho das cidades.
- **Brasil inteiro:** 28 arquivos (27 UFs + exterior), SHA-512 conferido, 499.206 seções,
  3.800.511 registros, **0 diferenças**.

Limite: o arquivo `bweb` é transcrição do próprio TSE. A checagem independente é confrontar
fotos de boletins tiradas por fiscais de partido.

---

## 3. Investigação forense do 1º turno (macro → micro)

Pipeline: `investigar.py` → `idade_biometria.py` → `aprofundar.py` → `logs_urna.py` →
`viradas.py` → `exportar_dossie.py`. Saídas em [investigacao.txt](investigacao.txt),
[aprofundamento.txt](aprofundamento.txt), [idade_biometria.txt](idade_biometria.txt),
[logs_urna.txt](logs_urna.txt), [viradas.json](viradas.json).

| Pista | Status | Achado |
|---|---|---|
| Estado mudou de forma anormal desde 2022? | explicada | Nenhum; GO (z = 2,4) tem o Caiado com 12,3% |
| Números inventados (último dígito) | sem sinal | Nenhum estado com excesso de 0 e 5 (maior \|z\| = 3,4) |
| Liberação sem digital × voto | **explicada** | z = 9,6 a favor do Lula some com a idade no modelo (+8,4 → +0,3 pp, z = 1,3). Digital falha mais em idosos (coef. liberação × 60+ com z = 212). 135 de 150 urnas mostram leitor falhando desde o 1º eleitor, espalhado no dia |
| Seções com ~100% de comparecimento e voto | explicada | 65 seções (62 Lula, 3 Flávio); 14 em aldeia/quilombo/assentamento; 18 de 21 já davam ≥ 90% em 2022; 92% identificados por digital |
| Seções que destoam da própria escola | **aberta** | 185 de 451.803 (0,04%): 123 pró-Lula, 62 pró-Flávio; 55 de 60 já destoavam em 2022; 125 são seções novas e mais jovens. Saldo ≈ **3.460 votos** |
| Viradas municipais desde 2022 | explicada em parte | 7 viradas (contra 0–2 nas trocas anteriores). Em todas, 100% das seções mudaram juntas; vários casos com líder local do PL > 30% na cidade |
| Crescimento anormal do eleitorado | **aberta** | 17 municípios (Canaã dos Carajás, Maricá, Extremoz, litoral de SC…); comparecimento normal, maioria por digital. Anhangüera combina crescimento e comparecimento baixo (título transferido) — caso de **cadastro** |
| Horário de abertura/encerramento | sem sinal | Nenhuma urna abriu cedo nem fechou antes das 17h de Brasília; 955 abriram com > 30 min de atraso |
| Seções do exterior com mesmo nº de urna | explicada | 28 seções votaram em cédula |
| Logs × boletim | sem sinal | 988 de 988 batem; nenhum voto < 20 s após o anterior no controle; intervalo mediano 100 s |

**Logs por grupo (1º turno, 988 urnas):**

| grupo | logs | batem com BU | liberação manual | seq. ≥ 10 | última hora |
|---|---|---|---|---|---|
| controle | 600 | 600 | 6,5% | 0 | 9,9% |
| seções novas destoantes | 117 | 117 | 6,7% | 0 | 9,1% |
| seções antigas destoantes | 56 | 56 | 6,4% | 0 | 8,9% |
| Klimek (canto) | 65 | 65 | 7,2% | 0 | 6,9% |
| biometria alta | 150 | 150 | 73,2% | 136 | 11,6% |

**Falsos alarmes do próprio método, corrigidos e registrados:** fuso do oeste do AM (UTC−5),
teste do último dígito (inclinação 0 > 9 — usar excesso de 0/5 acima da reta), logs com `.jez`
aninhado (urna trocada) e uma frase exagerada sobre líderes locais.

---

## 4. Contexto institucional (pesquisado a pedido)

Fontes primárias priorizadas; imprensa grande e alternativa confrontadas.

- **Voto impresso — histórico:** Lei 10.408/2002 (FHC) testada no DF e SE e revogada em 2003;
  Lei 12.034/2009 **sancionada por Lula**, derrubada no STF (ADI 4543); veto de Dilma derrubado em
  2015, lei derrubada por unanimidade no STF em 2020 (ADI 5889, ação de Raquel Dodge); PEC rejeitada
  em 2021 por 229 × 218 (precisava 308), com PT/PSOL/PCdoB **e também** PL, PSD, MDB, PSDB, DEM contra.
- **Código-fonte:** a nota do Ministério da Defesa (10/11/2022) registra restrições de acesso a
  código e bibliotecas de terceiros e diz que o teste de integridade não bastava para afastar
  código malicioso — mas **não apontou fraude**. O código ficou aberto às FA desde out/2021 (inspeção
  agendada só em ago/2022). Para 2026, aberto em 2/10/2025; inspecionaram União Brasil, Senado, SBC,
  CNC, CGU, PGR e CNMP. Não foi encontrado registro de inspeção do PL nem das FA em 2026 (a confirmar).
- **Comando do TSE em 2026:** presidente Nunes Marques e vice André Mendonça, ambos indicados ao STF por Bolsonaro.
- **Fatos do dia do 2º turno:** liminar do ministro Zanin estendendo a votação até 19h (pedido das
  duas campanhas, por alagamentos/energia/transporte), com execução caótica — muitas seções fecharam
  às 17h. Antecipação do Bolsa Família para 4 dias antes do 2º turno: possível **abuso de poder**
  (tema da Justiça Eleitoral), não fraude na urna.
- **Pesquisas:** Flávio liderou 17 de 18 pesquisas finais (Datafolha/Quaest 51 × 49, Atlas 50,8 × 49,2);
  resultado 48,2 × 51,8 — erro de ~2,6–2,8 pontos, fora da margem. Erro relevante, mas já ocorreu na
  direção oposta (2022).

---

## 5. 2º turno

**Totalização encerrada (100%):** Lula **64.256.232 (51,79%)** × Flávio **59.826.041 (48,21%)**.
Fontes: [balanco_turnos.txt](balanco_turnos.txt), [migracao.txt](migracao.txt),
[transferencia.txt](transferencia.txt), [realidade.txt](realidade.txt).

### 5.1 Balanço 1T → 2T (Brasil + exterior)

| | 1º turno | 2º turno | diferença |
|---|---|---|---|
| comparecimento | 125.275.835 | 128.236.074 | +2.960.239 |
| Lula | 53.879.538 | 64.256.232 | +10.376.694 |
| Flávio | 56.104.503 | 59.826.041 | +3.721.538 |
| brancos + nulos | 5.969.801 | 4.153.801 | −1.816.000 |
| eliminados | 9.321.993 | — | — |

Lula ficou com **74%** do ganho dos dois finalistas.

### 5.2 Migração por município

- **A conta fecha** em 100% dos 5.571 municípios (Lula + Flávio + brancos + nulos = comparecimento).
- A parcela do Lula no "bolo" cai conforme cresce a direita entre os eliminados do município —
  coerente com eleitor escolhendo:

| direita entre eliminados | municípios | parcela do Lula |
|---|---|---|
| 20–40% | 270 | 91% |
| 40–50% | 1.030 | 87% |
| 50–60% | 2.228 | 76% |
| 60–70% | 1.451 | 69% |
| 70–80% | 162 | 67% |
| 80–100% | 250 | 57% |

- **Goiás** (melhor teste, Caiado com 472 mil votos): ~59% (±4) dos eleitores do Caiado foram
  para o Flávio e ~34% (±5) para o Lula. Ainda assim o Lula ganhou mais votos ali (+396 mil × +293 mil).
- Brancos/nulos do 1T foram majoritariamente para o Lula (estimativa de 102%, ±17, com os totais
  finais; passar de 100% é a instabilidade da inferência ecológica). Nos redutos do Lula o
  comparecimento subiu mais (~6% sobre a base do 1T).
- Alertas: 938 municípios onde o Flávio **perdeu** votos (sobretudo Nordeste; no Norte, MA e PI
  o comparecimento caiu e ele foi quem mais perdeu), 290 onde o Lula ganhou mais que o bolo,
  14 com salto de comparecimento. Lista em [migracao.txt](migracao.txt).
- Limitação: a regressão nacional por candidato é instável (coeficientes fora de 0–100%), problema
  conhecido de inferência ecológica.
- **Matriz de transferência com restrições** ([matriz_transferencia.txt](matriz_transferencia.txt)):
  cada origem do 1T é dividida em 100% entre Lula, Flávio, branco/nulo e abstenção, com ajuste por estado.
  - Eliminados (9,3 mi): **~50% Lula [47–53], ~35% Flávio [33–37]**, 11% branco/nulo, 3% não votou.
    Só Renan+Caiado+Zema: 43–47% Lula × 40–42% Flávio, um empate.
  - Branco/nulo do 1T: ~55–60% Lula, ~1–4% Flávio. Quem não votou no 1T e votou no 2T: 2,7 mi Lula × 1,2 mi Flávio.
  - Decomposição da virada (+6,6 mi na margem): brancos/nulos +3,6 mi, novos eleitores +1,5 mi,
    Renan +1,2 mi, Cury +0,8 mi; Caiado −0,6 mi e Zema −0,2 mi a favor do Flávio; a troca direta
    entre as bases (~0,9% para cada lado) quase se anula. O modelo prevê a margem final em 4,38 mi (real 4,40 mi).
  - Controle de 2022 ([matriz_transferencia_2022.txt](matriz_transferencia_2022.txt)): o mesmo ajuste por
    município e por seção (471 mil) dá para os eliminados 37/42% e 36/44% (Lula/Bolsonaro). O viés de
    agregação é de ~2 pontos.
- **Lula perdeu votos** em 79 municípios (16 mil votos no total, sobretudo AM, AP, MA, PA e AC). Em
  todos os 79 o comparecimento caiu, e em 74 o Flávio também perdeu. Nenhum estado teve queda do Lula no
  total; o Flávio caiu no total em AC, AP, AM, MA, RR e TO.
- **Direita eliminada por estado** (Renan+Caiado+Zema; tabela no fim de
  [matriz_transferencia.txt](matriz_transferencia.txt)): o Flávio levou a maior parte em SC (~79%), PR,
  GO e RJ; o Lula, na BA (~99%), SP, MG, PA, MA e PI. Estados com poucos municípios têm faixa larga, e o DF
  (um só município) não tem estimativa.
- **Bolsa Família** ([bolsa_familia.txt](bolsa_familia.txt), pagamento de agosto/2026, 18,7 mi famílias):
  - Os 938 municípios onde o Flávio perdeu votos têm cobertura mediana de 21,6% (contra 9,2%) e
    Lula com 70% no 1T. O comparecimento caiu 1,9% ali, e havia poucos eliminados para dividir.
    Só pela queda de comparecimento e pela fatia normal dos eliminados, o Flávio teria 3,71 mi; teve 3,52 mi.
  - Dentro do estado e controlando o voto do 1T, mais cobertura **não** muda a parcela do Lula
    (−0,02 pp por +10 pontos de cobertura, z = −0,6) nem o comparecimento (z = +1,7). A variação do
    Flávio é 0,7 ponto menor por +10 pontos (z = −5): efeito real, mas pequeno.

### 5.3 "A quantidade de votos expressa a realidade?"

- População 213.251.678; aptos 157.691.290 (73,9%); comparecimento 127.746.033 (59,9%).
- **718 municípios têm mais eleitores que moradores** (324.638 além da população), sobretudo MG,
  GO, PI e RS. Casos extremos: Davinópolis-GO (2,19 aptos por morador), Anhangüera-GO (1,90).
- Pior caso, tirando do Flávio todo votante acima de 78% da população: **708.713 votos** — contra
  margem de 4.430.191.
- Esses municípios se moveram **menos** para o Lula (correlação −0,27 dentro do estado).
- Diagnóstico: cadastro desatualizado (domicílio eleitoral, óbitos, mudanças), não urna. Pesa mais
  em eleições municipais.

### 5.4 Auditoria nacional de logs (10.800 urnas sorteadas, 400 por UF)

- **1º turno (3220): concluída** — [logs_nacional_3220.txt](logs_nacional_3220.txt). Liberação
  manual entre 3,8% (RR) e 8,3% (PI); no máximo 1 sequência ≥ 10 liberações por UF; **0** urnas
  com padrão de liberações concentradas no fim; **0** votos rápidos.
- **2º turno (3221): concluída** — [logs_nacional_3221.txt](logs_nacional_3221.txt), as mesmas
  10.800 seções. Liberação manual entre 4,1% (RR) e 8,7% (PI), igual ao 1º turno; **0** urnas com
  liberações concentradas no fim; 3 votos rápidos em 2,68 milhões.
  - *Correção:* a primeira rodada repetia os números do 1º turno. O log do 2º turno acumula o do 1º
    (mesma urna) e `logs_urna.medir` filtrava a data fixa 04/10. Agora filtra o dia de cada pleito.

### 5.5 A prorrogação até 19h (liminar do ministro Zanin) mudou os votos?

Não houve disparada. Os logs registram a hora de cada voto, mas não o candidato. Por isso o teste
estima quantos votos a prorrogação poderia ter mudado, no máximo:

| Amostra de 10.800 urnas | 1º turno (04/10) | 2º turno (25/10) |
|---|---|---|
| Votos depois das 17h | 93.876 (3,53%) | **741 (0,028%)** |
| Urnas que votaram mais de 15 min além das 17h | 2.816 | **23** |
| Votos na última hora de cada urna | 10,3% | 6,9% |

- Na prática, quase todas as urnas fecharam às 17h. Isso combina com as notícias de mesários que
  não foram avisados da prorrogação.
- Levado ao país inteiro, no limite superior do intervalo de 99% (0,031% de 128,2 milhões),
  dá **no máximo cerca de 39 mil votos** depois das 17h. Mesmo que todos fossem do Lula, isso é
  0,9% da margem de 4.430.191.
- O 2º turno teve **menos** voto tardio que o 1º, quando não houve prorrogação.

---

## 6. Pistas que estavam abertas, e como foram fechadas (26/10, madrugada)

Scripts: [`scripts/conferir_2t.py`](../scripts/conferir_2t.py) (decodifica o `bu.dat` assinado de cada
urna do 2º turno, ASN.1, sem dependências) e [`scripts/fechar_pendencias.py`](../scripts/fechar_pendencias.py).
Saídas: [conferir_2t.txt](conferir_2t.txt), [pendencias.txt](pendencias.txt).

| Pista | Teste novo | Resultado | Situação |
|---|---|---|---|
| BU × totalização no 2º turno | BU assinado de 12.746 seções = 108 municípios sorteados inteiros (13.806 BUs baixados) | 0 diferenças em 3.128.134 votos | sem sinal |
| 185 seções destoantes da escola | BU do 2º turno da seção e das vizinhas, com urnas recarregadas | 172 de 173 destoam de novo no mesmo sentido (correlação 0,98). Exceção: Camaçari-BA z170 s262 | explicada (composição) |
| 7 viradas | Mesma regra, 2º turno 2022 × 2º turno 2026 | Só 3 de 5.570 (Belo Monte-AL, Pedro Laurentino-PI, São Julião-PI), todas com deputados locais de 26–61% na cidade | explicada |
| 17 com crescimento anormal | Censo 2022 × estimativa 2025 do IBGE | População cresceu ≥ 2× a mediana em 11; Lula perdeu espaço em todas as 17 | explicada (cadastro) |
| 718 com mais eleitores que moradores | Eleitorado 2022 × Censo 2022 (contagem) | 532 já estavam acima em 2022 (193.440 a mais) | explicada (cadastro antigo) |
| Flávio perdeu votos em 938 | Comparecimento, logs das mesmas urnas, 2022 | 728 com queda de comparecimento = 121.217 dos 133.900 votos; logs: votos −4,7%, digital 90,9% → 90,8%, 0 rajadas. Bolsonaro perdeu votos entre turnos em só 92 cidades em 2022 | explicada; resto ≤ ~56 mil na margem (1,3%) |
| Teste de integridade 2026 | Fonte oficial | TSE e TRE-SP (25/10): cédulas corresponderam aos votos no 2º turno | fora do alcance dos dados; resultado oficial citado |

Sobra sem verificação: a lista oficial de entidades que inspecionaram o código em 2026 (o site do
TSE responde 403 a acesso automatizado). É contexto, não dado de votação.

### Pistas remanescentes

| Pista | Impacto máximo | Próximo passo |
|---|---|---|
| 185 seções destoantes da própria escola | ~3.460 votos | Encerrado: persistem no 2º turno; só Camaçari-BA z170 s262 vale o boletim impresso |
| 17 municípios com crescimento anormal | cadastro | Encerrado: revisão de rotina do TRE |
| 718 municípios com mais eleitores que moradores | ≤ 708.713 votos | Encerrado: excesso já existia no Censo 2022 |
| Virada do 2º turno no Nordeste | explicada | Logs do 2T sem rajada nem voto tardio; com o voto do 1T controlado, cobertura do Bolsa Família não muda a parcela do Lula nem o comparecimento |
| Prorrogação até 19h (Zanin) | sem sinal · ≤ ~39 mil votos | Encerrado: 99,8% das urnas da amostra fecharam às 17h |
| Inspeção do código em 2026 por PL/FA | — | Confirmar na lista oficial do TSE |
| Urna gravou o voto digitado? | fora do alcance | Só registro em papel conferido pelo eleitor resolve em todas as urnas |

---

## 7. O que mudaria a conclusão

- Um boletim impresso, fotografado na seção, diferente do resultado publicado;
- um teste de integridade com cédulas que não batem com a urna;
- logs com votos em rajada ou liberações em massa no fim do dia;
- código malicioso identificado por quem inspecionou.

Nada disso apareceu até aqui.

---

## 8. Artefatos

- Dossiê público (8 abas, fichas de pistas, fontes com hash):
  <https://claude.ai/artifact/6hWk8PCf7GpwDaEsqFy3yN> — precisa ser compartilhado pelo menu
  *Compartilhar*. O "quadro de investigação" (cortiça e barbantes) foi feito mas **não publicado**.
- Dashboard local: `python3 scripts/dashboard.py` (seção histórica 1994–2026 e vereditos em linguagem simples).
- Dados do dossiê: [dados/derivados/dossie/](../dados/derivados/dossie/).
- Método e invariantes: [CLAUDE.md](../CLAUDE.md), [docs/benford-teoria.md](../docs/benford-teoria.md).

> Benford é filtro de atenção, nunca evidência. A auditoria que prova algo é conferir boletim de
> urna assinado contra a totalização — e essa conferência deu zero diferenças.
