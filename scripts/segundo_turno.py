#!/usr/bin/env python3
"""2o turno de 2026: de onde veio a mudanca entre os turnos?

1. Mudanca do Lula (share entre os dois finalistas) do 1o para o 2o turno,
   municipio a municipio, e regressao contra a composicao do 1o turno
   (votos de cada candidato eliminado, brancos e nulos). Se a mudanca e
   explicada pela transferencia dos eliminados, ela e o que se espera.
2. Municipios fora do padrao do proprio estado (z robusto > 5 e >= 5 pontos).
3. Com os logs (logs_urna.py nacional ... 3221): comparecimento 1T -> 2T por
   secao, votos depois das 17h e urnas que fecharam as 17h apesar da
   prorrogacao, cruzados com a mudanca de voto do municipio.

Entradas: dados/totais_2t_municipio_6258.csv (totais_2t.py, totais finais),
          dados/votacao_secao_2026_BR.csv, resultados/logs_nacional_3221.json
Saida:    resultados/segundo_turno.json
Uso:      python3 scripts/segundo_turno.py
"""

from __future__ import annotations

import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import historico  # noqa: E402
import totais_2t  # noqa: E402
from idade_biometria import ols  # noqa: E402

RAIZ = Path(__file__).parent.parent


def chave(uf: str, mun: str) -> str:
    return uf.upper() + str(int(mun))        # o 2T vem com zeros a esquerda


def main() -> None:
    m1, nomes = historico.carregar(2026)
    m1 = {chave(k[:2], k[2:]): v for k, v in m1.items()}
    t2: dict = defaultdict(dict)
    linhas2, meta = totais_2t.ler("6258")
    for L in linhas2:
        t2[chave(L["uf"], L["cd_municipio"])][L["nr_votavel"]] = L["qt_votos"]

    # brancos/nulos do 1o turno vem do CSV por secao (historico.carregar os descarta)
    bn1: dict = defaultdict(int)
    with open(RAIZ / "dados/votacao_secao_2026_BR.csv", encoding="latin-1", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        i = {c: n for n, c in enumerate(next(rd))}
        for L in rd:
            if L[i["CD_CARGO"]] == "1" and L[i["NR_VOTAVEL"]] in ("95", "96") and L[i["SG_UF"]] != "ZZ":
                bn1[chave(L[i["SG_UF"]], L[i["CD_MUNICIPIO"]])] += int(L[i["QT_VOTOS"]])

    eliminados = [nr for nr in sorted(nomes, key=lambda n: -sum(v.get(n, 0) for v in m1.values()))
                  if nr not in ("13", "22")][:4]
    linhas = []
    for k in t2.keys() & m1.keys():
        a, b = m1[k], t2[k]
        tot1 = sum(a.values()) + bn1.get(k, 0)
        d1, d2 = a.get("13", 0) + a.get("22", 0), b.get("13", 0) + b.get("22", 0)
        if not d1 or not d2 or tot1 < 200:
            continue
        linhas.append({"id": k, "uf": k[:2], "s1": a.get("13", 0) / d1, "s2": b.get("13", 0) / d2,
                       "validos2": d2, "tot1": tot1,
                       **{f"e{nr}": a.get(nr, 0) / tot1 for nr in eliminados},
                       "outros": sum(q for nr, q in a.items() if nr not in ("13", "22", *eliminados)) / tot1,
                       "bn": bn1.get(k, 0) / tot1})
    for L in linhas:
        L["mud"] = L["s2"] - L["s1"]

    # 1. regressao (variaveis centradas; mudanca ~ composicao do 1o turno)
    vs = [f"e{nr}" for nr in eliminados] + ["outros", "bn", "s1"]
    med = {v: st.fmean(L[v] for L in linhas) for v in vs + ["mud"]}
    y = [L["mud"] - med["mud"] for L in linhas]
    xs = [[L[v] - med[v] for L in linhas] for v in vs]
    reg = dict(zip(vs, ols(y, xs)))
    pred = [sum(reg[v]["coef"] * x[t] for v, x in zip(vs, xs)) for t in range(len(linhas))]
    sst = sum(v * v for v in y)
    sse = sum((a - b) ** 2 for a, b in zip(y, pred))
    r2 = 1 - sse / sst if sst else None
    for L, p in zip(linhas, pred):
        L["residuo"] = L["mud"] - med["mud"] - p

    # 2. fora do padrao do estado, depois de descontar a composicao
    por_uf = defaultdict(list)
    for L in linhas:
        por_uf[L["uf"]].append(L)
    fora = []
    for ls in por_uf.values():
        r = [L["residuo"] for L in ls]
        mr = st.median(r)
        mad = st.median(abs(x - mr) for x in r) * 1.4826
        for L in ls:
            L["z"] = (L["residuo"] - mr) / mad if mad else 0.0
            if abs(L["z"]) > 5 and abs(L["residuo"] - mr) >= .05:
                fora.append(L)

    d1 = sum(m1[k].get("13", 0) + m1[k].get("22", 0) for k in t2.keys() & m1.keys())
    d2 = sum(t2[k].get("13", 0) + t2[k].get("22", 0) for k in t2.keys() & m1.keys())
    out = {
        "totalizacao": meta,
        "municipios": len(linhas),
        "lula_1t": sum(m1[k].get("13", 0) for k in t2.keys() & m1.keys()) / d1,
        "lula_2t": sum(t2[k].get("13", 0) for k in t2.keys() & m1.keys()) / d2,
        "validos_1t_finalistas": d1, "validos_2t": d2,
        "mudanca_mediana": st.median(L["mud"] for L in linhas),
        "mudanca_p5": sorted(L["mud"] for L in linhas)[len(linhas) // 20],
        "mudanca_p95": sorted(L["mud"] for L in linhas)[-len(linhas) // 20],
        "eliminados": {f"e{nr}": nomes[nr] for nr in eliminados},
        "regressao": reg, "r2": r2,
        "fora_do_padrao": [{k: (round(v, 5) if isinstance(v, float) else v) for k, v in L.items()}
                           for L in sorted(fora, key=lambda L: -abs(L["z"]))],
        "horario": horario(linhas),
    }
    (RAIZ / "resultados/segundo_turno.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"Lula (2 finalistas): 1T {out['lula_1t']:.2%} -> 2T {out['lula_2t']:.2%} "
          f"({meta['pct_totalizado']}% totalizado, encerrada={meta['totalizacao_encerrada']})")
    print(f"mudanca por municipio: mediana {out['mudanca_mediana']*100:+.2f} pp "
          f"(p5 {out['mudanca_p5']*100:+.2f}, p95 {out['mudanca_p95']*100:+.2f}); n={len(linhas)}")
    print(f"R2 da composicao do 1T: {r2:.2f}")
    for v, c in reg.items():
        print(f"   {out['eliminados'].get(v, v):<28} {c['coef']*100:+7.2f} pp por 100%  z={c['z']:+.1f}")
    print(f"fora do padrao do estado: {len(fora)}")
    for L in out["fora_do_padrao"][:15]:
        print(f"   {L['id']:<10} mud={L['mud']*100:+.1f} residuo={L['residuo']*100:+.1f} z={L['z']:+.1f} validos={L['validos2']}")
    if out["horario"]:
        print("horario:", json.dumps(out["horario"]["resumo"], ensure_ascii=False))


def horario(linhas) -> dict | None:
    """Votos depois das 17h e comparecimento 1T -> 2T, pelos logs da amostra."""
    p = RAIZ / "resultados/logs_nacional_3221.json"
    if not p.exists():
        return None
    urnas = json.loads(p.read_text())["urnas"]
    mud = {L["id"]: L for L in linhas}
    por_mun = defaultdict(lambda: {"votos": 0, "apos": 0, "comp1": 0, "urnas": 0, "fechou17": 0})
    for k, x in urnas.items():
        if not x.get("votos_log"):
            continue
        uf, mun = k.split("-")[:2]
        m = por_mun[chave(uf, mun)]
        m["votos"] += x["votos_log"]
        m["apos"] += x["votos_apos_17h"]
        m["comp1"] += x["bu_comp_1t"]
        m["urnas"] += 1
        m["fechou17"] += x["minutos_apos_17h"] <= 15
    pares = [(m["apos"] / m["votos"], mud[k]["mud"], m["votos"] / m["comp1"] - 1)
             for k, m in por_mun.items() if k in mud and m["votos"]]
    vs = [m for m in por_mun.values() if m["votos"]]

    def corr(a, b):
        ma, mb = st.fmean(a), st.fmean(b)
        sa = sum((x - ma) ** 2 for x in a) ** .5
        sb = sum((x - mb) ** 2 for x in b) ** .5
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else None
    return {"resumo": {
        "urnas": sum(m["urnas"] for m in vs),
        "municipios": len(vs),
        "votos_apos_17h_pct": sum(m["apos"] for m in vs) / sum(m["votos"] for m in vs),
        "urnas_fecharam_17h_pct": sum(m["fechou17"] for m in vs) / sum(m["urnas"] for m in vs),
        "comparecimento_2t_vs_1t": sum(m["votos"] for m in vs) / sum(m["comp1"] for m in vs) - 1,
        "corr_apos17h_mudanca": corr([a for a, _, _ in pares], [b for _, b, _ in pares]),
        "corr_comparecimento_mudanca": corr([c for _, _, c in pares], [b for _, b, _ in pares]),
    }}


if __name__ == "__main__":
    main()
