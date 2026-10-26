#!/usr/bin/env python3
"""Matriz de transferencia de votos 1o -> 2o turno (inferencia ecologica).

Para cada estado, estima a fracao dos eleitores de cada opcao do 1o turno
(Lula, Flavio, Cury, Renan, Caiado, Zema, outros, branco/nulo, abstencao)
que foi para cada opcao do 2o turno (Lula, Flavio, branco/nulo, abstencao).

Modelo de Goodman em proporcoes do eleitorado apto, ponderado pelo aptos:
    y_jm = sum_k x_km * b_kj      com  b_kj >= 0  e  sum_j b_kj = 1
As restricoes (cada linha e uma divisao de 100% de um eleitorado) e o ajuste
por estado tiram a instabilidade da regressao livre de transferencia.py
(coeficientes negativos ou acima de 100%). Fluxos = sum_m aptos_m x_km b_kj.

Robustez: (a) ajuste por estado x tercil da parcela do Lula no 1T, que deixa
o comportamento variar dentro do estado; (b) bootstrap de municipios.

E inferencia, nao contagem: o voto e secreto e so ha totais por municipio.

Entradas: dados/derivados/secoes_pres_1t_2026.csv.gz, dados/votacao_secao_2026_BR.csv,
          dados/totais_2t_municipio_6258.csv
Saida:    resultados/matriz_transferencia.{txt,json}
Uso:      python3 scripts/matriz_transferencia.py [reps_bootstrap]
          python3 scripts/matriz_transferencia.py 2022   (controle municipio x secao)
"""

from __future__ import annotations

import csv
import gzip
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).parent.parent
ORIGENS = ["lula", "flavio", "cury", "renan", "caiado", "zema", "outros", "bn", "abst"]
ROT_O = {"lula": "Lula (1T)", "flavio": "Flávio (1T)", "cury": "Augusto Cury",
         "renan": "Renan Santos", "caiado": "Ronaldo Caiado", "zema": "Romeu Zema",
         "outros": "demais eliminados", "bn": "branco/nulo (1T)", "abst": "não votou (1T)"}
DESTINOS = ["lula", "flavio", "bn", "abst"]
ROT_D = {"lula": "Lula", "flavio": "Flávio", "bn": "bra/nulo", "abst": "não votou"}
NOMES = {"AUGUSTO JORGE CURY": "cury", "RENAN ANTONIO": "renan",
         "RONALDO RAMOS CAIADO": "caiado", "ROMEU ZEMA": "zema"}
BLOCOS = {"eliminados (todos)": ["cury", "renan", "caiado", "zema", "outros"],
          "Renan+Caiado+Zema": ["renan", "caiado", "zema"]}
REGIAO = {**dict.fromkeys(["AC", "AM", "AP", "PA", "RO", "RR", "TO"], "Norte"),
          **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Nordeste"),
          **dict.fromkeys(["DF", "GO", "MS", "MT"], "Centro-Oeste"),
          **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Sudeste"),
          **dict.fromkeys(["PR", "RS", "SC"], "Sul")}


def chave(uf, mun):
    return uf.upper() + str(int(mun))


def carregar():
    t1: dict = defaultdict(lambda: dict.fromkeys(ORIGENS, 0))
    with open(RAIZ / "dados/votacao_secao_2026_BR.csv", encoding="latin-1", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        i = {c: n for n, c in enumerate(next(rd))}
        for L in rd:
            if L[i["CD_CARGO"]] != "1" or L[i["SG_UF"]] == "ZZ":
                continue
            nr, nome = L[i["NR_VOTAVEL"]], L[i["NM_VOTAVEL"]]
            cat = ("lula" if nr == "13" else "flavio" if nr == "22" else "bn" if int(nr) >= 95
                   else next((c for p, c in NOMES.items() if p in nome), "outros"))
            t1[chave(L[i["SG_UF"]], L[i["CD_MUNICIPIO"]])][cat] += int(L[i["QT_VOTOS"]])
    ap1: dict = defaultdict(lambda: [0, 0])
    with gzip.open(RAIZ / "dados/derivados/secoes_pres_1t_2026.csv.gz", "rt", encoding="utf-8") as fh:
        for L in csv.DictReader(fh, delimiter=";"):
            if L["uf"] != "ZZ":
                a = ap1[chave(L["uf"], L["mun"])]
                a[0] += int(L["aptos"])
                a[1] += int(L["comp"])
    muns = []
    with open(RAIZ / "dados/totais_2t_municipio_6258.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            k = chave(r["uf"], r["cd_municipio"])
            if r["uf"] == "ZZ" or k not in t1 or k not in ap1:
                continue
            x = t1[k]
            aptos1, comp1 = ap1[k]
            x["abst"] = aptos1 - comp1
            a2, c2 = int(r["aptos"]), int(r["comparecimento"])
            y = {"lula": int(r["lula"]), "flavio": int(r["flavio"]),
                 "bn": int(r["brancos"]) + int(r["nulos"]), "abst": a2 - c2}
            if aptos1 <= 0 or a2 <= 0:
                continue
            muns.append({"id": k, "uf": r["uf"], "nome": r["nm_municipio"], "n": aptos1,
                         "x": [x[o] / aptos1 for o in ORIGENS],
                         "y": [y[d] / a2 for d in DESTINOS], "X": x, "Y": y})
    return muns


def proj_simplex(v):
    u = sorted(v, reverse=True)
    acum, theta = 0.0, 0.0
    for i, ui in enumerate(u, 1):
        acum += ui
        t = (acum - 1) / i
        if ui - t > 0:
            theta = t
    return [max(a - theta, 0.0) for a in v]


def gram(muns, pesos=None):
    K, J = len(muns[0]["x"]), len(muns[0]["y"])
    G = [[0.0] * K for _ in range(K)]
    H = [[0.0] * J for _ in range(K)]
    for t, m in enumerate(muns):
        w = m["n"] * (pesos[t] if pesos else 1)
        if not w:
            continue
        x, y = m["x"], m["y"]
        for a in range(K):
            wa = w * x[a]
            if not wa:
                continue
            Ga, Ha = G[a], H[a]
            for b in range(K):
                Ga[b] += wa * x[b]
            for j in range(J):
                Ha[j] += wa * y[j]
    return G, H


def ajustar(G, H, B=None, sweeps=3000):
    """Descida por blocos: cada linha e o minimo exato sobre o simplex."""
    K, J = len(G), len(H[0])
    B = [r[:] for r in B] if B else [[1.0 / J] * J for _ in range(K)]
    for _ in range(sweeps):
        mud = 0.0
        for k in range(K):
            if G[k][k] <= 0:
                continue
            v = [(H[k][j] - sum(G[k][l] * B[l][j] for l in range(K) if l != k)) / G[k][k]
                 for j in range(J)]
            novo = proj_simplex(v)
            mud = max(mud, max(abs(a - b) for a, b in zip(novo, B[k])))
            B[k] = novo
        if mud < 1e-10:
            break
    return B


def fluxos(muns, B):
    K, J = len(B), len(B[0])
    F = [[0.0] * J for _ in range(K)]
    for m in muns:
        for k in range(K):
            xk = m["x"][k] * m["n"]
            for j in range(J):
                F[k][j] += xk * B[k][j]
    return F


def grupos_estado(muns):
    g = defaultdict(list)
    for m in muns:
        g[m["uf"]].append(m)
    return g


def grupos_tercil(muns):
    g = defaultdict(list)
    for uf, ms in grupos_estado(muns).items():
        # x[0] e x[1] sao sempre os dois finalistas
        ms = sorted(ms, key=lambda m: m["x"][0] / max(1e-12, m["x"][0] + m["x"][1]))
        for i, m in enumerate(ms):
            g[(uf, 3 * i // len(ms))].append(m)
    return g


def estimar(grupos):
    um = next(iter(grupos.values()))[0]
    K, J = len(um["x"]), len(um["y"])
    F = [[0.0] * J for _ in range(K)]
    Bs, Fg = {}, {}
    for g, ms in grupos.items():
        B = ajustar(*gram(ms))
        f = fluxos(ms, B)
        Bs[g], Fg[g] = B, f
        for k in range(K):
            for j in range(J):
                F[k][j] += f[k][j]
    return F, Bs, Fg


def validar_2022() -> None:
    """Controle: o mesmo modelo em 2022 com municipios e com secoes.

    Secoes (~400 eleitores, uma escola) sao muito mais homogeneas que
    municipios. Se as duas estimativas batem, o vies de agregacao do ajuste
    por municipio -- o unico possivel em 2026 -- e pequeno."""
    import io
    import zipfile

    org = ["lula", "bolsonaro", "tebet", "ciro", "outros", "bn", "abst"]
    rot = {"lula": "Lula (1T)", "bolsonaro": "Bolsonaro (1T)", "tebet": "Simone Tebet",
           "ciro": "Ciro Gomes", "outros": "demais", "bn": "branco/nulo (1T)", "abst": "não votou (1T)"}
    cat1 = {"13": 0, "22": 1, "15": 2, "12": 3}
    v1: dict = defaultdict(lambda: [0] * 7)
    v2: dict = defaultdict(lambda: [0] * 4)
    with open(RAIZ / "dados/votacao_secao_2022_BR.csv", encoding="latin-1", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        next(rd)
        for L in rd:
            if L[17] != "1" or L[10] == "ZZ":
                continue
            k, nr, q = (L[10], L[13], L[15], L[16]), L[19], int(L[21])
            if L[5] == "1":
                v1[k][5 if int(nr) >= 95 else cat1.get(nr, 4)] += q
            else:
                v2[k][0 if nr == "13" else 1 if nr == "22" else 2] += q
    ap: dict = {}
    with zipfile.ZipFile(RAIZ / "dados/detalhe_votacao_secao_2022.zip") as z:
        with z.open("detalhe_votacao_secao_2022_BRASIL.csv") as bfh:
            rd = csv.reader(io.TextIOWrapper(bfh, encoding="latin-1", newline=""), delimiter=";")
            i = {c: n for n, c in enumerate(next(rd))}
            for L in rd:
                if L[i["CD_CARGO"]] != "1" or L[i["SG_UF"]] == "ZZ":
                    continue
                k = (L[i["SG_UF"]], L[i["CD_MUNICIPIO"]], L[i["NR_ZONA"]], L[i["NR_SECAO"]])
                ap[(k, L[i["NR_TURNO"]])] = (int(L[i["QT_APTOS"]]), int(L[i["QT_COMPARECIMENTO"]]))
    secoes, mun = [], defaultdict(lambda: [[0] * 7, [0] * 4])
    for k in v1.keys() & v2.keys():
        a1, a2 = ap.get((k, "1")), ap.get((k, "2"))
        if not a1 or not a2 or a1[0] <= 0 or a2[0] <= 0:
            continue
        x, y = v1[k][:], v2[k][:]
        x[6], y[3] = a1[0] - a1[1], a2[0] - a2[1]
        secoes.append({"uf": k[0], "n": a1[0], "x": [c / a1[0] for c in x], "y": [c / a2[0] for c in y]})
        M = mun[(k[0], k[1])]
        for t in range(7):
            M[0][t] += x[t]
        for t in range(4):
            M[1][t] += y[t]
    muns = []
    for (uf, _), (x, y) in mun.items():
        n1, n2 = sum(x), sum(y)
        muns.append({"uf": uf, "n": n1, "x": [c / n1 for c in x], "y": [c / n2 for c in y]})
    tot1 = [sum(s["x"][t] * s["n"] for s in secoes) for t in range(7)]
    res = {}
    for nome, us in (("municípios", muns), ("seções", secoes)):
        F, _, _ = estimar(grupos_estado(us))
        res[nome] = F
    L: list[str] = []
    w = L.append
    w(f"CONTROLE 2022: mesmo modelo, {len(muns):,} municipios x {len(secoes):,} secoes (ajuste por estado)")
    w("fracao de cada origem do 1T para Lula / Bolsonaro / bra-nulo / nao votou no 2T\n")
    for t, o in enumerate(org):
        for nome, F in res.items():
            w(f"   {rot[o] if nome == 'municípios' else '':<18}{nome:<11}{tot1[t]:>12,.0f}  " +
              "  ".join(f"{F[t][j]/tot1[t]*100:5.1f}%" for j in range(4)))
    elim = [2, 3, 4]
    n = sum(tot1[t] for t in elim)
    for nome, F in res.items():
        w(f"   {'eliminados':<18}{nome:<11}{n:>12,.0f}  " +
          "  ".join(f"{sum(F[t][j] for t in elim)/n*100:5.1f}%" for j in range(4)))
    texto = "\n".join(L)
    print(texto)
    (RAIZ / "resultados/matriz_transferencia_2022.txt").write_text(texto + "\n")


def main(reps: int = 100) -> None:
    muns = carregar()
    est = grupos_estado(muns)
    F, Bs, Fg = estimar(est)
    F3, _, Fg3 = estimar(grupos_tercil(muns))
    Fuf3 = {uf: [[sum(Fg3[(uf, t)][k][j] for t in range(3) if (uf, t) in Fg3)
                  for j in range(len(DESTINOS))] for k in range(len(ORIGENS))] for uf in Fg}

    rng = random.Random(2026)
    boot = []
    boot_uf = defaultdict(list)
    for _ in range(reps):
        Fb = [[0.0] * len(DESTINOS) for _ in ORIGENS]
        for uf, ms in est.items():
            w = [0] * len(ms)
            for _ in ms:
                w[rng.randrange(len(ms))] += 1
            B = ajustar(*gram(ms, w), B=Bs[uf], sweeps=500)
            f = fluxos(ms, B)
            boot_uf[uf].append(f)
            for k in range(len(ORIGENS)):
                for j in range(len(DESTINOS)):
                    Fb[k][j] += f[k][j]
        boot.append(Fb)

    def ic(k, j):
        v = sorted(b[k][j] for b in boot)
        return (v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]) if v else (0, 0)

    tot1 = {o: sum(m["X"][o] for m in muns) for o in ORIGENS}
    tot2 = {d: sum(m["Y"][d] for m in muns) for d in DESTINOS}
    prev = {d: sum(F[k][j] for k in range(len(ORIGENS))) for j, d in enumerate(DESTINOS)}

    L: list[str] = []
    w = L.append
    w(f"MATRIZ DE TRANSFERENCIA 1T -> 2T  ({len(muns):,} municipios, ajuste por estado)")
    w("fracao de cada origem do 1T que foi para cada destino no 2T; [IC 95% bootstrap]\n")
    w(f"{'origem (1T)':<20}{'eleitores':>12}  " + "".join(f"{ROT_D[d]:>22}" for d in DESTINOS))
    for k, o in enumerate(ORIGENS):
        cel = []
        for j in range(len(DESTINOS)):
            a, b = ic(k, j)
            fr = F[k][j] / tot1[o] if tot1[o] else 0
            cel.append(f"{fr*100:5.1f}% [{a/tot1[o]*100:4.0f}-{b/tot1[o]*100:3.0f}]".rjust(22))
        w(f"{ROT_O[o]:<20}{tot1[o]:>12,}  " + "".join(cel))
    w("\nblocos (mais estáveis que a divisão candidato a candidato):")
    for nome, os_ in BLOCOS.items():
        ks = [ORIGENS.index(o) for o in os_]
        n = sum(tot1[o] for o in os_)
        cel = []
        for j in range(len(DESTINOS)):
            v = sorted(sum(b[k][j] for k in ks) for b in boot)
            a, b = (v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]) if v else (0, 0)
            cel.append(f"{sum(F[k][j] for k in ks)/n*100:5.1f}% [{a/n*100:4.0f}-{b/n*100:3.0f}]".rjust(22))
        w(f"{nome:<20}{n:>12,}  " + "".join(cel))
        w(f"{'  (estado x tercil)':<34}" + "".join(
            f"{sum(F3[k][j] for k in ks)/n*100:5.1f}%".rjust(22) for j in range(len(DESTINOS))))

    w("\nmesmos fluxos em votos:")
    w(f"{'origem (1T)':<20}" + "".join(f"{ROT_D[d]:>14}" for d in DESTINOS))
    for k, o in enumerate(ORIGENS):
        w(f"{ROT_O[o]:<20}" + "".join(f"{F[k][j]:>14,.0f}" for j in range(len(DESTINOS))))
    w(f"{'previsto 2T':<20}" + "".join(f"{prev[d]:>14,.0f}" for d in DESTINOS))
    w(f"{'real 2T':<20}" + "".join(f"{tot2[d]:>14,}" for d in DESTINOS))

    w("\nrobustez -- ajuste por estado x tercil do Lula (fracao para Lula / Flavio / bra-nulo / nao votou):")
    for k, o in enumerate(ORIGENS):
        w(f"   {ROT_O[o]:<20}" + "  ".join(f"{F3[k][j]/tot1[o]*100:5.1f}%" for j in range(len(DESTINOS))))

    # de onde veio a virada: margem Lula - Flavio
    il, if_ = DESTINOS.index("lula"), DESTINOS.index("flavio")
    w("\nDE ONDE VEIO A VIRADA (margem Lula - Flávio)")
    m1 = tot1["lula"] - tot1["flavio"]
    w(f"   margem no 1T: {m1:+,}")
    # contribuicao de cada origem para a mudanca da margem; para as bases de
    # Lula e Flavio e o que elas deixaram de dar ao proprio candidato
    contrib = {o: F[k][il] - F[k][if_] - (tot1[o] if o == "lula" else -tot1[o] if o == "flavio" else 0)
               for k, o in enumerate(ORIGENS)}
    for o, c in sorted(contrib.items(), key=lambda t: -abs(t[1])):
        w(f"   {ROT_O[o]:<22}{c:+14,.0f}")
    w(f"   {'soma = virada':<22}{sum(contrib.values()):+14,.0f}")
    w(f"   {'(previsto) margem 2T':<22}{prev['lula'] - prev['flavio']:+14,.0f}   real {tot2['lula'] - tot2['flavio']:+,}")

    w("\nPOR REGIAO (votos, fluxos estimados; margem real)")
    reg = defaultdict(lambda: defaultdict(float))
    for uf, f in Fg.items():
        r = REGIAO[uf]
        for k, o in enumerate(ORIGENS):
            for j, d in enumerate(DESTINOS):
                reg[r][(o, d)] += f[k][j]
    for uf, ms in est.items():
        r = REGIAO[uf]
        for m in ms:
            reg[r]["m1"] += m["X"]["lula"] - m["X"]["flavio"]
            reg[r]["m2"] += m["Y"]["lula"] - m["Y"]["flavio"]
            reg[r]["abst1"] += m["X"]["abst"]
            reg[r]["abst2"] += m["Y"]["abst"]
    for r in ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]:
        d = reg[r]
        elim = [o for o in ORIGENS if o in ("cury", "renan", "caiado", "zema", "outros")]
        el = sum(d[(o, "lula")] for o in elim)
        ef = sum(d[(o, "flavio")] for o in elim)
        w(f"   {r:<13} margem {d['m1']:+12,.0f} -> {d['m2']:+12,.0f} (virada {d['m2'] - d['m1']:+11,.0f}) | "
          f"eliminados: Lula {el:,.0f} Flávio {ef:,.0f} | novos eleitores: Lula {d[('abst', 'lula')]:,.0f} "
          f"Flávio {d[('abst', 'flavio')]:,.0f} | abstenção {d['abst1']:,.0f} -> {d['abst2']:,.0f}")

    # por estado: bloco da direita (Renan+Caiado+Zema) e todos os eliminados.
    # Valor central = media dos dois ajustes (estado e estado x tercil); a
    # faixa junta o IC 95% do bootstrap e o ajuste por tercil.
    por_uf = {}
    for uf in sorted(Fg):
        ms = est[uf]
        r = {"uf": uf}
        for nome, os_ in (("direita", ("renan", "caiado", "zema")),
                          ("elim", ("cury", "renan", "caiado", "zema", "outros"))):
            ks = [ORIGENS.index(o) for o in os_]
            n = sum(m["X"][o] for m in ms for o in os_)
            r[nome] = {"n": n}
            for d, j in (("lula", il), ("flavio", if_)):
                a = sum(Fg[uf][k][j] for k in ks)
                b = sum(Fuf3[uf][k][j] for k in ks)
                bs = sorted(sum(f[k][j] for k in ks) for f in boot_uf[uf])
                lo = min([a, b] + ([bs[int(.025 * len(bs))]] if bs else []))
                hi = max([a, b] + ([bs[int(.975 * len(bs)) - 1]] if bs else []))
                r[nome][d] = round((a + b) / 2)
                r[nome][d + "_faixa"] = [round(lo / n, 3), round(hi / n, 3)] if n else [0, 0]
        r["lula1"], r["flavio1"] = sum(m["X"]["lula"] for m in ms), sum(m["X"]["flavio"] for m in ms)
        r["lula2"], r["flavio2"] = sum(m["Y"]["lula"] for m in ms), sum(m["Y"]["flavio"] for m in ms)
        por_uf[uf] = r

    w("\nPOR ESTADO -- eleitores de Renan+Caiado+Zema no 1T e para onde foram (votos; [faixa])")
    w(f"   {'UF':<4}{'direita 1T':>11}{'-> Lula':>11}{'':>12}{'-> Flávio':>11}{'':>12}{'saldo Flávio':>14}")
    for r in sorted(por_uf.values(), key=lambda r: -r["direita"]["n"]):
        d = r["direita"]
        if d["n"]:
            fl, ff = d["lula_faixa"], d["flavio_faixa"]
            w(f"   {r['uf']:<4}{d['n']:>11,}{d['lula']:>11,} [{fl[0]*100:3.0f}-{fl[1]*100:3.0f}%]"
              f"{d['flavio']:>11,} [{ff[0]*100:3.0f}-{ff[1]*100:3.0f}%]{d['flavio'] - d['lula']:>+14,}")

    texto = "\n".join(L)
    print(texto)
    (RAIZ / "resultados/matriz_transferencia.txt").write_text(texto + "\n")
    out = {"origens": ORIGENS, "destinos": DESTINOS, "eleitores_1t": tot1, "real_2t": tot2,
           "fluxos": F, "fluxos_tercil": F3,
           "ic95": [[ic(k, j) for j in range(len(DESTINOS))] for k in range(len(ORIGENS))],
           "por_estado": {uf: Fg[uf] for uf in sorted(Fg)}, "por_uf": por_uf}
    (RAIZ / "resultados/matriz_transferencia.json").write_text(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1:2] == ["2022"]:
        validar_2022()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 100)
