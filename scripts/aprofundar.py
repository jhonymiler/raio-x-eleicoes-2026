#!/usr/bin/env python3
"""Aprofunda os sinais levantados por investigar.py. Cada teste tem uma
hipotese inocente e uma de fraude, e o dado decide entre elas.

1. Biometria: secoes com muita liberacao sem digital votam diferente das
   vizinhas de escola. Ja votavam assim em 2022 (composicao do eleitorado)
   ou passaram a votar em 2026 (mesario votando por ausentes)?
2. Secoes que destoam da escola (|z|>5): a favor de quem, e ja destoavam
   em 2022?
3. Canto de Klimek (comparecimento >= 95% e um candidato >= 90%): a mesma
   secao ja era assim em 2022?
4. Municipios em alerta: candidatos locais, cadastro, biometria por secao.

Entradas: dados/derivados/secoes_pres_1t_2026.csv.gz (de investigar.py),
          dados/votacao_secao_2022_BR.csv, resultados/investigacao.json
Saida:    resultados/aprofundamento.json

Uso:  python3 scripts/aprofundar.py
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import historico  # noqa: E402

RAIZ = Path(__file__).parent.parent
SAIDA = RAIZ / "resultados" / "aprofundamento.json"


def carregar_2026() -> dict:
    out = {}
    with gzip.open(RAIZ / "dados" / "derivados" / "secoes_pres_1t_2026.csv.gz", "rt",
                   encoding="utf-8") as fh:
        for L in csv.DictReader(fh, delimiter=";"):
            k = (L["uf"], L["mun"], L["zona"], L["secao"])
            comp = int(L["comp"])
            val = comp - int(L["brancos"]) - int(L["nulos"])
            out[k] = {"local": L["local"], "mun_nome": L["mun_nome"], "aptos": int(L["aptos"]),
                      "comp": comp, "val": val, "v13": int(L["votos_13"]),
                      "v22": int(L["votos_22"]), "biom": int(L["biom"]),
                      "res": float(L["res_escola_lula"]) if L["res_escola_lula"] else None,
                      "z": float(L["z_escola_lula"]) if L["z_escola_lula"] else None}
    return out


def carregar_2022() -> dict:
    """Secao -> votos validos, Lula, Bolsonaro e local (1o turno 2022)."""
    out: dict = {}
    with open(RAIZ / "dados" / "votacao_secao_2022_BR.csv", encoding="latin-1",
              newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        i = {c: n for n, c in enumerate(next(rd))}
        for L in rd:
            if L[i["CD_CARGO"]] != "1" or L[i["NR_TURNO"]] != "1":
                continue
            k = (L[i["SG_UF"]], L[i["CD_MUNICIPIO"]], L[i["NR_ZONA"]], L[i["NR_SECAO"]])
            s = out.setdefault(k, {"local": L[i["NR_LOCAL_VOTACAO"]], "val": 0, "v13": 0, "v22": 0})
            nr, q = L[i["NR_VOTAVEL"]], int(L[i["QT_VOTOS"]])
            if nr in ("95", "96"):
                continue
            s["val"] += q
            if nr in ("13", "22"):
                s["v" + nr] += q
    return out


def residuos(secoes: dict, local_de) -> dict:
    """Share do Lula na secao menos o das outras secoes do mesmo local."""
    grupos = defaultdict(list)
    for k, s in secoes.items():
        if s["val"] > 0:
            grupos[k[:3] + (local_de(s),)].append(k)
    res = {}
    for ks in grupos.values():
        if len(ks) < 3:
            continue
        tv = sum(secoes[k]["val"] for k in ks)
        t13 = sum(secoes[k]["v13"] for k in ks)
        for k in ks:
            s = secoes[k]
            ov, o13 = tv - s["val"], t13 - s["v13"]
            if s["val"] >= 50 and ov > 0:
                res[k] = s["v13"] / s["val"] - o13 / ov
    return res


def media_ic(v) -> dict:
    v = [x for x in v if x is not None]
    if len(v) < 2:
        return {"n": len(v), "media": None, "ep": None}
    return {"n": len(v), "media": st.fmean(v), "ep": st.stdev(v) / math.sqrt(len(v))}


def diff(a: dict, b: dict) -> dict:
    if a["media"] is None or b["media"] is None:
        return {"dif": None, "z": None}
    d = a["media"] - b["media"]
    ep = math.hypot(a["ep"], b["ep"])
    return {"dif": d, "z": d / ep if ep else None}


def main() -> None:
    s26 = carregar_2026()
    s22 = carregar_2022()
    r26 = {k: s["res"] for k, s in s26.items() if s["res"] is not None}
    r22 = residuos(s22, lambda s: s["local"])
    print(f"secoes 2026: {len(s26):,}  2022: {len(s22):,}  "
          f"com residuo nas duas: {len(r26.keys() & r22.keys()):,}", flush=True)
    out = {}

    # ---- 1. biometria: diferenca-em-diferencas -----------------------------
    def tx(s):
        return s["biom"] / s["comp"] if s["comp"] and s["biom"] >= 0 else None
    alto = [k for k, s in s26.items() if (tx(s) or 0) >= .2 and k in r26]
    baixo = [k for k, s in s26.items() if tx(s) is not None and tx(s) < .05 and k in r26]
    g = {}
    for nome, ks in (("alto", alto), ("baixo", baixo)):
        par = [k for k in ks if k in r22]
        g[nome] = {"r26": media_ic([r26[k] for k in ks]),
                   "r26_par": media_ic([r26[k] for k in par]),
                   "r22_par": media_ic([r22[k] for k in par]),
                   "delta": media_ic([r26[k] - r22[k] for k in par])}
    out["biometria"] = {
        "grupos": g,
        "dif_2026": diff(g["alto"]["r26"], g["baixo"]["r26"]),
        "dif_2022_mesmas": diff(g["alto"]["r22_par"], g["baixo"]["r22_par"]),
        "dif_mudanca": diff(g["alto"]["delta"], g["baixo"]["delta"]),
        # votos do Lula que a diferenca de 2026 representaria, se fosse toda fraude
        "votos_em_jogo": round(sum(s26[k]["val"] for k in alto) *
                               (g["alto"]["r26"]["media"] - g["baixo"]["r26"]["media"])),
        # faixas de liberacao sem biometria x residuo (dose-resposta)
        "faixas": faixas(s26, r26, r22, tx),
    }

    # ---- 2. secoes que destoam da escola ------------------------------------
    fortes = [k for k, s in s26.items() if s["z"] is not None and abs(s["z"]) > 5]
    out["escola"] = {
        "n": len(fortes),
        "pro_lula": sum(1 for k in fortes if s26[k]["z"] > 0),
        "pro_flavio": sum(1 for k in fortes if s26[k]["z"] < 0),
        "com_2022": sum(1 for k in fortes if k in r22),
        "mesmo_sinal_2022": sum(1 for k in fortes if k in r22 and
                                 (r22[k] > 0) == (s26[k]["z"] > 0) and abs(r22[k]) > .05),
        "correlacao_26_22": correl([(r26[k], r22[k]) for k in r26.keys() & r22.keys()]),
        "correlacao_fortes": correl([(r26[k], r22[k]) for k in fortes if k in r22]),
        "lista": sorted(({"id": "-".join(k), "mun": s26[k]["mun_nome"],
                          "z": s26[k]["z"], "res26": r26.get(k), "res22": r22.get(k),
                          "aptos": s26[k]["aptos"], "comp": s26[k]["comp"],
                          "lula": s26[k]["v13"], "flavio": s26[k]["v22"],
                          "lula22": s22.get(k, {}).get("v13"), "bolsonaro22": s22.get(k, {}).get("v22"),
                          "biom": s26[k]["biom"]} for k in fortes), key=lambda d: -abs(d["z"])),
    }

    # ---- 3. canto de Klimek -------------------------------------------------
    canto = []
    for k, s in s26.items():
        if s["aptos"] < 50 or not s["val"]:
            continue
        turn = s["comp"] / s["aptos"]
        for nr, v in (("13", s["v13"]), ("22", s["v22"])):
            if turn >= .95 and v / s["val"] >= .9:
                o = s22.get(k)
                canto.append({"id": "-".join(k), "mun": s["mun_nome"], "candidato": nr,
                              "aptos": s["aptos"], "comp": s["comp"], "turn": turn,
                              "share26": v / s["val"], "biom": s["biom"],
                              "share22": (o["v" + nr] / o["val"]) if o and o["val"] else None})
    out["klimek_canto"] = {
        "n": len(canto), "lula": sum(1 for c in canto if c["candidato"] == "13"),
        "flavio": sum(1 for c in canto if c["candidato"] == "22"),
        "ja_90_em_2022": sum(1 for c in canto if (c["share22"] or 0) >= .9),
        "sem_2022": sum(1 for c in canto if c["share22"] is None),
        "lista": sorted(canto, key=lambda c: -c["turn"]),
    }

    # ---- 4. municipios em alerta ---------------------------------------------
    inv = json.loads((RAIZ / "resultados" / "investigacao.json").read_text())
    m22, n22 = historico.carregar(2022)
    m26, n26 = historico.carregar(2026)
    casos = []
    for uf, ls in inv["municipios"].items():
        for x in ls:
            if not x["alertas"]:
                continue
            chave = uf + x["mun"]
            top = lambda m, n: [{"nome": n[nr], "share": q / sum(m[chave].values())}
                                for nr, q in sorted(m[chave].items(), key=lambda t: -t[1])[:4]] \
                if chave in m else []
            ks = [k for k in s26 if k[0] == uf and k[1] == x["mun"]]
            txs = sorted(tx(s26[k]) or 0 for k in ks)
            casos.append({
                "id": f"{uf}-{x['mun']}", "uf": uf, "municipio": x["nome"],
                "alertas": x["alertas"], "secoes": len(ks),
                "aptos": sum(s26[k]["aptos"] for k in ks),
                "comp": sum(s26[k]["comp"] for k in ks),
                "validos_2022": sum(m22.get(chave, {}).values()),
                "validos_2026": sum(m26.get(chave, {}).values()),
                "top_2026": top(m26, n26), "top_2022": top(m22, n22),
                "biom_secoes_acima_30": sum(1 for t in txs if t >= .3),
                "biom_mediana": st.median(txs) if txs else None,
                "biom_max": txs[-1] if txs else None,
                "swing": x["swing"], "turn": x["turn"], "biom_tx": x["biom_tx"],
                "cresc": x["cresc"],
            })
    out["municipios"] = casos
    enriquecer(out, s26)

    SAIDA.write_text(json.dumps(out, ensure_ascii=False, default=float))
    resumo(out)


def categoria_local(nome: str) -> str:
    n = nome.upper()
    if re.search(r"PRISIONAL|PENITENCI|PRES[IÍ]DIO|CADEIA P|CARCER|\bCDP\b|DETEN[CÇ]|"
                 r"SOCIOEDUCA|INTERNA[CÇ][AÃ]O|FUNDA[CÇ][AÃ]O CASA|\bAPAC\b", n):
        return "presídio / internação"
    if re.search(r"IND[IÍ]GENA|ALDEIA|\bTERRA IND", n):
        return "aldeia / escola indígena"
    if "QUILOMB" in n:
        return "quilombo"
    if re.search(r"HOSPITAL|ASILO|ABRIGO|LAR DOS IDOSOS", n):
        return "hospital / asilo"
    if re.search(r"ASSENTAMENTO|AGROVILA|VILA RURAL", n):
        return "assentamento rural"
    return "convencional"


def enriquecer(out: dict, s26: dict) -> None:
    """Nome e tipo do local, idade x vizinhas, digital (Klimek), votos em jogo."""
    alvo = {s["id"] for s in out["escola"]["lista"]} | {s["id"] for s in out["klimek_canto"]["lista"]}
    nomes = {}
    with open(RAIZ / "dados" / "votacao_secao_2026_BR.csv", encoding="latin-1", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        i = {c: n for n, c in enumerate(next(rd))}
        for L in rd:
            k = "-".join((L[i["SG_UF"]], L[i["CD_MUNICIPIO"]], L[i["NR_ZONA"]], L[i["NR_SECAO"]]))
            if k in alvo and k not in nomes:
                nomes[k] = L[i["NM_LOCAL_VOTACAO"]]
    perfil = {}
    pf = RAIZ / "dados" / "derivados" / "perfil_secao.csv.gz"
    if pf.exists():                                   # gerado por idade_biometria.py
        with gzip.open(pf, "rt", encoding="utf-8") as fh:
            for L in csv.DictReader(fh, delimiter=";"):
                if int(L["eleitores"]) > 0:
                    perfil["-".join((L["uf"], L["mun"], L["zona"], L["secao"]))] = (
                        int(L["idade60"]) / int(L["eleitores"]),
                        int(L["com_biometria"]) / int(L["eleitores"]))
    escolas = defaultdict(list)
    for k, s in s26.items():
        escolas[k[:3] + (s["local"],)].append("-".join(k))
    escola_de = {kid: e for e, ks in escolas.items() for kid in ks}
    for s in out["escola"]["lista"] + out["klimek_canto"]["lista"]:
        s["local_nome"] = nomes.get(s["id"], "")
        s["local_cat"] = categoria_local(s["local_nome"])
        viz = [j for j in escolas[escola_de[s["id"]]] if j != s["id"] and j in perfil]
        s["idade60_vs_vizinhas"] = (perfil[s["id"]][0] - st.fmean(perfil[j][0] for j in viz)
                                    if s["id"] in perfil and viz else None)
    for s in out["klimek_canto"]["lista"]:
        p = perfil.get(s["id"])
        s["identificados_digital"] = (max(0, min(p[1] * s["aptos"], s["comp"]) - s["biom"])
                                      if p else None)
    e = out["escola"]
    e["votos_pro_lula"] = sum(s["res26"] * s["comp"] for s in e["lista"] if s["z"] > 0 and s["res26"] is not None)
    e["votos_pro_flavio"] = sum(s["res26"] * s["comp"] for s in e["lista"] if s["z"] < 0 and s["res26"] is not None)
    e["votos_saldo"] = e["votos_pro_lula"] + e["votos_pro_flavio"]
    e["novas"] = sum(1 for s in e["lista"] if s["res22"] is None)
    e["novas_pro_lula"] = sum(1 for s in e["lista"] if s["res22"] is None and s["z"] > 0)
    for lado, cond in (("lula", lambda s: s["z"] > 0), ("flavio", lambda s: s["z"] < 0)):
        v = [s["idade60_vs_vizinhas"] for s in e["lista"] if cond(s) and s["idade60_vs_vizinhas"] is not None]
        e[f"idade60_mediana_{lado}"] = st.median(v) if v else None
    k = out["klimek_canto"]
    ident = [s for s in k["lista"] if s["identificados_digital"] is not None]
    k["identificados_digital_pct"] = (sum(s["identificados_digital"] for s in ident) /
                                      max(1, sum(s["comp"] for s in ident)))
    k["indigenas_quilombos"] = sum(1 for s in k["lista"] if s["local_cat"] != "convencional")


def faixas(s26, r26, r22, tx) -> list:
    cortes = [0, .02, .05, .1, .2, .3, 1.01]
    out = []
    for a, b in zip(cortes, cortes[1:]):
        ks = [k for k, s in s26.items() if k in r26 and tx(s) is not None and a <= tx(s) < b]
        par = [k for k in ks if k in r22]
        out.append({"de": a, "ate": min(b, 1), "secoes": len(ks),
                    "res26": media_ic([r26[k] for k in ks])["media"],
                    "res22": media_ic([r22[k] for k in par])["media"],
                    "delta": media_ic([r26[k] - r22[k] for k in par])["media"]})
    return out


def correl(pares) -> float | None:
    if len(pares) < 3:
        return None
    xs, ys = zip(*pares)
    mx, my = st.fmean(xs), st.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in pares)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return sxy / (sx * sy) if sx and sy else None


def resumo(o) -> None:
    b = o["biometria"]
    f = lambda d: "—" if d is None else f"{d*100:+.2f}pp"
    print("\n1. BIOMETRIA (residuo do Lula vs escola; alto = >=20% liberados sem digital)")
    for g in ("alto", "baixo"):
        x = b["grupos"][g]
        print(f"   {g:<5} n={x['r26']['n']:>7,} 2026={f(x['r26']['media'])}  "
              f"mesmas secoes: 2022={f(x['r22_par']['media'])} 2026={f(x['r26_par']['media'])} "
              f"mudanca={f(x['delta']['media'])} (n={x['delta']['n']:,})")
    for nome in ("dif_2026", "dif_2022_mesmas", "dif_mudanca"):
        d = b[nome]
        print(f"   {nome:<16} {f(d['dif'])}  z={d['z'] if d['z'] is None else round(d['z'],1)}")
    print(f"   votos em jogo se tudo fosse fraude: {b['votos_em_jogo']:,}")
    for x in b["faixas"]:
        print(f"   faixa {x['de']:.2f}-{x['ate']:.2f}: n={x['secoes']:>7,} "
              f"2026={f(x['res26'])} 2022={f(x['res22'])} mudanca={f(x['delta'])}")
    e = o["escola"]
    print(f"\n2. ESCOLA |z|>5: {e['n']} secoes, pro-Lula {e['pro_lula']}, pro-Flavio {e['pro_flavio']}; "
          f"com 2022: {e['com_2022']}, mesmo sinal e >5pp em 2022: {e['mesmo_sinal_2022']}; "
          f"correlacao 2026x2022 geral={e['correlacao_26_22']:.2f}, fortes={e['correlacao_fortes'] or 0:.2f}")
    k = o["klimek_canto"]
    print(f"\n3. KLIMEK canto: {k['n']} (Lula {k['lula']}, Flavio {k['flavio']}); "
          f"ja >=90% em 2022: {k['ja_90_em_2022']}; sem par em 2022: {k['sem_2022']}")
    for c in k["lista"][:12]:
        print(f"   {c['id']:<22} {c['mun'][:20]:<20} cand={c['candidato']} aptos={c['aptos']} "
              f"turn={c['turn']:.2f} share26={c['share26']:.2f} share22={c['share22'] if c['share22'] is None else round(c['share22'],2)} biom={c['biom']}")
    print("\n4. MUNICIPIOS")
    for c in o["municipios"]:
        t26 = ", ".join(f"{x['nome'].split()[0]} {x['share']:.0%}" for x in c["top_2026"][:3])
        t22 = ", ".join(f"{x['nome'].split()[0]} {x['share']:.0%}" for x in c["top_2022"][:2])
        print(f"   {c['uf']} {c['municipio'][:24]:<24} {c['alertas']} aptos={c['aptos']:,} "
              f"val22={c['validos_2022']:,} val26={c['validos_2026']:,} biom>30%={c['biom_secoes_acima_30']}/{c['secoes']} "
              f"| 2026: {t26} | 2022: {t22}")


if __name__ == "__main__":
    main()
