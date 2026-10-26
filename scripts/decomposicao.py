#!/usr/bin/env python3
"""Decomposicao de Fourier: separa o que e geografia do que e do candidato.

Para cada municipio m:   votos(c,m) = porte(m) * share(c,m)
Em log:                  log V = log P + log S

A funcao caracteristica de uma soma de variaveis INDEPENDENTES e o produto
das funcoes caracteristicas. Logo, sob independencia entre porte e share:

    |phi_V(2pi)| = |phi_P(2pi)| * |phi_S(2pi)|   <=   |phi_P(2pi)|

ou seja, o share so pode SUAVIZAR -- aproximar de Benford. Se a razao
observado/esperado for >> 1, porte e share estao acoplados na frequencia
2pi: o share nao suaviza, ele TRANSLADA a mantissa. Isso e uma assinatura
log-periodica da geografia eleitoral do candidato, e e exatamente o tipo
de estrutura que um teste de Benford ingenuo leria como "fraude".

Uso:  python3 decomposicao.py <csv_por_secao> <turno> <rotulo>
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

IDX = {"turno": 5, "uf": 10, "municipio": 13, "cargo": 17, "votavel": 19,
       "nome": 20, "votos": 21}


def phi(valores, k: int = 1) -> tuple[float, float, int]:
    ls = [math.log10(v) for v in valores if v > 0]
    n = len(ls)
    if n < 2:
        return 0.0, 0.0, n
    w = 2 * math.pi * k
    re = sum(math.cos(w * x) for x in ls) / n
    im = -sum(math.sin(w * x) for x in ls) / n
    return math.hypot(re, im), math.atan2(im, re), n


def carregar(caminho: Path, turno: str):
    mun: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    nomes: dict[str, str] = {}
    with open(caminho, encoding="latin-1", newline="") as fh:
        leitor = csv.reader(fh, delimiter=";", quotechar='"')
        next(leitor)
        for L in leitor:
            if len(L) <= IDX["votos"]:
                continue
            if L[IDX["cargo"]] != "1" or L[IDX["turno"]] != turno:
                continue
            # exterior fora; brancos (95) e nulos (96) fora: porte = votos validos,
            # a mesma definicao de historico.py e do 2o turno pela API
            if L[IDX["uf"]] == "ZZ" or int(L[IDX["votavel"]]) >= 95:
                continue
            try:
                v = int(L[IDX["votos"]])
            except ValueError:
                continue
            mun[L[IDX["municipio"]]][L[IDX["votavel"]]] += v
            nomes.setdefault(L[IDX["votavel"]], L[IDX["nome"]])
    return mun, nomes


def relatar(caminho: Path, turno: str, rotulo: str) -> str:
    mun, nomes = carregar(caminho, turno)
    muns = [m for m in sorted(mun) if sum(mun[m].values()) > 0]
    if not muns:
        return f"{rotulo}: sem dados para o turno {turno}\n"
    tot = {m: sum(mun[m].values()) for m in muns}
    base, fase_b, n = phi([tot[m] for m in muns])

    L = [f"### {rotulo}  (turno {turno}, {len(muns):,} municipios)",
         f"    porte municipal (votos validos): |phi(2pi)| = {base:.4f}  fase = {fase_b:+.3f}",
         "",
         f"    {'candidato':<26} {'|phi_V|':>8} {'|phi_S|':>8} "
         f"{'esperado':>9} {'razao':>7}  {'share':>6}",
         "    " + "-" * 70]

    ordem = sorted(nomes, key=lambda c: -sum(mun[m].get(c, 0) for m in muns))
    for nr in ordem:
        v = [mun[m].get(nr, 0) for m in muns]
        if sum(1 for x in v if x > 0) < 1000:
            continue
        s = [mun[m][nr] / tot[m] for m in muns if mun[m].get(nr, 0) > 0]
        pv, _fv, _ = phi([x for x in v if x > 0])
        ps, _fs, _ = phi(s)
        esp = base * ps
        razao = pv / esp if esp else 0.0
        marca = "  <<<" if razao > 2 else ""
        L.append(f"    {nomes[nr][:26]:<26} {pv:>8.4f} {ps:>8.4f} "
                 f"{esp:>9.4f} {razao:>6.2f}x  {sum(s)/len(s):>5.3f}{marca}")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    print(relatar(Path(sys.argv[1]), sys.argv[2], sys.argv[3]))
