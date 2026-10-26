# Análise forense de Benford — Eleições 2026 (Presidente)

**Data da análise:** 25/10/2026, 21h55 BRT · **revisão:** 26/10/2026, 02h
**Fonte:** Portal de Dados Abertos do TSE + API de divulgação oficial
**Método:** [`docs/benford-teoria.md`](../docs/benford-teoria.md)

> **Revisão de 26/10 (auditoria dos números).** Três correções, todas nos
> dados de entrada. As fórmulas estavam certas.
> 1. O 2º turno usava o retrato parcial (99,87%). Agora usa os totais finais
>    (`totais_2t_municipio_6258.csv`, 5.571 municípios, todos encerrados).
> 2. Os ~145 municípios do exterior (UF `ZZ`) entravam como se fossem
>    municípios brasileiros. Agora ficam de fora em todos os scripts.
> 3. O porte não tinha a mesma definição em todos os turnos: com brancos e
>    nulos nos CSVs por seção, e só votos válidos no 2T pela API. Agora é
>    **votos válidos** em todos.
>
> A conclusão não muda. A faixa da razão passa de 2,96–3,23 para
> **2,87–3,05**.

---

## Conclusão

**Não há evidência de fraude nos dados analisados.**

O único desvio estatisticamente forte encontrado — nos totais municipais de
Flávio Bolsonaro — **se repete nas eleições de 2022**, com outro candidato, em
turnos contados separadamente, numa faixa estreita (2,87–3,05). É uma
assinatura estável da geografia eleitoral daquele eleitorado, não um artefato
de manipulação.

| eleição | Bolsonaro | Lula |
|---|---|---|
| 2022, 1º turno | **2,93×** | 0,49× |
| 2022, 2º turno | **2,87×** | 0,47× |
| 2026, 1º turno | **2,88×** | 0,65× |
| 2026, 2º turno | **3,05×** | 0,45× |

*Municípios brasileiros (exterior excluído), porte = votos válidos, 2º turno
de 2026 com 100% totalizado.*

Uma manipulação teria de reproduzir a mesma estrutura log-periódica em quatro
turnos, dois candidatos e eleições separadas por quatro anos.

### A previsão que foi testada ao vivo

Às 20h41, com 66% apurado, registrei que *se* a leitura estrutural estivesse
certa, a razão — então inflada em 4,64× pela apuração parcial — deveria cair
para perto de 3× conforme a totalização fechasse, e a base |φ_P| subir para
perto de 0,066. Foi o que aconteceu:

| apurado | base \|φ_P\| | Bolsonaro | Lula |
|---|---|---|---|
| 65,94% | 0,0397 | 4,64× | 0,97× |
| 85,84% | 0,0602 | 3,28× | 0,56× |
| 99,87% | 0,0639 | 3,23× | 0,44× |
| **100%** | **0,0654** | **3,18×** | **0,41×** |
| 2022 completo | 0,0653–0,0655 | 2,96–3,04× | 0,48–0,52× |

*Esta tabela usa a definição da noite da coleta (exterior incluído), para que
as linhas sejam comparáveis entre si. Na definição corrigida, o 2T fechado dá
3,05× e 0,45×, e 2022 dá 2,87–2,93× e 0,47–0,49×.*

A previsão era falsificável: se a razão tivesse ficado em 4,6× com a base já
normalizada, haveria algo a investigar. Ela convergiu.

---

## 1. Dados

| conjunto | registros | estado |
|---|---|---|
| 1º turno — votação por seção (CSV oficial) | 3.800.511 linhas · 499.206 seções · 5.571 municípios (+145 no exterior, excluídos) | completo |
| 2º turno — totais por município (API) | 5.571 municípios (+186 no exterior, excluídos) · 497.897 seções | **100%, encerrada** |
| 2022 — 1º e 2º turnos (controle) | 5.570 municípios (exterior excluído) | completo |

**O 2º turno de 2026 foi em 25/10.** O CSV consolidado só sai no portal de
dados abertos daqui a alguns dias. A coleta foi feita pela API de divulgação
com `totais_2t.py`, depois que todos os municípios marcaram a totalização
como encerrada. A primeira versão deste relatório usou um retrato de 99,87%
(`coletar_2t.py`). Nesse retrato faltavam 9 municípios inteiros, e outros 61
ainda mudaram de valor depois. A varredura leva ~24 min a 4 req/s; ver a nota
sobre limite de taxa em `CLAUDE.md`. Para refazer:

```bash
python3 scripts/totais_2t.py 6258 && python3 scripts/analisar_2t.py 6258
```

---

## 2. Votos por seção: o teste não se aplica — e isso é o achado

Seções têm ~400 eleitores. A faixa é estreita demais para Benford.

| série | σ (décadas) | \|φ(2π)\| | excesso sobre o ruído |
|---|---|---|---|
| Flávio Bolsonaro | 0,241 | 0,5129 | **362×** |
| Lula | 0,196 | 0,4923 | **347×** |
| Voto nulo | 0,284 | 0,3009 | **211×** |

Todas as séries falham o χ² com p = 0 — **inclusive o voto nulo**, que
ninguém tem motivo para manipular. Isso não é sinal de fraude: é a prova de
que o método não vale nesse nível de agregação.

O teste do segundo dígito (2BL, o padrão da literatura de *election
forensics*) também rejeita tudo:

| série | MAD | classificação |
|---|---|---|
| Flávio Bolsonaro | 0,01307 | não conformidade |
| Lula | 0,00918 | aceitável |
| Voto nulo | 0,05159 | não conformidade |

> **Qualquer alegação de fraude construída sobre primeiro ou segundo dígito de
> votos por seção é um artefato de método.** O voto nulo é a prova de
> controle: ele "falha" tão espetacularmente quanto os candidatos.

---

## 3. Totais por município: aqui o teste vale

Nesse nível os totais vão de ~10² a ~10⁶ e o gate de Fourier aprova.

### 1º turno de 2026

| candidato | \|φ(2π)\| / ruído | χ² (1º dígito) | p | MAD | Kuiper p |
|---|---|---|---|---|---|
| Lula | 1,6× — forma Benford | 12,8 | 0,118 | 0,00327 | 0,088 |
| Flávio Bolsonaro | 6,5× — forma marginal | 85,6 | **3,6 × 10⁻¹⁵** | 0,01145 | 1,4 × 10⁻¹⁵ |

Lula conforma. Flávio Bolsonaro desvia, com excesso concentrado no dígito 1:

```
1:  1.954 obs  vs  1.677 esp   +4,97pp   z = +8,07
5:    363 obs  vs    441 esp   −1,40pp   z = −3,85
6:    310 obs  vs    373 esp   −1,13pp   z = −3,35
4:    468 obs  vs    540 esp   −1,29pp   z = −3,23
```

### 2º turno de 2026 (100%, encerrada)

Resultado nos municípios brasileiros: **Lula 51,78%** (64.056.078) ×
**Flávio Bolsonaro 48,22%** (59.654.544). Com o exterior: 64.256.232 ×
59.826.041, os mesmos 51,79%.

| candidato | \|φ(2π)\| / ruído | χ² (1º dígito) | p | MAD | Kuiper p |
|---|---|---|---|---|---|
| Lula | 1,3× — forma Benford | 8,1 | 0,423 | 0,00359 | 0,124 |
| Flávio Bolsonaro | 6,4× — forma marginal | 80,4 | **4,1 × 10⁻¹⁴** | 0,01161 | 3,3 × 10⁻¹⁴ |

O mesmo padrão, mesmo sinal, mesma magnitude do 1º turno — em dados apurados
três semanas depois, por outra contagem:

```
1:  1.923 obs  vs  1.677 esp   +4,42pp   z = +7,17
6:    294 obs  vs    373 esp   −1,42pp   z = −4,21
5:    370 obs  vs    441 esp   −1,28pp   z = −3,50
4:    476 obs  vs    540 esp   −1,15pp   z = −2,87
```

Compare com o 1º turno acima: excesso no dígito 1 de +4,97pp contra +4,42pp,
déficit espalhado em 4–7. É a mesma assinatura.

---

## 4. Controle estrutural: variáveis que ninguém manipula

| variável | \|φ(2π)\| / ruído | p (1º dígito) | dígito 1 |
|---|---|---|---|
| eleitorado apto | 4,8× | 2,7 × 10⁻⁷ | **−3,12pp** |
| comparecimento | 4,9× | 5,9 × 10⁻⁹ | **−3,11pp** |
| abstenções | 3,1× | 0,0045 | +0,91pp |
| votos válidos | 5,0× | 1,4 × 10⁻⁸ | **−3,18pp** |

A geografia municipal brasileira **já não é Benford**, a ~5× o ruído. Mas o
desvio da base é no sentido **oposto** (déficit de dígito 1) ao de Flávio
Bolsonaro (excesso). Então o desvio dele não é simplesmente herdado — e é isso
que motivou a decomposição.

---

## 5. Decomposição de Fourier — o teste decisivo

Para cada município: `votos = porte × share`. Em log, soma. Se porte e share
forem **independentes**, a função característica do produto é o produto das
funções características:

$$|\varphi_V(2\pi)| = |\varphi_P(2\pi)| \cdot |\varphi_S(2\pi)| \;\le\; |\varphi_P(2\pi)|$$

Ou seja: **um fator multiplicativo independente só pode aproximar de Benford.**
Razão observado/esperado ≫ 1 prova acoplamento na frequência 2π.

Em todos os turnos: municípios brasileiros (exterior excluído) e porte =
votos válidos. Share = votos do candidato / votos válidos do município.

### 2026, 1º turno (porte: |φ| = 0,0671)

| candidato | \|φ_V\| | \|φ_S\| | esperado | **razão** |
|---|---|---|---|---|
| Flávio Bolsonaro | 0,0870 | 0,4503 | 0,0302 | **2,88×** |
| Lula | 0,0208 | 0,4786 | 0,0321 | 0,65× |
| Augusto Cury | 0,0505 | 0,5875 | 0,0394 | 1,28× |
| Ronaldo Caiado | 0,0543 | 0,2892 | 0,0194 | 2,80× |

### 2022, 1º turno — controle (porte: |φ| = 0,0664)

| candidato | \|φ_V\| | \|φ_S\| | esperado | **razão** |
|---|---|---|---|---|
| Jair Bolsonaro | 0,0726 | 0,3728 | 0,0247 | **2,93×** |
| Lula | 0,0196 | 0,5958 | 0,0395 | 0,49× |
| Simone Tebet | 0,0739 | 0,3205 | 0,0213 | 3,47× |
| Ciro Gomes | 0,0261 | 0,5994 | 0,0398 | 0,66× |

### 2022, 2º turno — controle (porte: |φ| = 0,0664)

| candidato | \|φ_V\| | \|φ_S\| | esperado | **razão** |
|---|---|---|---|---|
| Jair Bolsonaro | 0,0740 | 0,3886 | 0,0258 | **2,87×** |
| Lula | 0,0187 | 0,5961 | 0,0396 | 0,47× |

### 2026, 2º turno — 100% (porte: |φ| = 0,0664)

| candidato | \|φ_V\| | \|φ_S\| | esperado | **razão** |
|---|---|---|---|---|
| Flávio Bolsonaro | 0,0856 | 0,4221 | 0,0280 | **3,05×** |
| Lula | 0,0173 | 0,5740 | 0,0381 | 0,45× |

A assinatura é **estável em quatro turnos e dois candidatos**: 2,93 / 2,87 /
2,88 / 3,05. A de Lula também: 0,49 / 0,47 / 0,65 / 0,45. O |φ_S| separa os
dois de forma consistente: ~0,41 contra ~0,56 — a distribuição de share do
Bolsonaro é mais concentrada em log, logo suaviza menos a base.

### Como ler isso

O `|φ_S|` de Flávio Bolsonaro (0,450) é menor que o de Lula (0,479): a
distribuição de share dele é mais concentrada em log, logo suaviza menos. E a
fase do share dele se alinha com a do porte em vez de cancelá-la. O resultado é
um excesso de municípios na faixa 1.000–1.999 votos.

**Advertência sobre a métrica:** a razão é inflada para candidatos pequenos
(|φ_S| → 0 quando o apoio é esparso — ver Zema 12,5×, D'Ávila/Eymael > 30×).
Ela só é comparável entre candidatos de porte parecido.

---

## 6. O que não foi testado

- **Dois últimos dígitos e duplicação ao nível de seção.** Exigem ≥ 4 dígitos
  significativos; votos por seção têm 2–3. O código agora recusa esses testes
  nessa faixa, em vez de reportar ruído.
- **Boletins de urna individuais** (`bweb_*.zip`, 1,3 GB só para SP). Comparar
  BU assinado contra totalização é a auditoria de verdade — Benford não é.
- Nenhum arquivo foi verificado contra os hashes SHA-512 publicados pelo TSE.
- O 2º turno vem da API de divulgação, não do CSV consolidado do portal. Os
  totais foram coletados com todos os municípios encerrados, mas ainda falta
  conferir contra o CSV quando ele sair.

---

## 7. O que Benford pode e não pode dizer aqui

Benford é um **filtro de atenção**, não evidência. Mesmo um desvio real e
inexplicado não provaria fraude; e sua ausência não provaria lisura — gerar
números conformes a Benford é uma linha de código.

A auditoria que de fato prova alguma coisa é outra: conferir o boletim de urna
impresso e assinado digitalmente contra o que entrou na totalização. Os BUs
estão públicos no mesmo portal.
