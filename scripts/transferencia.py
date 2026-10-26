#!/usr/bin/env python3
"""Para onde foram os votos dos eliminados no 2o turno? (inferencia ecologica)

Regressao de Goodman municipio a municipio, em contagens:
  ganho do Flavio_m = soma_k b_k * votos1T_k,m  (+ termos de base)
  ganho do Lula_m   = soma_k a_k * votos1T_k,m
b_k estima a fracao dos eleitores do candidato k (1o turno) que foi para o
Flavio; a_k, para o Lula. Termos de base (votos de Lula e Flavio no 1T)
absorvem a mudanca de comparecimento proporcional ao tamanho do eleitorado.
E um experimento natural em Goias: Caiado teve la 12% dos votos.

Entradas: dados/votacao_secao_2026_BR.csv, dados/totais_2t_municipio_6258.csv
Saida: resultados/transferencia.json
Uso:   python3 scripts/transferencia.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import totais_2t  # noqa: E402
from idade_biometria import ols  # noqa: E402

RAIZ = Path(__file__).parent.parent


def chave(uf, mun):
    return uf.upper() + str(int(mun))


def main() -> None:
    v1: dict = defaultdict(lambda: defaultdict(int))
    nomes = {}
    with open(RAIZ / "dados/votacao_secao_2026_BR.csv", encoding="latin-1", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        i = {c: n for n, c in enumerate(next(rd))}
        for L in rd:
            if L[i["CD_CARGO"]] != "1" or L[i["SG_UF"]] == "ZZ":
                continue
            nr = L[i["NR_VOTAVEL"]]
            nr = "bn" if nr in ("95", "96") else nr
            v1[chave(L[i["SG_UF"]], L[i["CD_MUNICIPIO"]])][nr] += int(L[i["QT_VOTOS"]])
            nomes[nr] = L[i["NM_VOTAVEL"]]
    v2: dict = defaultdict(dict)
    for L in totais_2t.ler("6258")[0]:
        v2[chave(L["uf"], L["cd_municipio"])][L["nr_votavel"]] = L["qt_votos"]
    principais = ["23", "30", "44", "28"]          # Cury, Renan, Caiado, Zema (maiores eliminados)
    principais = sorted((nr for nr in nomes if nr not in ("13", "22", "bn")),
                        key=lambda nr: -sum(m.get(nr, 0) for m in v1.values()))[:4]
    vars_ = principais + ["pequenos", "bn", "13", "22"]

    def linhas(filtro):
        ks = [k for k in v1.keys() & v2.keys() if filtro(k)
              and v2[k].get("13", 0) + v2[k].get("22", 0) > 0]
        X = {v: [] for v in vars_}
        dl, df = [], []
        for k in ks:
            a, b = v1[k], v2[k]
            for v in vars_:
                X[v].append(sum(q for nr, q in a.items() if nr not in ("13", "22", "bn", *principais))
                            if v == "pequenos" else a.get(v, 0))
            dl.append(b.get("13", 0) - a.get("13", 0))
            df.append(b.get("22", 0) - a.get("22", 0))
        return ks, X, dl, df

    def estimar(filtro):
        ks, X, dl, df = linhas(filtro)
        xs = [X[v] for v in vars_]
        rf, rl = ols(df, xs), ols(dl, xs)
        rot = {nr: nomes[nr] for nr in principais} | {"pequenos": "demais eliminados",
               "bn": "brancos e nulos do 1T", "13": "base Lula 1T (comparecimento)",
               "22": "base Flávio 1T (comparecimento)"}
        return {"municipios": len(ks), "coef": [{"origem": rot[v], "votos_1t": sum(X[v]),
                "para_flavio": rf[j]["coef"], "ep_flavio": rf[j]["ep"],
                "para_lula": rl[j]["coef"], "ep_lula": rl[j]["ep"]} for j, v in enumerate(vars_)]}

    out = {"brasil": estimar(lambda k: True),
           "goias": estimar(lambda k: k.startswith("GO"))}
    # Goias em totais: o estado do Caiado
    go = [k for k in v1.keys() & v2.keys() if k.startswith("GO")]
    out["goias_totais"] = {
        "caiado_1t": sum(v1[k].get(principais[2] if nomes.get(principais[2], "").startswith("RONALDO") else "44", 0) for k in go),
        "lula_1t": sum(v1[k].get("13", 0) for k in go), "lula_2t": sum(v2[k].get("13", 0) for k in go),
        "flavio_1t": sum(v1[k].get("22", 0) for k in go), "flavio_2t": sum(v2[k].get("22", 0) for k in go)}
    (RAIZ / "resultados/transferencia.json").write_text(json.dumps(out, ensure_ascii=False))
    for reg in ("brasil", "goias"):
        print(f"\n{reg.upper()} ({out[reg]['municipios']} municipios): fracao de cada origem que foi para cada finalista")
        for c in out[reg]["coef"]:
            print(f"   {c['origem'][:34]:<34} {c['votos_1t']:>11,}  -> Flávio {c['para_flavio']:+.2f} (±{1.96*c['ep_flavio']:.2f})"
                  f"   -> Lula {c['para_lula']:+.2f} (±{1.96*c['ep_lula']:.2f})")
    g = out["goias_totais"]
    print(f"\nGoiás totais: Caiado 1T {g['caiado_1t']:,} | Lula {g['lula_1t']:,} -> {g['lula_2t']:,} (+{g['lula_2t']-g['lula_1t']:,}) "
          f"| Flávio {g['flavio_1t']:,} -> {g['flavio_2t']:,} (+{g['flavio_2t']-g['flavio_1t']:,})")


if __name__ == "__main__":
    main()
