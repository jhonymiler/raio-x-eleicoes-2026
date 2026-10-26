"""Suite de testes de Benford e forense numerica, em stdlib puro.

Implementa, na ordem em que devem ser usados:
  - gate de aplicabilidade (sigma em decadas via criterio de Fourier)
  - primeiro digito, dois primeiros digitos, segundo digito (2BL)
  - estatisticas: chi2 (+p), MAD, Kuiper V (+p), z por digito
  - invariancia de soma
  - uniformidade dos dois ultimos digitos
  - duplicacao de valores

Referencia teorica em ../docs/benford-teoria.md
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

LOG10 = math.log(10.0)


# --------------------------------------------------------------------------
# distribuicoes esperadas
# --------------------------------------------------------------------------

def p_primeiro_digito() -> dict[int, float]:
    return {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def p_dois_primeiros() -> dict[int, float]:
    return {n: math.log10(1 + 1 / n) for n in range(10, 100)}


def p_segundo_digito() -> dict[int, float]:
    """P(D2=d) = sum_{j=1..9} log10(1 + 1/(10j+d)). Quase uniforme."""
    return {d: sum(math.log10(1 + 1 / (10 * j + d)) for j in range(1, 10))
            for d in range(10)}


# --------------------------------------------------------------------------
# extracao de digitos
# --------------------------------------------------------------------------

def primeiro_digito(x: float) -> int | None:
    x = abs(x)
    if x <= 0:
        return None
    d = int(str(int(x)) [0]) if x >= 1 else None
    if d is None:                      # 0 < x < 1
        s = f"{x:.17e}"
        d = int(s[0])
    return d or None


def dois_primeiros(x: float) -> int | None:
    """Retorna 10..99, ou None se |x| < 10 (nao ha dois digitos significativos
    confiaveis em contagens inteiras pequenas)."""
    x = abs(x)
    if x < 10:
        return None
    s = str(int(x))
    return int(s[:2])


def segundo_digito(x: float) -> int | None:
    x = abs(x)
    if x < 10:
        return None
    return int(str(int(x))[1])


def dois_ultimos(x: float) -> int | None:
    """So faz sentido com pelo menos 4 digitos significativos.

    Em contagens de 100 a 400 (votos por secao) os dois ultimos digitos
    herdam a forma da distribuicao e o teste de uniformidade rejeita
    sempre -- sem que isso signifique nada. Nigrini aplica o teste a
    valores com >= 4 digitos; e o que fazemos aqui.
    """
    x = abs(x)
    if x < 1000:
        return None
    return int(x) % 100


def mantissa(x: float) -> float | None:
    """Parte fracionaria de log10(x) -- o objeto real da lei."""
    x = abs(x)
    if x <= 0:
        return None
    return math.log10(x) % 1.0


# --------------------------------------------------------------------------
# funcoes especiais (chi2 e Kuiper sem scipy)
# --------------------------------------------------------------------------

def _gammainc_q(a: float, x: float) -> float:
    """Q(a,x) = gama incompleta superior regularizada. Serie + fracao continua."""
    if x < 0 or a <= 0:
        raise ValueError("dominio invalido")
    if x == 0:
        return 1.0
    if x < a + 1.0:                                     # serie para P(a,x)
        ap, s, termo = a, 1.0 / a, 1.0 / a
        for _ in range(1000):
            ap += 1
            termo *= x / ap
            s += termo
            if abs(termo) < abs(s) * 1e-15:
                break
        return 1.0 - s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # fracao continua de Lentz para Q(a,x)
    tiny = 1e-300
    b, c, d = x + 1.0 - a, 1.0 / tiny, 1.0 / (x + 1.0 - a)
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(stat: float, df: int) -> float:
    """P(X2 > stat). Cauda superior."""
    if stat <= 0:
        return 1.0
    return _gammainc_q(df / 2.0, stat / 2.0)


def kuiper_sf(v: float, n: int) -> float:
    """p-valor assintotico de Kuiper (Stephens 1970)."""
    if n <= 0:
        return 1.0
    lam = (math.sqrt(n) + 0.155 + 0.24 / math.sqrt(n)) * v
    if lam < 0.4:
        return 1.0
    s = 0.0
    for k in range(1, 101):
        t = 2.0 * k * k * lam * lam
        s += 2.0 * (2.0 * t - 1.0) * math.exp(-t)
        if t > 300:
            break
    return max(0.0, min(1.0, s))


def erfc(x: float) -> float:
    return math.erfc(x)


def z_bicaudal(z: float) -> float:
    return erfc(abs(z) / math.sqrt(2.0))


# --------------------------------------------------------------------------
# resultado de um teste
# --------------------------------------------------------------------------

@dataclass
class Resultado:
    nome: str
    n: int
    observado: dict
    esperado_prob: dict
    chi2: float = 0.0
    gl: int = 0
    p_chi2: float = 1.0
    mad: float = 0.0
    kuiper_v: float = 0.0
    p_kuiper: float = 1.0
    z_por_bin: dict = field(default_factory=dict)
    nota: str = ""

    def desvios(self, top: int = 10) -> list[tuple]:
        """Bins ordenados por |z| decrescente."""
        linhas = []
        for b, z in self.z_por_bin.items():
            obs = self.observado.get(b, 0)
            esp = self.esperado_prob[b] * self.n
            linhas.append((b, obs, esp, (obs - esp) / self.n * 100, z))
        linhas.sort(key=lambda r: -abs(r[4]))
        return linhas[:top]


def avaliar(nome: str, valores, extrator, probs: dict,
            usar_kuiper: bool = False) -> Resultado:
    """Conta digitos, compara com `probs`, devolve todas as estatisticas."""
    cont = Counter()
    n = 0
    for v in valores:
        b = extrator(v)
        if b is None or b not in probs:
            continue
        cont[b] += 1
        n += 1
    if n == 0:
        return Resultado(nome, 0, {}, probs, nota="sem dados elegiveis")

    chi2 = 0.0
    mad = 0.0
    zs: dict = {}
    for b, p in probs.items():
        esp = p * n
        obs = cont.get(b, 0)
        chi2 += (obs - esp) ** 2 / esp
        mad += abs(obs / n - p)
        # z de proporcao com correcao de continuidade
        se = math.sqrt(p * (1 - p) / n)
        corr = 1 / (2 * n)
        num = abs(obs / n - p)
        num = num - corr if num > corr else 0.0
        zs[b] = (num / se) * (1 if obs / n >= p else -1)
    mad /= len(probs)
    gl = len(probs) - 1

    return Resultado(nome, n, dict(cont), probs,
                     chi2=chi2, gl=gl, p_chi2=chi2_sf(chi2, gl),
                     mad=mad, z_por_bin=zs)


def kuiper_mantissa(valores) -> tuple[float, float, int]:
    """Kuiper V sobre a mantissa -- o teste geometricamente correto.

    Invariante a rotacao do circulo, logo invariante a mudanca de unidade.
    """
    ms = sorted(m for m in (mantissa(v) for v in valores) if m is not None)
    n = len(ms)
    if n < 2:
        return 0.0, 1.0, n
    dplus = max((i + 1) / n - m for i, m in enumerate(ms))
    dminus = max(m - i / n for i, m in enumerate(ms))
    v = dplus + dminus
    return v, kuiper_sf(v, n), n


# --------------------------------------------------------------------------
# gate de aplicabilidade
# --------------------------------------------------------------------------

def sigma_decadas(valores) -> tuple[float, float, int]:
    """Desvio-padrao de log10(x) e o desvio de Benford previsto por Fourier
    SOB HIPOTESE LOGNORMAL.

    Para log10(X) ~ N(mu, sigma^2), |phi(2*pi)| = exp(-2*pi^2*sigma^2) e o
    desvio maximo na CDF da mantissa fica ~= 2*exp(-2*pi^2*sigma^2)/(2*pi).

    ATENCAO: se os dados nao forem lognormais esta previsao e otimista
    demais. Use `fourier_empirico`, que nao assume distribuicao nenhuma.
    """
    ls = [math.log10(abs(v)) for v in valores if v and abs(v) > 0]
    n = len(ls)
    if n < 2:
        return 0.0, 1.0, n
    mu = sum(ls) / n
    var = sum((x - mu) ** 2 for x in ls) / (n - 1)
    sd = math.sqrt(var)
    desvio = 2 * math.exp(-2 * math.pi ** 2 * var) / (2 * math.pi)
    return sd, desvio, n


def fourier_empirico(valores, kmax: int = 3) -> dict:
    """Criterio EXATO de Benford, estimado dos proprios dados.

    X e Benford  <=>  phi_{log10 X}(2*pi*k) = 0 para todo k != 0.

    Estima |phi(2*pi*k)| = |media de exp(-2*pi*i*k*log10(x))| direto da
    amostra -- sem supor lognormal, nem nada. Devolve tambem:

      ruido : |phi| esperado por acaso numa amostra Benford de tamanho n,
              que e ~sqrt(1/n) (passeio aleatorio no plano complexo).
      excesso_k1 : |phi(2pi)| / ruido. Se ~1, a amostra e indistinguivel
              de Benford. Se >> 1, a PROPRIA FORMA da distribuicao e
              nao-Benford -- e o desvio observado nos digitos nao e
              evidencia de manipulacao, e evidencia de que o dado nunca
              deveria ter sido Benford.
      desvio_previsto : limite superior do desvio na CDF da mantissa,
              sum_k 2|phi(2pi k)| / (pi*k), em pontos percentuais
              (o fator 2 soma os termos -k, conjugados dos +k).
    """
    ls = [math.log10(abs(v)) for v in valores if v and abs(v) > 0]
    n = len(ls)
    if n < 2:
        return {"n": n, "phi": {}, "ruido": 1.0, "excesso_k1": 0.0,
                "desvio_previsto": 100.0}
    phi = {}
    for k in range(1, kmax + 1):
        re = im = 0.0
        w = 2 * math.pi * k
        for x in ls:
            a = w * x
            re += math.cos(a)
            im -= math.sin(a)
        phi[k] = math.hypot(re / n, im / n)
    ruido = math.sqrt(1.0 / n)
    desvio = sum(2 * phi[k] / (math.pi * k) for k in phi) * 100
    return {"n": n, "phi": phi, "ruido": ruido,
            "excesso_k1": phi[1] / ruido if ruido else 0.0,
            "desvio_previsto": desvio}


# --------------------------------------------------------------------------
# testes complementares
# --------------------------------------------------------------------------

def invariancia_soma(valores) -> dict[int, float]:
    """Num conjunto Benford, a SOMA por primeiro digito e ~constante.
    Devolve a fracao do total por digito (esperado ~1/9 = 0.1111 cada)."""
    somas = Counter()
    for v in valores:
        d = primeiro_digito(v)
        if d:
            somas[d] += abs(v)
    total = sum(somas.values()) or 1.0
    return {d: somas.get(d, 0) / total for d in range(1, 10)}


def uniformidade_dois_ultimos(valores) -> Resultado:
    """Os DOIS ULTIMOS digitos devem ser UNIFORMES (nao Benford).
    Picos em 00/50 revelam arredondamento, invencao ou limiar."""
    probs = {k: 1 / 100 for k in range(100)}
    return avaliar("dois ultimos digitos (uniforme)", valores, dois_ultimos, probs)


def duplicacao(valores, top: int = 15) -> tuple[list[tuple], float]:
    """Valores exatos mais repetidos e a fracao que eles representam."""
    c = Counter(v for v in valores if v and v > 0)
    total = sum(c.values()) or 1
    mais = c.most_common(top)
    return mais, sum(q for _, q in mais) / total


# --------------------------------------------------------------------------
# limiares de Nigrini para MAD (calibrados em dados contabeis)
# --------------------------------------------------------------------------

LIMIARES_MAD = {
    "primeiro digito":      [(0.0060, "conformidade proxima"),
                             (0.0120, "aceitavel"),
                             (0.0150, "marginal"),
                             (float("inf"), "NAO CONFORMIDADE")],
    "dois primeiros":       [(0.0012, "conformidade proxima"),
                             (0.0018, "aceitavel"),
                             (0.0022, "marginal"),
                             (float("inf"), "NAO CONFORMIDADE")],
    "segundo digito":       [(0.0080, "conformidade proxima"),
                             (0.0100, "aceitavel"),
                             (0.0120, "marginal"),
                             (float("inf"), "NAO CONFORMIDADE")],
}


def classificar_mad(mad: float, tipo: str) -> str:
    for limite, rotulo in LIMIARES_MAD.get(tipo, LIMIARES_MAD["primeiro digito"]):
        if mad < limite:
            return rotulo
    return "?"
