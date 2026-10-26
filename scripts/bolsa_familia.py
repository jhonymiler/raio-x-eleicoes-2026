#!/usr/bin/env python3
"""Bolsa Familia x mudanca de voto entre os turnos, por municipio.

1. Agrega o arquivo do Portal da Transparencia (uma linha por familia paga)
   em familias e valor por municipio. So o agregado e gravado: nomes, CPF e
   NIS nao saem do zip.
2. Cruza com os totais do 1o e do 2o turno: cobertura = familias / aptos.
3. Pergunta: onde o Flavio perdeu votos (938 municipios) a cobertura e maior?
   E o efeito sobrevive ao controle por estado e pela parcela do Lula no 1T?
   (Cobertura alta e voto no Lula andam juntos; sem o controle, a correlacao
   so repete o mapa do 1o turno.)

Entradas: dados/bolsa_familia_<aaaamm>.zip (portaldatransparencia.gov.br,
          novo-bolsa-familia), resultados/migracao.json
Saida:    dados/derivados/bolsa_familia_mun_<aaaamm>.csv, resultados/bolsa_familia.{txt,json}
Uso:      python3 scripts/bolsa_familia.py [aaaamm]      (padrao 202608)
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
from idade_biometria import ols  # noqa: E402
from realidade import norm  # noqa: E402

RAIZ = Path(__file__).parent.parent


def agregar(mes: str) -> Path:
    saida = RAIZ / f"dados/derivados/bolsa_familia_mun_{mes}.csv"
    if saida.exists():
        return saida
    agg: dict = defaultdict(lambda: [0, 0.0, 0])
    with zipfile.ZipFile(RAIZ / f"dados/bolsa_familia_{mes}.zip") as z:
        with z.open(z.namelist()[0]) as bfh:
            rd = csv.reader(io.TextIOWrapper(bfh, encoding="latin-1", newline=""), delimiter=";")
            next(rd)
            for L in rd:
                a = agg[(L[2], L[3], L[4])]
                a[0] += 1
                a[1] += float(L[8].replace(".", "").replace(",", "."))
                a[2] += L[1] == L[0]            # parcela do proprio mes (nao retroativa)
    with open(saida, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["uf", "siafi", "municipio", "parcelas", "valor", "parcelas_do_mes"])
        for (uf, sf, nome), (n, v, nm) in sorted(agg.items()):
            w.writerow([uf, sf, nome, n, f"{v:.2f}", nm])
    return saida


def main(mes: str = "202608") -> None:
    bf = {}
    with open(agregar(mes), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            bf[(r["uf"], norm(r["municipio"]))] = (int(r["parcelas_do_mes"]), float(r["valor"]))
    mig = json.loads((RAIZ / "resultados/migracao.json").read_text())["municipios"]
    linhas, nao = [], []
    for m in mig:
        k = (m["uf"], norm(m["municipio"]))
        if k not in bf:
            nao.append(f"{m['uf']} {m['municipio']}")
            continue
        fam, val = bf[k]
        a1 = m["aptos"]
        if not a1 or not (m["lula1"] + m["flavio1"]) or not (m["lula2"] + m["flavio2"]):
            continue
        linhas.append({**m, "familias": fam, "valor": val, "cob": fam / a1,
                       "s1": m["lula1"] / (m["lula1"] + m["flavio1"]),
                       "mud": m["lula2"] / (m["lula2"] + m["flavio2"]) - m["lula1"] / (m["lula1"] + m["flavio1"]),
                       "dflavio": (m["flavio2"] - m["flavio1"]) / m["flavio1"] if m["flavio1"] else 0,
                       "dcomp": (m["comp2"] - m["comp1"]) / m["comp1"] if m["comp1"] else 0})

    # efeitos fixos de estado: centra tudo dentro da UF
    vs = ["mud", "dflavio", "dcomp", "cob", "s1"]
    por_uf = defaultdict(list)
    for L in linhas:
        por_uf[L["uf"]].append(L)
    for ls in por_uf.values():
        med = {v: st.fmean(L[v] for L in ls) for v in vs}
        for L in ls:
            for v in vs:
                L["c_" + v] = L[v] - med[v]

    T: list[str] = []
    w = T.append
    w(f"BOLSA FAMILIA ({mes}) x MUDANCA ENTRE OS TURNOS -- {len(linhas):,} municipios "
      f"({len(nao)} sem par de nome)")
    w(f"familias: {sum(L['familias'] for L in linhas):,}  valor R$ {sum(L['valor'] for L in linhas):,.0f}")
    w("cobertura = familias beneficiarias / eleitores aptos\n")

    perdeu = [L for L in linhas if L["flavio2"] < L["flavio1"]]
    resto = [L for L in linhas if L["flavio2"] >= L["flavio1"]]
    w(f"Flavio perdeu votos: {len(perdeu)} municipios, cobertura mediana {st.median(L['cob'] for L in perdeu):.1%}"
      f" | demais: {len(resto)}, {st.median(L['cob'] for L in resto):.1%}")
    w(f"   parcela do Lula no 1T, mediana: {st.median(L['s1'] for L in perdeu):.1%} x {st.median(L['s1'] for L in resto):.1%}")
    w(f"   variacao do comparecimento, mediana: {st.median(L['dcomp'] for L in perdeu):+.1%} x "
      f"{st.median(L['dcomp'] for L in resto):+.1%}")

    w("\npor faixa de cobertura (Brasil inteiro):")
    w(f"   {'cobertura':<12}{'municipios':>11}{'Lula 1T':>9}{'mudanca Lula':>14}{'var. Flavio':>13}"
      f"{'var. compar.':>14}{'Flavio perdeu':>15}")
    faixas = [0, .05, .10, .15, .20, .25, .30, .40, 9]
    for a, b in zip(faixas, faixas[1:]):
        g = [L for L in linhas if a <= L["cob"] < b]
        if g:
            w(f"   {f'{a:.0%}-{b:.0%}' if b < 9 else f'>= {a:.0%}':<12}{len(g):>11}"
              f"{st.median(L['s1'] for L in g):>9.1%}{st.median(L['mud'] for L in g)*100:>+12.2f}pp"
              f"{st.median(L['dflavio'] for L in g):>+13.1%}{st.median(L['dcomp'] for L in g):>+14.1%}"
              f"{sum(L['flavio2'] < L['flavio1'] for L in g) / len(g):>15.0%}")

    w("\nregressao dentro do estado (efeito fixo de UF), por +10 pontos de cobertura:")
    res = {}
    for y, rot in (("mud", "mudanca do Lula (pp)"), ("dflavio", "variacao do Flavio (%)"),
                   ("dcomp", "variacao do comparecimento (%)")):
        for ctl in (False, True):
            xs = [[L["c_cob"] for L in linhas]] + ([[L["c_s1"] for L in linhas]] if ctl else [])
            r = ols([L["c_" + y] for L in linhas], xs)
            c = r[0]
            res[f"{y}{'_ctl' if ctl else ''}"] = c
            w(f"   {rot:<32}{'+ controle Lula 1T' if ctl else 'so cobertura':<20}"
              f"{c['coef'] * 10:+7.2f}  z={c['z']:+6.1f}")

    texto = "\n".join(T)
    print(texto)
    (RAIZ / "resultados/bolsa_familia.txt").write_text(texto + "\n")
    (RAIZ / "resultados/bolsa_familia.json").write_text(json.dumps(
        {"mes": mes, "regressoes": res, "sem_par": nao,
         "municipios": [{k: L[k] for k in ("id", "uf", "municipio", "familias", "valor", "cob", "s1", "mud",
                                          "dflavio", "dcomp")} for L in linhas]}, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:2])
