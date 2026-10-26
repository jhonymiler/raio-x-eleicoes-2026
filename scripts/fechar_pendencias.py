#!/usr/bin/env python3
"""Testes que fecham as pistas em aberto, cada um com controle.

1. cadastro   : os 718 municipios com mais eleitores que moradores (estimativa
                IBGE 2025) ja eram assim em 2022, contra a CONTAGEM do Censo
                2022? Se sim, o excesso e antigo e nao foi criado para 2026.
2. crescimento: nos 17 municipios cujos votos cresceram fora do padrao, o
                eleitorado cresceu junto com a populacao (Censo 2022 ->
                estimativa 2025)?
3. viradas    : a mesma regra de mudanca anormal (z > 5 e >= 5 pts no
                estado), aplicada ao 2o turno 2022 x 2o turno 2026 (os dois
                frente a frente, sem os 11 outros candidatos do 1o turno).
4. Flavio perdeu votos entre os turnos (938 municipios): o Bolsonaro tambem
                perdeu votos entre os turnos de 2022 nos mesmos lugares? E
                quanto da perda acompanha a queda do comparecimento?

Entradas: dados/ibge/censo_2022.json (SIDRA 4709), dados/ibge/pop_2025.json,
          dados/detalhe_munzona_2022.zip, dados/detalhe_munzona/*_2026_BR.csv,
          dados/votacao_secao_2022_BR.csv, dados/totais_2t_municipio_6258.csv,
          resultados/migracao.json, dados/derivados/dossie/*.json
Saida:    resultados/pendencias.{txt,json}
"""

from __future__ import annotations

import csv
import io
import json
import statistics as st
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from realidade import norm  # noqa: E402
from viradas import anormais  # noqa: E402

RAIZ = Path(__file__).parent.parent
DOSSIE = RAIZ / "dados/derivados/dossie"


def ibge(arq: str) -> dict:
    out = {}
    for L in json.loads((RAIZ / "dados/ibge" / arq).read_text())[1:]:
        nome, uf = L["D1N"].rsplit(" - ", 1)
        out[(uf, norm(nome))] = int(L["V"])
    return out


def aptos(linhas) -> dict:
    """Aptos no 1o turno, Presidente, somando as zonas; chave (uf, nome)."""
    out, nomes = defaultdict(int), {}
    for L in linhas:
        if L["NR_TURNO"] == "1" and L["CD_CARGO"] == "1" and L["SG_UF"] not in ("ZZ", "BR"):
            k = f"{L['SG_UF']}-{int(L['CD_MUNICIPIO'])}"
            out[k] += int(L["QT_APTOS"])
            nomes[k] = (L["SG_UF"], norm(L["NM_MUNICIPIO"]))
    return out, nomes


def ler_csv(fh):
    return csv.DictReader(fh, delimiter=";")


def main() -> None:
    censo, est25 = ibge("censo_2022.json"), ibge("pop_2025.json")
    with zipfile.ZipFile(RAIZ / "dados/detalhe_munzona_2022.zip") as z:
        a22, nomes = aptos(ler_csv(io.TextIOWrapper(z.open("detalhe_votacao_munzona_2022_BR.csv"), encoding="latin-1")))
    with open(RAIZ / "dados/detalhe_munzona/detalhe_votacao_munzona_2026_BR.csv", encoding="latin-1") as fh:
        a26, nomes26 = aptos(ler_csv(fh))
    nomes.update(nomes26)
    out: dict = {}

    # ---------- 1. cadastro
    cad = json.load(open(DOSSIE / "cadastro_populacao.json", encoding="utf-8"))
    ja22 = []
    for c in cad:
        k = nomes.get(c["id"])
        if k in censo and c["id"] in a22:
            ja22.append({"id": c["id"], "municipio": c["municipio"], "censo_2022": censo[k],
                         "aptos_2022": a22[c["id"]], "aptos_2026": a26.get(c["id"]),
                         "razao_2022": round(a22[c["id"]] / censo[k], 3)})
    acima22 = [x for x in ja22 if x["razao_2022"] > 1]
    todos22 = sum(1 for k, v in a22.items() if nomes.get(k) in censo and v > censo[nomes[k]])
    cresc_cad = [x["aptos_2026"] / x["aptos_2022"] - 1 for x in ja22 if x["aptos_2026"]]
    cresc_br = [a26[k] / a22[k] - 1 for k in a22 if k in a26 and a22[k]]
    out["cadastro"] = {
        "municipios": len(cad), "casados_censo": len(ja22),
        "ja_acima_em_2022": len(acima22), "brasil_acima_em_2022": todos22,
        "excesso_2022": sum(x["aptos_2022"] - x["censo_2022"] for x in acima22),
        "cresc_eleitorado_mediano": round(st.median(cresc_cad), 4),
        "cresc_eleitorado_mediano_brasil": round(st.median(cresc_br), 4),
        "lista": sorted(ja22, key=lambda x: -x["razao_2022"])}

    # ---------- 2. crescimento
    muns = json.load(open(DOSSIE / "municipios.json", encoding="utf-8"))
    alvo = [m for m in muns if "z_cresc" in (m["alertas"] or "")]
    cr = []
    for m in alvo:
        k = nomes.get(m["id"])
        if k not in censo or k not in est25 or m["id"] not in a22 or m["id"] not in a26:
            continue
        cr.append({"id": m["id"], "municipio": m["municipio"], "cresc_votos": m["cresc_validos"],
                   "cresc_eleitorado": round(a26[m["id"]] / a22[m["id"]] - 1, 4),
                   "cresc_populacao": round(est25[k] / censo[k] - 1, 4),
                   "aptos_pop_2025": round(a26[m["id"]] / est25[k], 3)})
    pop_br = [est25[k] / censo[k] - 1 for k in censo if k in est25]
    acompanha = [x for x in cr if x["cresc_populacao"] >= st.median(pop_br) * 2 or x["cresc_eleitorado"] <= x["cresc_populacao"] + .05]
    out["crescimento"] = {
        "municipios": len(alvo), "medidos": len(cr),
        "pop_cresceu_mais_que_o_dobro_do_brasil": sum(1 for x in cr if x["cresc_populacao"] >= st.median(pop_br) * 2),
        "eleitorado_ate_5pts_acima_da_pop": sum(1 for x in cr if x["cresc_eleitorado"] <= x["cresc_populacao"] + .05),
        "explicados": len(acompanha),
        "pop_mediana_brasil": round(st.median(pop_br), 4),
        "eleit_mediano_brasil": round(st.median(cresc_br), 4),
        "lista": cr}

    # ---------- 3 e 4. 2o turno de 2022 por municipio
    m22 = defaultdict(lambda: defaultdict(int))     # (mun, turno) -> votavel -> votos
    with open(RAIZ / "dados/votacao_secao_2022_BR.csv", encoding="latin-1", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        i = {c: n for n, c in enumerate(next(rd))}
        for L in rd:
            if L[i["CD_CARGO"]] != "1" or L[i["SG_UF"]] == "ZZ":
                continue
            k = f"{L[i['SG_UF']]}-{int(L[i['CD_MUNICIPIO']])}"
            m22[(k, L[i["NR_TURNO"]])][L[i["NR_VOTAVEL"]]] += int(L[i["QT_VOTOS"]])
    t26 = {}
    for r in csv.DictReader(open(RAIZ / "dados/totais_2t_municipio_6258.csv", encoding="utf-8")):
        t26[f"{r['uf']}-{int(r['cd_municipio'])}"] = r

    # 3. anomalias 2T x 2T, mesma regra (chave com a UF nos 2 primeiros caracteres)
    ma = {k.replace("-", ""): {"13": v["13"], "22": v["22"]} for (k, t), v in m22.items() if t == "2"}
    mb = {k.replace("-", ""): {"13": int(r["lula"]), "22": int(r["flavio"])} for k, r in t26.items() if r["uf"] != "ZZ"}
    an = anormais(ma, mb)
    vir1t = {v["id"].replace("-", "") for v in json.load(open(DOSSIE / "viradas_casos.json", encoding="utf-8"))}
    out["viradas"] = {
        "anomalas_2t": len(an), "comparados": len(ma.keys() & mb.keys()),
        "das_7_do_1t_tambem_no_2t": sorted(k for k, _, _ in an if k in vir1t),
        "lista_2t": [{"id": f"{k[:2]}-{k[2:]}", "variacao": round(x, 4), "mediana_estado": round(m, 4)} for k, x, m in an]}

    # 4. Flavio perdeu votos: controle 2022
    mig = {m["id"]: m for m in json.load(open(RAIZ / "resultados/migracao.json"))["municipios"]}
    perdeu26 = {k for k, m in mig.items() if m["flavio2"] < m["flavio1"]}
    perdeu22, base = set(), 0
    for k in mig:
        a, b = m22.get((k, "1")), m22.get((k, "2"))
        if not a or not b:
            continue
        base += 1
        if b["22"] < a["22"]:
            perdeu22.add(k)
    comp = []
    for k in perdeu26:
        m = mig[k]
        comp.append((m["flavio2"] - m["flavio1"], m["comp2"] - m["comp1"]))
    queda = [c for c in comp if c[1] < 0]
    por_uf = defaultdict(lambda: [0, 0])
    for k in perdeu26:
        por_uf[k[:2]][0] += 1
        por_uf[k[:2]][1] += k in perdeu22
    out["flavio_perdeu"] = {
        "municipios_2026": len(perdeu26), "bolsonaro_perdeu_2022": len(perdeu22), "comparados_2022": base,
        "nos_dois_anos": len(perdeu26 & perdeu22),
        "com_queda_de_comparecimento": len(queda),
        "perda_total": -sum(c[0] for c in comp),
        "perda_onde_comparecimento_caiu": -sum(c[0] for c in queda),
        "por_uf": {u: {"2026": v[0], "tambem_2022": v[1]} for u, v in sorted(por_uf.items())}}

    (RAIZ / "resultados/pendencias.json").write_text(json.dumps(out, ensure_ascii=False))
    c, g, v, f = out["cadastro"], out["crescimento"], out["viradas"], out["flavio_perdeu"]
    txt = [
        "PENDENCIAS FECHADAS",
        f"1. Cadastro: dos {c['municipios']} municipios, {c['casados_censo']} casados com o Censo; "
        f"{c['ja_acima_em_2022']} ja tinham mais eleitores que moradores CONTADOS em 2022 "
        f"(Brasil: {c['brasil_acima_em_2022']}), excesso {c['excesso_2022']}; eleitorado 2022->2026 "
        f"mediano {c['cresc_eleitorado_mediano']:.1%} (Brasil {c['cresc_eleitorado_mediano_brasil']:.1%})",
        f"2. Crescimento: {g['medidos']}/{g['municipios']} medidos; populacao cresceu >= 2x a mediana "
        f"({g['pop_mediana_brasil']:.1%}) em {g['pop_cresceu_mais_que_o_dobro_do_brasil']}; eleitorado ate 5 pts "
        f"acima da populacao em {g['eleitorado_ate_5pts_acima_da_pop']}; explicados {g['explicados']}"]
    txt += [f"   {x['id']} {x['municipio']}: votos {x['cresc_votos']:+.1%} eleitorado {x['cresc_eleitorado']:+.1%} "
            f"populacao {x['cresc_populacao']:+.1%} aptos/pop {x['aptos_pop_2025']}" for x in g["lista"]]
    txt += [f"3. Viradas no 2T x 2T: {v['anomalas_2t']} de {v['comparados']}; das 7 do 1T tambem no 2T: {v['das_7_do_1t_tambem_no_2t']}"]
    txt += [f"   {x['id']} {x['variacao']:+.1%} (estado {x['mediana_estado']:+.1%})" for x in v["lista_2t"]]
    txt += [f"4. Flavio perdeu votos: {f['municipios_2026']} em 2026; Bolsonaro perdeu em {f['bolsonaro_perdeu_2022']} "
            f"de {f['comparados_2022']} em 2022; nos dois anos {f['nos_dois_anos']}; com queda de comparecimento "
            f"{f['com_queda_de_comparecimento']}; perda total {f['perda_total']}, onde o comparecimento caiu {f['perda_onde_comparecimento_caiu']}"]
    txt += [f"   {u}: {x['2026']} ({x['tambem_2022']} tambem em 2022)" for u, x in f["por_uf"].items()]
    (RAIZ / "resultados/pendencias.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
