#!/usr/bin/env python3
"""Pista da biometria: o voto a mais no Lula nas secoes com muita liberacao
sem digital e fraude (mesario votando por ausentes) ou idade (digital
gasta e mais comum em idosos, e idosos se moveram menos para a direita)?

Regressao DENTRO de cada escola (local de votacao): a variavel resposta e a
mudanca do residuo do Lula de 2022 para 2026 (secao menos as vizinhas de
escola). Regressores, todos como desvio da media da propria escola:
  taxa de liberacao sem digital (do BU), % de eleitores 60+, % com
  superior completo, % sem biometria cadastrada (do perfil do eleitorado).
Se o coeficiente da liberacao some com a idade no modelo, a pista se
explica pela composicao etaria; se sobrevive, fica em aberto.

Entradas: dados/eleitorado/perfil_eleitor_secao_ATUAL_<UF>.zip,
          dados/eleitorado/eleitorado_local_votacao_2026.zip (tipo do local)
Saida:    resultados/idade_biometria.json, dados/derivados/perfil_secao.csv.gz

Uso:  python3 scripts/idade_biometria.py
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import sys
import zipfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import aprofundar as ap  # noqa: E402

RAIZ = Path(__file__).parent.parent
EL = RAIZ / "dados" / "eleitorado"


def perfil_uf(caminho: str) -> dict:
    z = zipfile.ZipFile(caminho)
    out: dict = defaultdict(lambda: [0, 0, 0, 0, 0])  # total, 60+, 70+, superior, com biometria
    for nome in (n for n in z.namelist() if n.endswith(".csv")):
        with io.TextIOWrapper(z.open(nome), encoding="latin-1", newline="") as fh:
            rd = csv.reader(fh, delimiter=";")
            i = {c: n for n, c in enumerate(next(rd))}
            for L in rd:
                k = (L[i["SG_UF"]], L[i["CD_MUNICIPIO"]], L[i["NR_ZONA"]], L[i["NR_SECAO"]])
                q = int(L[i["QT_ELEITORES"]])
                idade = L[i["DS_FAIXA_ETARIA"]].strip()[:3].strip()
                idade = int(idade) if idade.isdigit() else 0
                s = out[k]
                s[0] += q
                s[1] += q if idade >= 60 else 0
                s[2] += q if idade >= 70 else 0
                s[3] += q if L[i["DS_GRAU_INSTRUCAO"]].startswith("SUPERIOR COMPLETO") else 0
                s[4] += int(L[i["QT_ELEITORES_BIOMETRIA"]])
    return dict(out)


def tipos_local() -> dict:
    z = zipfile.ZipFile(EL / "eleitorado_local_votacao_2026.zip")
    out = {}
    for nome in (n for n in z.namelist() if n.endswith(".csv")):
        with io.TextIOWrapper(z.open(nome), encoding="latin-1", newline="") as fh:
            for L in csv.DictReader(fh, delimiter=";"):
                if L["NR_TURNO"] != "1":
                    continue
                out[(L["SG_UF"], L["CD_MUNICIPIO"], L["NR_ZONA"], L["NR_SECAO"])] = (
                    L["DS_TIPO_LOCAL"], L["NM_LOCAL_VOTACAO"], L["DS_SITU_LOCALIDADE"])
    return out


def ols(y, xs) -> list[dict]:
    """MQO sem intercepto (dados ja centrados na escola), erro-padrao robusto HC1."""
    k, n = len(xs), len(y)
    xtx = [[sum(xs[a][t] * xs[b][t] for t in range(n)) for b in range(k)] for a in range(k)]
    xty = [sum(xs[a][t] * y[t] for t in range(n)) for a in range(k)]
    inv = inverter(xtx)
    beta = [sum(inv[a][b] * xty[b] for b in range(k)) for a in range(k)]
    res = [y[t] - sum(beta[a] * xs[a][t] for a in range(k)) for t in range(n)]
    meat = [[sum(xs[a][t] * xs[b][t] * res[t] ** 2 for t in range(n)) for b in range(k)]
            for a in range(k)]
    cov = mult(mult(inv, meat), inv)
    corr = n / (n - k)
    return [{"coef": beta[a], "ep": math.sqrt(cov[a][a] * corr),
             "z": beta[a] / math.sqrt(cov[a][a] * corr)} for a in range(k)]


def inverter(m):
    n = len(m)
    a = [row[:] + [float(i == j) for j in range(n)] for i, row in enumerate(m)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        a[c], a[p] = a[p], a[c]
        pv = a[c][c]
        a[c] = [x / pv for x in a[c]]
        for r in range(n):
            if r != c:
                f = a[r][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return [row[n:] for row in a]


def mult(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))]
            for i in range(len(a))]


def main() -> None:
    zips = sorted(map(str, EL.glob("perfil_eleitor_secao_ATUAL_*.zip")))
    perfil: dict = {}
    with ProcessPoolExecutor(8) as ex:
        loc_fut = ex.submit(tipos_local)
        for p in ex.map(perfil_uf, zips):
            perfil.update(p)
        locais = loc_fut.result()
    print(f"perfil: {len(perfil):,} secoes; locais: {len(locais):,}", flush=True)
    with gzip.open(RAIZ / "dados/derivados/perfil_secao.csv.gz", "wt", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["uf", "mun", "zona", "secao", "eleitores", "idade60", "idade70",
                    "superior", "com_biometria", "tipo_local", "local", "localidade"])
        for k, v in perfil.items():
            w.writerow([*k, *v, *locais.get(k, ("", "", ""))])

    s26, s22 = ap.carregar_2026(), ap.carregar_2022()
    r26 = {k: s["res"] for k, s in s26.items() if s["res"] is not None}
    r22 = ap.residuos(s22, lambda s: s["local"])

    linhas = []
    for k in r26.keys() & r22.keys() & perfil.keys():
        s, p = s26[k], perfil[k]
        if s["comp"] < 50 or p[0] < 50 or s["biom"] < 0:
            continue
        linhas.append({"k": k, "esc": k[:3] + (s["local"],), "dy": r26[k] - r22[k],
                       "y26": r26[k], "biom": s["biom"] / s["comp"], "i60": p[1] / p[0],
                       "sup": p[3] / p[0], "semb": 1 - p[4] / p[0]})
    # centraliza cada variavel na media da propria escola
    grupos = defaultdict(list)
    for L in linhas:
        grupos[L["esc"]].append(L)
    for g in grupos.values():
        for v in ("biom", "i60", "sup", "semb"):
            m = sum(L[v] for L in g) / len(g)
            for L in g:
                L["c_" + v] = L[v] - m
    linhas = [L for L in linhas if len(grupos[L["esc"]]) >= 3]
    print(f"secoes no modelo: {len(linhas):,}", flush=True)

    y = [L["dy"] for L in linhas]
    col = lambda v: [L["c_" + v] for L in linhas]
    modelos = {
        "so_biometria": dict(zip(["biom"], ols(y, [col("biom")]))),
        "biometria_idade": dict(zip(["biom", "i60"], ols(y, [col("biom"), col("i60")]))),
        "completo": dict(zip(["biom", "i60", "sup", "semb"],
                             ols(y, [col("biom"), col("i60"), col("sup"), col("semb")]))),
    }
    # quanto a idade explica da liberacao sem digital (dentro da escola)
    b_ib = ols(col("biom"), [col("i60")])[0]
    out = {"secoes": len(linhas), "modelos": modelos, "biom_por_idade": b_ib}
    (RAIZ / "resultados/idade_biometria.json").write_text(json.dumps(out, ensure_ascii=False))
    for nome, m in modelos.items():
        print(f"{nome:<16} " + "  ".join(
            f"{v}: {c['coef']*100:+.2f}pp por 100% (z={c['z']:+.1f})" for v, c in m.items()))
    print(f"liberacao sem digital ~ idade60: coef={b_ib['coef']:+.3f} z={b_ib['z']:+.1f}")


if __name__ == "__main__":
    main()
