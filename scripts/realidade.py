#!/usr/bin/env python3
"""Os numeros da eleicao cabem na populacao real?

Compara, por municipio, eleitores aptos e comparecimento do 2o turno de 2026
com a populacao residente estimada pelo IBGE para 2025. Cadastro inflado ou
voto inventado aparecem como mais eleitores (ou votantes) do que gente.

  aptos / populacao : no Brasil ~0,75 (cerca de 78% da populacao tem 16+).
                      Acima de 1 = mais eleitores do que moradores.
  comparecimento / populacao : acima de ~0,8 seria quase todo adulto votando.

Controle: municipios pequenos de onde as pessoas migram mantem o titulo na
cidade de origem; o cadastro "inflado" por isso e conhecido e antigo. Por
isso o teste decisivo e se o excesso se relaciona com a MUDANCA de voto
entre os turnos dentro do mesmo estado, e nao com o nivel.

Entradas: dados/ibge/pop_2025.json (SIDRA tabela 6579),
          dados/totais_2t_municipio_6258.csv, resultados/migracao.json
Saida:    resultados/realidade.json
Uso:      python3 scripts/realidade.py
"""

from __future__ import annotations

import csv
import json
import statistics as st
import unicodedata
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).parent.parent


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().upper()
    return "".join(c for c in s if c.isalnum())


# grafias que divergem entre TSE e IBGE (descobertas pelo relatorio de nao casados)
APELIDOS: dict[tuple[str, str], str] = {}


def main() -> None:
    pop = {}
    for L in json.loads((RAIZ / "dados/ibge/pop_2025.json").read_text())[1:]:
        nome, uf = L["D1N"].rsplit(" - ", 1)
        pop[(uf, norm(nome))] = (int(L["V"]), L["D1C"], nome)
    linhas, nao = [], []
    with open(RAIZ / "dados/totais_2t_municipio_6258.csv", encoding="utf-8") as fh:
        for L in csv.DictReader(fh):
            if L["uf"] == "ZZ":
                continue
            k = (L["uf"], APELIDOS.get((L["uf"], norm(L["nm_municipio"])), norm(L["nm_municipio"])))
            if k not in pop:
                nao.append(f"{L['uf']} {L['nm_municipio']}")
                continue
            p, ibge, _ = pop[k]
            apt, comp = int(L["aptos"]), int(L["comparecimento"])
            linhas.append({"id": f"{L['uf']}-{int(L['cd_municipio'])}", "uf": L["uf"],
                           "municipio": L["nm_municipio"], "ibge": ibge, "populacao": p,
                           "aptos": apt, "comparecimento": comp,
                           "aptos_pop": apt / p, "comp_pop": comp / p,
                           "lula": int(L["lula"]), "flavio": int(L["flavio"])})
    mig = {m["id"]: m for m in json.loads((RAIZ / "resultados/migracao.json").read_text())["municipios"]}
    for L in linhas:
        m = mig.get(L["id"])
        if m and m["lula1"] + m["flavio1"] and m["lula2"] + m["flavio2"]:
            L["mudanca_lula"] = (m["lula2"] / (m["lula2"] + m["flavio2"]) -
                                 m["lula1"] / (m["lula1"] + m["flavio1"]))

    # dentro de cada estado: excesso de cadastro x mudanca de voto
    por_uf = defaultdict(list)
    for L in linhas:
        if "mudanca_lula" in L:
            por_uf[L["uf"]].append(L)
    pares = []
    for ls in por_uf.values():
        ma = st.fmean(L["aptos_pop"] for L in ls)
        mm = st.fmean(L["mudanca_lula"] for L in ls)
        pares += [(L["aptos_pop"] - ma, L["mudanca_lula"] - mm) for L in ls]
    sx = sum(a * a for a, _ in pares) ** .5
    sy = sum(b * b for _, b in pares) ** .5
    corr = sum(a * b for a, b in pares) / (sx * sy) if sx and sy else None
    acima = [L for L in linhas if L["aptos_pop"] > 1]
    comp_alto = [L for L in linhas if L["comp_pop"] > .8]

    def faixa(ls):
        return {"municipios": len(ls), "populacao": sum(L["populacao"] for L in ls),
                "aptos": sum(L["aptos"] for L in ls), "comparecimento": sum(L["comparecimento"] for L in ls),
                "lula": sum(L["lula"] for L in ls), "flavio": sum(L["flavio"] for L in ls)}
    out = {
        "casados": len(linhas), "nao_casados": nao,
        "brasil": faixa(linhas) | {"aptos_pop": sum(L["aptos"] for L in linhas) / sum(L["populacao"] for L in linhas),
                                   "comp_pop": sum(L["comparecimento"] for L in linhas) / sum(L["populacao"] for L in linhas)},
        "aptos_acima_populacao": faixa(acima) | {"lista": sorted(acima, key=lambda L: -L["aptos_pop"])[:60]},
        "comparecimento_acima_80": faixa(comp_alto) | {"lista": sorted(comp_alto, key=lambda L: -L["comp_pop"])[:60]},
        "corr_excesso_mudanca_dentro_uf": corr,
        "mediana_aptos_pop": st.median(L["aptos_pop"] for L in linhas),
        "municipios": linhas,
    }
    (RAIZ / "resultados/realidade.json").write_text(json.dumps(out, ensure_ascii=False))
    b = out["brasil"]
    f = lambda x: f"{x:,}".replace(",", ".")
    print(f"casados {len(linhas)} de {len(linhas) + len(nao)}; não casados: {nao[:12]}")
    print(f"Brasil: população {f(b['populacao'])} | aptos {f(b['aptos'])} ({b['aptos_pop']:.1%}) | "
          f"comparecimento {f(b['comparecimento'])} ({b['comp_pop']:.1%}) | mediana aptos/pop {out['mediana_aptos_pop']:.2f}")
    a = out["aptos_acima_populacao"]
    print(f"municípios com mais eleitores que moradores: {a['municipios']} (pop {f(a['populacao'])}, "
          f"aptos {f(a['aptos'])}, Lula {f(a['lula'])}, Flávio {f(a['flavio'])})")
    for L in a["lista"][:12]:
        print(f"   {L['uf']} {L['municipio'][:26]:<26} pop {f(L['populacao']):>7} aptos {f(L['aptos']):>7} ({L['aptos_pop']:.2f}) "
              f"votaram {f(L['comparecimento']):>7} ({L['comp_pop']:.2f})")
    c = out["comparecimento_acima_80"]
    print(f"municípios com comparecimento > 80% da população: {c['municipios']}")
    for L in c["lista"][:8]:
        print(f"   {L['uf']} {L['municipio'][:26]:<26} pop {f(L['populacao']):>7} votaram {f(L['comparecimento']):>7} ({L['comp_pop']:.2f})")
    print(f"correlação (dentro do estado) entre excesso de cadastro e mudança para o Lula: {corr:+.3f}")


if __name__ == "__main__":
    main()
