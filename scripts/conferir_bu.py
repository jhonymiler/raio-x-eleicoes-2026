#!/usr/bin/env python3
"""Confere o boletim de urna (BU) de cada secao contra a totalizacao.

BU   : dados/bu/bweb_<turno>t_<UF>_*.csv  (buweb do TSE, um registro por
       secao x votavel, transcrito do BU que a urna imprime e assina)
Total: dados/votacao_secao_2026_BR.csv    (o que entrou no resultado oficial)

Compara voto a voto, por (municipio, zona, secao, numero votado), no cargo
Presidente. Qualquer diferenca e listada.

O que isto prova: que nada mudou entre o BU de cada urna e o resultado
oficial (transmissao, soma, publicacao). O que NAO prova: que a urna
registrou corretamente o voto que o eleitor digitou -- isso nenhum dado
publicado consegue mostrar sem um registro em papel conferido pelo eleitor.

Uso:  python3 scripts/conferir_bu.py CE [turno]
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).parent.parent


def ler(caminho: Path, filtro, campo_cargo: str) -> Counter:
    c: Counter = Counter()
    with open(caminho, encoding="latin-1", newline="") as fh:
        for L in csv.DictReader(fh, delimiter=";"):
            if L[campo_cargo] != "1" or not filtro(L):
                continue
            c[(L["CD_MUNICIPIO"], L["NR_ZONA"], L["NR_SECAO"],
               L["NR_VOTAVEL"])] += int(L["QT_VOTOS"])
    return c


def main(uf: str, turno: str = "1") -> int:
    bu_csv = sorted((RAIZ / "dados" / "bu").glob(f"bweb_{turno}t_{uf}_*.csv"))[-1]
    bu = ler(bu_csv, lambda L: L["NR_TURNO"] == turno, "CD_CARGO_PERGUNTA")
    tot = ler(RAIZ / "dados" / "votacao_secao_2026_BR.csv",
              lambda L: L["SG_UF"] == uf and L["NR_TURNO"] == turno, "CD_CARGO")

    difs = [(k, bu.get(k, 0), tot.get(k, 0)) for k in bu.keys() | tot.keys()
            if bu.get(k, 0) != tot.get(k, 0)]
    secoes = {k[:3] for k in bu} | {k[:3] for k in tot}
    por_votavel = defaultdict(lambda: [0, 0])
    for k, v in bu.items():
        por_votavel[k[3]][0] += v
    for k, v in tot.items():
        por_votavel[k[3]][1] += v

    print(f"{uf} {turno}o turno, Presidente — {bu_csv.name}")
    print(f"  secoes: {len({k[:3] for k in bu}):,} no BU, "
          f"{len({k[:3] for k in tot}):,} na totalizacao ({len(secoes):,} na uniao)")
    print(f"  registros secao x votavel: {len(bu):,} BU, {len(tot):,} totalizacao")
    print(f"  {'votavel':>8} {'BU':>12} {'totalizacao':>12}")
    for nr, (a, b) in sorted(por_votavel.items(), key=lambda x: -x[1][0]):
        print(f"  {nr:>8} {a:>12,} {b:>12,}{'  <<<' if a != b else ''}")
    print(f"  DIFERENCAS: {len(difs)}")
    for k, a, b in sorted(difs)[:30]:
        print(f"    mun {k[0]} zona {k[1]} secao {k[2]} votavel {k[3]}: BU={a} total={b}")
    return 1 if difs else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1].upper(), *sys.argv[2:3]))
