#!/usr/bin/env python3
"""Migracao de votos do 1o para o 2o turno, municipio a municipio.

Identidade contabil (tem de fechar em todo municipio):
  Lula2 + Flavio2 + brancos2 + nulos2 = comparecimento2
  ganho_Lula + ganho_Flavio = eliminados + (brancos/nulos1 - brancos/nulos2)
                              + (comparecimento2 - comparecimento1)
O lado direito e o "bolo" de votos em jogo. Para cada municipio:
  parcela do bolo que foi para cada finalista;
  Flavio esperado se toda a direita eliminada (Renan, Caiado, Zema) fosse dele;
alertas: Flavio perdendo votos; Lula ganhando mais que o bolo; salto de
comparecimento fora do padrao do estado (z robusto > 5 e >= 5 pontos).

Entradas: dados/totais_2t_municipio_6258.csv (totais_2t.py),
          dados/votacao_secao_2026_BR.csv, dados/derivados/secoes_pres_1t_2026.csv.gz
Saida:    resultados/migracao.json
Uso:      python3 scripts/migracao.py
"""

from __future__ import annotations

import csv
import gzip
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).parent.parent
DIREITA = {"30": "Renan Santos", "44": "Ronaldo Caiado", "28": "Romeu Zema"}


def chave(uf, mun):
    return uf.upper() + str(int(mun))


def z_rob(v):
    med = st.median(v)
    mad = st.median(abs(x - med) for x in v) * 1.4826
    return [(x - med) / mad if mad else 0.0 for x in v], med


def main() -> None:
    # 1o turno: votos por candidato e brancos/nulos por municipio
    t1: dict = defaultdict(lambda: defaultdict(int))
    nomes = {}
    with open(RAIZ / "dados/votacao_secao_2026_BR.csv", encoding="latin-1", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        i = {c: n for n, c in enumerate(next(rd))}
        for L in rd:
            if L[i["CD_CARGO"]] != "1" or L[i["NR_TURNO"]] != "1" or L[i["SG_UF"]] == "ZZ":
                continue
            nr = L[i["NR_VOTAVEL"]]
            t1[chave(L[i["SG_UF"]], L[i["CD_MUNICIPIO"]])][nr] += int(L[i["QT_VOTOS"]])
            nomes[nr] = L[i["NM_VOTAVEL"]]
    ap1: dict = defaultdict(lambda: [0, 0])
    with gzip.open(RAIZ / "dados/derivados/secoes_pres_1t_2026.csv.gz", "rt", encoding="utf-8") as fh:
        for L in csv.DictReader(fh, delimiter=";"):
            if L["uf"] != "ZZ":
                a = ap1[chave(L["uf"], L["mun"])]
                a[0] += int(L["aptos"])
                a[1] += int(L["comp"])
    # identifica numeros da direita pelo nome (o numero do partido pode variar)
    direita = {nr for nr, n in nomes.items()
               if any(p in n for p in ("RENAN ANTONIO", "RONALDO RAMOS CAIADO", "ROMEU ZEMA"))}
    cury = {nr for nr, n in nomes.items() if "AUGUSTO JORGE CURY" in n}

    t2 = {}
    with open(RAIZ / "dados/totais_2t_municipio_6258.csv", encoding="utf-8") as fh:
        for L in csv.DictReader(fh):
            t2[chave(L["uf"], L["cd_municipio"])] = {k: (int(v) if v.lstrip("-").isdigit() else v)
                                                     for k, v in L.items()}

    linhas = []
    for k in t1.keys() & t2.keys():
        a, b = t1[k], t2[k]
        L1, F1 = a.get("13", 0), a.get("22", 0)
        bn1 = a.get("95", 0) + a.get("96", 0)
        elim = sum(q for nr, q in a.items() if nr not in ("13", "22", "95", "96"))
        dir_ = sum(a.get(nr, 0) for nr in direita)
        cur = sum(a.get(nr, 0) for nr in cury)
        apt1, comp1 = ap1[k]
        L2, F2, bn2, comp2 = b["lula"], b["flavio"], b["brancos"] + b["nulos"], b["comparecimento"]
        gL, gF = L2 - L1, F2 - F1
        bolo = gL + gF
        linhas.append({
            "id": f"{k[:2]}-{k[2:]}", "uf": k[:2], "municipio": b["nm_municipio"],
            "encerrada": b["encerrada"] in (True, "True"), "aptos": b["aptos"],
            "comp1": comp1, "comp2": comp2, "turn1": comp1 / apt1 if apt1 else None,
            "turn2": comp2 / b["aptos"] if b["aptos"] else None,
            "lula1": L1, "lula2": L2, "flavio1": F1, "flavio2": F2,
            "eliminados": elim, "direita": dir_, "cury": cur, "bn1": bn1, "bn2": bn2,
            "ganho_lula": gL, "ganho_flavio": gF, "bolo": bolo,
            "parcela_lula": gL / bolo if bolo > 0 else None,
            "flavio_se_direita": F1 + dir_, "deficit_flavio": F2 - (F1 + dir_),
            "fecha_2t": L2 + F2 + bn2 - comp2,                   # tem de ser 0
            "fecha_bolo": bolo - (elim + bn1 - bn2 + comp2 - comp1),  # tem de ser 0
        })

    # salto de comparecimento fora do padrao do estado
    por_uf = defaultdict(list)
    for L in linhas:
        if L["turn1"] and L["turn2"]:
            L["dturn"] = L["turn2"] - L["turn1"]
            por_uf[L["uf"]].append(L)
    for ls in por_uf.values():
        zs, med = z_rob([L["dturn"] for L in ls])
        for L, z in zip(ls, zs):
            L["z_dturn"] = z
            L["dturn_vs_uf"] = L["dturn"] - med
    for L in linhas:
        al = []
        if L["flavio2"] < L["flavio1"]:
            al.append("Flávio perdeu votos")
        if L["lula2"] < L["lula1"]:
            al.append("Lula perdeu votos")
        if L["ganho_lula"] > L["eliminados"] + max(0, L["bn1"] - L["bn2"]) + max(0, L["comp2"] - L["comp1"]):
            al.append("Lula ganhou mais que o bolo")
        if abs(L.get("z_dturn") or 0) > 5 and abs(L.get("dturn_vs_uf") or 0) >= .05:
            al.append("salto de comparecimento")
        if L["fecha_2t"]:
            al.append("2º turno não fecha")
        L["alertas"] = al

    def soma(f, ls=linhas):
        return sum(L[f] for L in ls)
    nac = {f: soma(f) for f in ("lula1", "lula2", "flavio1", "flavio2", "eliminados", "direita",
                                 "cury", "bn1", "bn2", "comp1", "comp2", "ganho_lula", "ganho_flavio")}
    nac["parcela_lula"] = nac["ganho_lula"] / (nac["ganho_lula"] + nac["ganho_flavio"])
    nac["municipios"] = len(linhas)
    nac["nao_fecham"] = sum(1 for L in linhas if L["fecha_2t"])
    nac["nao_encerrados"] = sum(1 for L in linhas if not L["encerrada"])
    nac["alertas"] = {a: sum(1 for L in linhas if a in L["alertas"])
                      for a in ("Flávio perdeu votos", "Lula perdeu votos", "Lula ganhou mais que o bolo",
                                "salto de comparecimento", "2º turno não fecha")}
    # a parcela do Lula no bolo acompanha a composicao do bolo?
    faixas = []
    cortes = [0, .2, .4, .5, .6, .7, .8, 1.01]
    for x, y in zip(cortes, cortes[1:]):
        ls = [L for L in linhas if L["eliminados"] and x <= L["direita"] / L["eliminados"] < y and L["bolo"] > 0]
        if ls:
            faixas.append({"direita_no_bolo": f"{int(x*100)}–{int(round(min(y,1)*100))}%", "municipios": len(ls),
                           "parcela_lula": soma("ganho_lula", ls) / soma("bolo", ls),
                           "dturn": st.median(L["dturn"] for L in ls if "dturn" in L)})
    uf = []
    for u, ls in sorted(por_uf.items()):
        uf.append({"uf": u, "municipios": len(ls), "ganho_lula": soma("ganho_lula", ls),
                   "ganho_flavio": soma("ganho_flavio", ls), "direita": soma("direita", ls),
                   "cury": soma("cury", ls), "eliminados": soma("eliminados", ls),
                   "dcomp": soma("comp2", ls) - soma("comp1", ls),
                   "parcela_lula": soma("ganho_lula", ls) / max(1, soma("ganho_lula", ls) + soma("ganho_flavio", ls))})
    out = {"nacional": nac, "faixas_direita": faixas, "por_uf": uf,
           "municipios": sorted(linhas, key=lambda L: (-len(L["alertas"]), -abs(L.get("z_dturn") or 0)))}
    (RAIZ / "resultados/migracao.json").write_text(json.dumps(out, ensure_ascii=False, default=float))

    f = lambda x: f"{x:,}".replace(",", ".")
    print(f"{nac['municipios']} municipios; não encerrados {nac['nao_encerrados']}; 2T não fecha em {nac['nao_fecham']}")
    print(f"ganho Lula {f(nac['ganho_lula'])} | ganho Flávio {f(nac['ganho_flavio'])} | parcela Lula {nac['parcela_lula']:.0%}")
    print(f"eliminados {f(nac['eliminados'])} (direita {f(nac['direita'])}, Cury {f(nac['cury'])}) | "
          f"brancos/nulos {f(nac['bn1'])} -> {f(nac['bn2'])} | comparecimento {f(nac['comp1'])} -> {f(nac['comp2'])}")
    print("alertas:", nac["alertas"])
    print("\nparcela do Lula no bolo, pela fração de direita entre os eliminados do município:")
    for x in faixas:
        print(f"   direita {x['direita_no_bolo']:<8} municípios={x['municipios']:>5} parcela Lula={x['parcela_lula']:.0%} "
              f"comparecimento {x['dturn']*100:+.1f} pp")
    print("\npor UF:")
    for x in uf:
        print(f"   {x['uf']} ganho Lula {f(x['ganho_lula']):>10} Flávio {f(x['ganho_flavio']):>10} "
              f"(direita elim. {f(x['direita']):>9}, Cury {f(x['cury']):>8}, Δcomp {f(x['dcomp']):>9}) parcela Lula {x['parcela_lula']:.0%}")
    print("\nmunicípios com alerta:")
    for L in out["municipios"][:25]:
        if not L["alertas"]:
            break
        print(f"   {L['id']:<9} {L['municipio'][:24]:<24} {L['alertas']} Lula {f(L['lula1'])}->{f(L['lula2'])} "
              f"Flávio {f(L['flavio1'])}->{f(L['flavio2'])} comp {f(L['comp1'])}->{f(L['comp2'])} "
              f"elim {f(L['eliminados'])}")


if __name__ == "__main__":
    main()
