#!/usr/bin/env python3
"""Viradas municipais anormais do voto no PT (numero 13) entre eleicoes.

1. Linha de base: quantos municipios viram de forma anormal (z robusto > 5
   dentro do estado E >= 5 pontos) em cada troca de eleicao desde 2002.
2. Espalhada x concentrada: nos municipios de 2026, quantas secoes
   seguiram a virada (manipulacao de urnas especificas deixaria secoes
   intactas ao lado de secoes alteradas).
3. Lider local: candidato a deputado/governador mais votado na cidade e
   seu peso no estado (um cacique local explica uma virada inteira).

Saida: resultados/viradas.json
Uso:   python3 scripts/viradas.py
"""

from __future__ import annotations

import csv
import glob
import gzip
import io
import json
import statistics as st
import sys
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import historico  # noqa: E402

RAIZ = Path(__file__).parent.parent
ANOS = [2002, 2006, 2010, 2014, 2018, 2022, 2026]


def share13(m, k):
    t = sum(m[k].values())
    return m[k].get("13", 0) / t if t else None


def anormais(ma, mb) -> list:
    por_uf = defaultdict(list)
    for k in mb:
        if k in ma:
            a, b = share13(ma, k), share13(mb, k)
            if a is not None and b is not None:
                por_uf[k[:2]].append((k, b - a))
    out = []
    for ls in por_uf.values():
        v = [x for _, x in ls]
        med = st.median(v)
        mad = st.median(abs(x - med) for x in v) * 1.4826
        out += [(k, x, med) for k, x in ls
                if mad and abs(x - med) / mad > 5 and abs(x - med) >= .05]
    return out


def lider_local(arg) -> list:
    uf, nomes = arg
    z = zipfile.ZipFile(glob.glob(str(RAIZ / f"dados/bu/bweb_1t_{uf}_*.zip"))[0])
    fh = io.TextIOWrapper(z.open(next(n for n in z.namelist() if n.endswith(".csv"))),
                          encoding="latin-1")
    rd = csv.reader(fh, delimiter=";")
    i = {c: n for n, c in enumerate(next(rd))}
    loc, uft, nm = defaultdict(Counter), defaultdict(Counter), {}
    for L in rd:
        cg = L[i["DS_CARGO_PERGUNTA"]]
        if cg not in ("Deputado Federal", "Deputado Estadual", "Governador"):
            continue
        nr, q = L[i["NR_VOTAVEL"]], int(L[i["QT_VOTOS"]])
        if nr in ("95", "96"):
            continue
        uft[cg][nr] += q
        if L[i["NM_MUNICIPIO"]] in nomes:
            loc[(L[i["NM_MUNICIPIO"]], cg)][nr] += q
            nm[(cg, nr)] = (L[i["NM_VOTAVEL"]], L[i["SG_PARTIDO"]])
    out = []
    for (mun, cg), c in sorted(loc.items()):
        nr, q = c.most_common(1)[0]
        out.append({"uf": uf, "municipio": mun, "cargo": cg, "candidato": nm[(cg, nr)][0],
                    "partido": nm[(cg, nr)][1], "share_cidade": q / sum(c.values()),
                    "share_estado": uft[cg][nr] / sum(uft[cg].values())})
    return out


def main() -> None:
    dados = {a: historico.carregar(a)[0] for a in ANOS}
    base = []
    for a, b in zip(ANOS, ANOS[1:]):
        an = anormais(dados[a], dados[b])
        base.append({"de": a, "para": b, "municipios": len(an),
                     "comparados": len(dados[b].keys() & dados[a].keys())})
        print(f"{a}->{b}: {len(an)}", flush=True)

    casos = anormais(dados[2022], dados[2026])
    alvo = {(k[:2], k[2:]) for k, _, _ in casos}
    # secao a secao
    s26, nomes = {}, {}
    with gzip.open(RAIZ / "dados/derivados/secoes_pres_1t_2026.csv.gz", "rt", encoding="utf-8") as fh:
        for L in csv.DictReader(fh, delimiter=";"):
            if (L["uf"], L["mun"]) in alvo:
                val = int(L["comp"]) - int(L["brancos"]) - int(L["nulos"])
                s26[(L["uf"], L["mun"], L["zona"], L["secao"])] = int(L["votos_13"]) / val if val else None
                nomes[(L["uf"], L["mun"])] = L["mun_nome"]
    s22 = defaultdict(lambda: [0, 0])
    with open(RAIZ / "dados/votacao_secao_2022_BR.csv", encoding="latin-1", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        i = {c: n for n, c in enumerate(next(rd))}
        for L in rd:
            if (L[i["CD_CARGO"]] != "1" or L[i["NR_TURNO"]] != "1" or
                    (L[i["SG_UF"]], L[i["CD_MUNICIPIO"]]) not in alvo):
                continue
            nr = L[i["NR_VOTAVEL"]]
            if nr in ("95", "96"):
                continue
            k = (L[i["SG_UF"]], L[i["CD_MUNICIPIO"]], L[i["NR_ZONA"]], L[i["NR_SECAO"]])
            s22[k][0] += int(L[i["QT_VOTOS"]])
            if nr == "13":
                s22[k][1] += int(L[i["QT_VOTOS"]])
    out_casos = []
    for k, x, med in casos:
        m = (k[:2], k[2:])
        dif = sorted(s26[s] - s22[s][1] / s22[s][0] for s in s26
                     if s[:2] == m and s in s22 and s22[s][0] and s26[s] is not None)
        out_casos.append({"id": f"{m[0]}-{m[1]}", "uf": m[0], "municipio": nomes.get(m, m[1]),
                          "virada": x, "mediana_estado": med, "secoes": len(dif),
                          "secoes_mesma_direcao": sum(1 for d in dif if (d < 0) == (x < 0)),
                          "min": dif[0] if dif else None, "max": dif[-1] if dif else None})
    por_uf = defaultdict(set)
    for c in out_casos:
        por_uf[c["uf"]].add(c["municipio"])
    with ProcessPoolExecutor(6) as ex:
        lideres = [r for rs in ex.map(lider_local, por_uf.items()) for r in rs]
    out = {"linha_base": base, "casos": out_casos, "lideres": lideres}
    (RAIZ / "resultados/viradas.json").write_text(json.dumps(out, ensure_ascii=False))
    for c in out_casos:
        print(f"  {c['uf']} {c['municipio']:<26} {c['virada']*100:+.0f}pp "
              f"{c['secoes_mesma_direcao']}/{c['secoes']} secoes na mesma direcao")


if __name__ == "__main__":
    main()
