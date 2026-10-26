#!/usr/bin/env python3
"""Totais finais do 2o turno por municipio: aptos, comparecimento, brancos,
nulos, Lula e Flavio, pela API de divulgacao do TSE.

coletar_2t.py so guarda os candidatos (brancos e nulos ficam dentro de "v"
no JSON, e o comparecimento em "e"); este script guarda os totais, num
arquivo separado para nao mudar o que o painel ao vivo le.

Saida: dados/totais_2t_municipio_<cd>.csv
Uso:   python3 scripts/totais_2t.py [cd_eleicao]      (padrao 6258)
"""

from __future__ import annotations

import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from coletar_2t import BASE, Bloqueado, municipios, pegar  # noqa: E402

RAIZ = Path(__file__).parent.parent
CAMPOS = ["uf", "cd_municipio", "nm_municipio", "encerrada", "secoes_tot", "secoes",
          "aptos", "comparecimento", "brancos", "nulos", "lula", "flavio"]


def totais(args) -> dict | None:
    cd, uf, mun, nome = args
    try:
        d = pegar(f"{BASE}/{cd}/dados/{uf}/{uf}{mun}-c0001-e00{cd}-u.json")
    except Bloqueado:
        return None
    if not d:
        return None
    e, v, s = d.get("e", {}), d.get("v", {}), d.get("s", {})
    votos = {c.get("n"): int(c.get("vap") or 0)
             for agr in (d.get("carg") or [{}])[0].get("agr", [])
             for par in agr.get("par", []) for c in par.get("cand", [])}
    return {"uf": uf.upper(), "cd_municipio": mun, "nm_municipio": nome,
            "encerrada": d.get("tf") == "s", "secoes_tot": int(s.get("st") or 0),
            "secoes": int(s.get("ts") or 0), "aptos": int(e.get("te") or 0),
            "comparecimento": int(e.get("c") or 0), "brancos": int(v.get("vb") or 0),
            "nulos": int(v.get("tvn") or 0), "lula": votos.get("13", 0), "flavio": votos.get("22", 0)}


NOMES = {"13": "LULA", "22": "FLAVIO BOLSONARO"}


def ler(cd: str = "6258", exterior: bool = False):
    """Totais finais do 2T em linhas no formato de resultado_2t_municipio
    (uf, cd_municipio, nm_municipio, nr_votavel, nm_votavel, qt_votos) e
    um meta de totalizacao calculado dos proprios municipios."""
    linhas, sec_tot, sec, enc, n = [], 0, 0, 0, 0
    with open(RAIZ / f"dados/totais_2t_municipio_{cd}.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not exterior and r["uf"] == "ZZ":
                continue
            n += 1
            sec_tot += int(r["secoes_tot"])
            sec += int(r["secoes"])
            enc += r["encerrada"] == "True"
            for nr, col in (("13", "lula"), ("22", "flavio")):
                linhas.append({"uf": r["uf"], "cd_municipio": r["cd_municipio"],
                               "nm_municipio": r["nm_municipio"], "nr_votavel": nr,
                               "nm_votavel": NOMES[nr], "qt_votos": int(r[col])})
    meta = {"cd_eleicao": cd, "fonte": f"totais_2t_municipio_{cd}.csv",
            "secoes_totalizadas": sec_tot, "secoes_esperadas": sec,
            "pct_totalizado": f"{sec_tot / sec * 100:.2f}".replace(".", ",") if sec else "0",
            "municipios": n, "municipios_encerrados": enc,
            "totalizacao_encerrada": n > 0 and enc == n}
    return linhas, meta


def main(cd: str = "6258") -> None:
    muns = municipios(cd)
    print(f"{len(muns)} municipios", flush=True)
    linhas, falhas = [], 0
    with ThreadPoolExecutor(4) as ex:
        for i, r in enumerate(ex.map(totais, [(cd, *m) for m in muns]), 1):
            if r:
                linhas.append(r)
            else:
                falhas += 1
            if i % 1000 == 0:
                print(f"  {i}/{len(muns)}", flush=True)
    saida = RAIZ / f"dados/totais_2t_municipio_{cd}.csv"
    with open(saida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(linhas)
    print(f"-> {saida.relative_to(RAIZ)}: {len(linhas)} municipios, {falhas} falhas, "
          f"{sum(r['encerrada'] for r in linhas)} encerrados")


if __name__ == "__main__":
    main(*sys.argv[1:2])
