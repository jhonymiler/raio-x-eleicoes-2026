# A lei de Benford — teoria, mecanismo e uso forense

Material de referência do projeto. A implementação está em
[`scripts/benford.py`](../scripts/benford.py).

---

## 1. Como se chegou nela

**Simon Newcomb, 1881.** Astrônomo, usava tábuas de logaritmos impressas.
Notou que as primeiras páginas — números começando com 1 — estavam muito mais
gastas que as finais. Chutou a fórmula P(d) = log₁₀(1 + 1/d) a partir do
desgaste, publicou duas páginas sem demonstração, e ninguém ligou.

**Frank Benford, 1938.** Físico da GE, redescobriu o mesmo desgaste. Foi atrás
de dados: ~20.000 números de 20 fontes sem relação entre si — áreas de rios,
populações, constantes físicas, endereços, pesos atômicos. Todos batiam com a
mesma curva. Virou "lei de Benford" pelo volume empírico, não pela prioridade.

---

## 2. O objeto certo não é o dígito, é a mantissa

Para x > 0, o **significando** é

$$S(x) = x \cdot 10^{-\lfloor \log_{10} x \rfloor} \in [1,10)$$

O primeiro dígito é só ⌊S(x)⌋ — uma discretização grosseira. A lei forte é a
**lei do significando**:

$$P(S(X) \le t) = \log_{10} t, \quad t \in [1,10)$$

Daí sai qualquer enunciado sobre dígitos, por diferença:

| teste | distribuição esperada |
|---|---|
| primeiro dígito | log₁₀(1 + 1/d), d = 1..9 |
| dois primeiros | log₁₀(1 + 1/n), n = 10..99 |
| segundo dígito | Σⱼ₌₁⁹ log₁₀(1 + 1/(10j+d)) — de 0,1197 (d=0) a 0,0850 (d=9) |
| terceiro em diante | uniforme até ~10⁻³ |

Os dígitos **não são independentes**, mas a dependência decai rápido. Por isso
testes sérios usam os **dois primeiros** dígitos: máxima informação antes do
sinal sumir.

Equivalentemente, com M = {log₁₀ X} (parte fracionária), a lei inteira é uma
frase só: **M ~ Uniforme[0,1)**. Todo o resto é consequência.

---

## 3. Os três teoremas de invariância

**(a) Invariância de escala** — Pinkham, 1961. Se existe uma lei de dígitos
invariante sob X ↦ cX para todo c > 0, ela é Benford. Multiplicar por c
translada M por log c mod 1 — uma rotação no círculo; a única medida de
probabilidade invariante por toda rotação é a uniforme (Haar).

**(b) Invariância de base** — Hill, 1995. Mais forte: se a lei dos
significandos é a mesma em base 10, 2, 7, …, então ou é Benford ou é a
degenerada em S = 1. Não supõe nada sobre escala.

**(c) Invariância de soma** — Allaart, 1997. Num conjunto Benford, a **soma**
das entradas com primeiro dígito d é aproximadamente a mesma para todo d. Há
6,5× mais números começando com 1, mas os com 9 são ~6,5× maiores. É um teste
de auditoria subutilizado: pega poucas faturas infladas, que a contagem dilui.

---

## 4. O mecanismo real: Fourier na mantissa

Seja Y = log₁₀ X, com densidade f_Y em ℝ. A densidade de M = {Y} em [0,1) é o
*wrapping* f_M(m) = Σₖ f_Y(m + k). O k-ésimo coeficiente de Fourier é

$$\hat{c}_k = \int_0^1 e^{-2\pi i k m} f_M(m)\,dm = \varphi_Y(-2\pi k)$$

onde φ_Y é a função característica de Y. Como ĉ₀ = 1 sempre:

> **X é exatamente Benford ⟺ φ_{log₁₀X}(2πk) = 0 para todo inteiro k ≠ 0.**

Benford deixa de ser folclore e vira uma condição pontual sobre a transformada
de Fourier do log. O desvio sai de graça:

$$\sup_m |F_M(m) - m| \;\le\; \sum_{k \neq 0} \frac{|\varphi_Y(2\pi k)|}{2\pi |k|}$$

quase sempre dominado por k = ±1.

**É isto que o projeto usa como gate** (`bf.fourier_empirico`): estima
|φ(2πk)| direto da amostra, sem supor distribuição nenhuma, e compara com o
ruído amostral √(1/n). Excesso ≫ 1 significa que a *forma do próprio dado* não
é Benford — e aí desvio nos dígitos não é evidência de nada.

### Por que processos multiplicativos convergem

Se X = ∏ᵢ Xᵢ então Y = Σᵢ log Xᵢ e **φ_Y = ∏ᵢ φᵢ**. Cada |φᵢ(2π)| ≤ 1, e é
estritamente < 1 a menos que log Xᵢ viva num reticulado. O produto decai
**geometricamente no número de fatores**. Não é "o TCL espalha o log" — é
melhor: a convergência é exponencialmente rápida e não precisa de normalidade.

**Corolário usado neste projeto:** se V = P · S com P e S independentes, então
|φ_V| = |φ_P| · |φ_S| ≤ |φ_P|. Um fator multiplicativo independente **só pode
aproximar de Benford**. Observar |φ_V| > |φ_P| prova acoplamento na frequência
2π. Ver [`scripts/decomposicao.py`](../scripts/decomposicao.py).

### Quantificando: quando um dado é "Benford o bastante"

Para log₁₀X ~ N(μ, σ²), com σ em **décadas**: |φ(2π)| = e^(−2π²σ²).

| σ (décadas) | desvio ≈ 2e^(−2π²σ²) |
|---|---|
| 0,25 | 0,58 — nada Benford |
| 0,50 | 1,5 × 10⁻² |
| 0,75 | 3,0 × 10⁻⁵ |
| 1,00 | 5,5 × 10⁻⁹ |

Regra de bolso: **σ ≳ 0,5 década ⇒ Benford dentro de 1,5%**; σ ≳ 1 ⇒ Benford
para qualquer efeito prático.

> **Armadilha confirmada neste projeto.** Essa tabela supõe lognormalidade. Nos
> dados do TSE, σ = 0,57 décadas previa desvio de 0,05 pp, e o desvio observado
> foi ~100× maior — porque a distribuição não é lognormal. **Use sempre o φ
> empírico, nunca o gate lognormal.**

**Pareto / lei de potência** com índice α: |φ(2πk)| ≈ α/(2π|k|). Caudas pesadas
são Benford; caudas leves, não. **Exponencial:** não é Benford, desvio máximo
~3 pp — perto o bastante para enganar um teste fraco.

---

## 5. O teorema de Hill, com precisão

Seja uma distribuição de probabilidade sobre o espaço de distribuições em
(0,∞), **não-atômica**. Amostre m distribuições dela, depois n amostras de
cada. Então, com probabilidade 1, a distribuição dos significandos da amostra
combinada **converge para Benford** quando m, n → ∞.

Benford é o **ponto fixo** da mistura aleatória de distribuições — o análogo,
no grupo multiplicativo das mantissas, do que a normal é para somas. É
literalmente o experimento do Benford, formalizado 57 anos depois.

**Corolário determinístico:** 2ⁿ, Fibonacci e n! são *exatamente* Benford, por
Weyl — log₁₀2 é irracional, logo {n log₁₀2} é equidistribuída. Sem
aleatoriedade nenhuma.

---

## 6. Testar na prática

### O problema do N

χ² com 9 ou 90 bins **rejeita qualquer dataset real** quando N é grande, porque
nenhum dado empírico é exatamente Benford. Com N = 10⁶, 0,1 pp de desvio dá
p < 10⁻¹⁰. O teste responde "é exatamente Benford?" (sempre não) quando a
pergunta é "é anomalamente não-Benford?".

### O que usar

**Kuiper (V).** A mantissa vive num *círculo*; Kolmogorov–Smirnov depende do
ponto de corte, Kuiper não — é invariante a rotação, logo a mudança de unidade.
É o teste geometricamente correto e raramente é o usado.

**MAD** (Nigrini). Sem distribuição amostral, mas insensível a N. Limiares para
os dois primeiros dígitos: < 0,0012 conformidade próxima · 0,0012–0,0018
aceitável · 0,0018–0,0022 marginal · > 0,0022 não-conformidade. São
heurísticos, calibrados em dados contábeis — não transportar sem recalibrar.

**z por dígito**, com correção de continuidade, para apontar *qual* bin está
anômalo. É isso que direciona a investigação.

### A bateria do Nigrini, em ordem

1. **Primeiro dígito** — triagem grossa, baixa potência.
2. **Dois primeiros dígitos** — o teste principal, 90 bins.
3. **Invariância de soma** — pega valores grandes inflados.
4. **Últimos dois dígitos** — devem ser *uniformes*, não Benford. Só faz
   sentido com ≥ 4 dígitos significativos (ver aviso em `bf.dois_ultimos`).
5. **Duplicação** — valores repetidos exatos. Não é Benford, mas é onde a
   fraude costuma estar.

---

## 7. Falsos positivos — o que separa uso competente de teatro

Benford falha legitimamente, sem fraude nenhuma, quando:

- **Há limiar institucional.** Alçada em R$ 5.000 gera pico em "49". É *gaming*
  de política, não falsificação.
- **Números atribuídos.** CPF, nota fiscal, CEP. São rótulos, não medidas.
- **Preços psicológicos.** 19,99 / 99,00.
- **Faixa estreita.** σ < 0,3 década. Salários de uma função, notas, alturas —
  **e votos por seção eleitoral**.
- **Dados truncados ou filtrados.** "Transações acima de 1.000" enviesa.
- **Apuração parcial.** Mistura unidades completas com incompletas.

E o limite fundamental: **um fraudador que conhece Benford conforma
trivialmente**. Gerar números Benford é uma linha de código. A lei detecta
invenção *ingênua*. É um **filtro de atenção**, nunca evidência.

Tribunais e campanhas que trataram Benford como prova de fraude eleitoral
produziram conclusões ruins — justamente porque contagens de seção têm faixa
estreita demais e por construção não deveriam ser Benford. Ver
[`resultados/RELATORIO.md`](../resultados/RELATORIO.md), onde isso é medido.

---

## 8. Resumo operacional

1. O dado atravessa ≥ 2 ordens de grandeza? Se não, pare.
2. Calcule **|φ(2π)| empírico** e compare com √(1/n). Excesso ≫ 1 ⇒ a forma do
   dado não é Benford; desvio nos dígitos não significa nada.
3. Rode dois primeiros dígitos com MAD + Kuiper. Ignore χ² se N > ~10.000.
4. Rode invariância de soma e dois últimos dígitos — pegam coisas diferentes.
5. **Tenha um controle.** Uma variável que ninguém manipula, ou a mesma
   medição num período anterior. Sem controle, um desvio não é interpretável.
6. Desvio é **endereço de investigação**, não conclusão.
