#!/usr/bin/env python3
"""Investigacao forense do 1o turno de 2026 (Presidente), do macro ao micro.

Nivel 0  integridade: boletim de urna (BU) x totalizacao, secao a secao
Nivel 1  estados: todos os 27 + exterior, com testes validos em qualquer UF
Nivel 2  municipios: o que destoa do proprio estado
Nivel 3  zonas: o que destoa do proprio municipio
Nivel 4  secoes: a urna que destoa das outras secoes da MESMA escola

Indicadores por secao (todos do BU publicado pelo TSE):
  comparecimento/aptos, votos por candidato, eleitores com biometria
  liberados sem ela (QT_ELEI_BIOM_SEM_HABILITACAO), tipo de urna
  (apurada / anulada / nao instalada...), horarios de abertura,
  encerramento e emissao do BU, numero e carga da urna.

Entradas:  dados/bu/bweb_1t_<UF>_*.zip   (lidos sem extrair)
           dados/votacao_secao_2026_BR.csv, dados/votacao_secao_2022_BR.csv
Saidas:    dados/derivados/secoes_pres_1t_2026.csv.gz (uma linha por secao)
           resultados/investigacao.json            (lido pelo painel)

Uso:  python3 scripts/investigar.py [UF ...]     (sem UF = Brasil inteiro)
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import statistics as st
import sys
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import benford as bf  # noqa: E402
import historico  # noqa: E402

RAIZ = Path(__file__).parent.parent
BU_DIR = RAIZ / "dados" / "bu"
DERIV = RAIZ / "dados" / "derivados"
SAIDA = RAIZ / "resultados" / "investigacao.json"

A, B = "13", "22"                   # 1o e 2o colocados nacionais em 2026
NOMES = {A: "Lula", B: "Flávio Bolsonaro"}
PISO = {"z_swing": ("swing", .05), "z_turn": ("turn", .05),
        "z_biom": ("biom_tx", .05), "z_cresc": ("cresc", .15)}
Z_ALERTA = 5.0                      # z robusto; com ~5.570 municipios, z>5 por acaso ~0


def minutos(s: str) -> int | None:
    try:
        h, m = s[11:16].split(":")
        return int(h) * 60 + int(m)
    except (ValueError, IndexError):
        return None


# --------------------------------------------------------------------------
# leitura dos BUs (um processo por UF)
# --------------------------------------------------------------------------

def ler_uf(caminho: str) -> dict:
    z = zipfile.ZipFile(caminho)
    nome = next(n for n in z.namelist() if n.endswith(".csv"))
    secoes: dict = {}
    with io.TextIOWrapper(z.open(nome), encoding="latin-1", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        cab = next(rd)
        i = {c: k for k, c in enumerate(cab)}
        ic = i["CD_CARGO_PERGUNTA"]
        for L in rd:
            if L[ic] != "1":
                continue
            k = (L[i["SG_UF"]], L[i["CD_MUNICIPIO"]], L[i["NR_ZONA"]], L[i["NR_SECAO"]])
            s = secoes.get(k)
            if s is None:
                s = secoes[k] = {
                    "mun_nome": L[i["NM_MUNICIPIO"]], "local": L[i["NR_LOCAL_VOTACAO"]],
                    "aptos": int(L[i["QT_APTOS"]]), "comp": int(L[i["QT_COMPARECIMENTO"]]),
                    "tipo": L[i["CD_TIPO_URNA"]], "urna": L[i["NR_URNA_EFETIVADA"]],
                    "carga": L[i["CD_CARGA_1_URNA_EFETIVADA"]] + L[i["CD_CARGA_2_URNA_EFETIVADA"]],
                    "dt_carga": L[i["DT_CARGA_URNA_EFETIVADA"]],
                    "abre": L[i["DT_ABERTURA"]], "fecha": L[i["DT_ENCERRAMENTO"]],
                    "emite": L[i["DT_EMISSAO_BU"]], "recebe": L[i["DT_BU_RECEBIDO"]],
                    "biom": int(L[i["QT_ELEI_BIOM_SEM_HABILITACAO"]] or -1),
                    "agreg": L[i["DS_SECOES_AGREGADAS"]], "votos": Counter()}
            s["votos"][L[i["NR_VOTAVEL"]]] += int(L[i["QT_VOTOS"]])
    return secoes


def ler_totalizacao() -> Counter:
    tot: Counter = Counter()
    with open(RAIZ / "dados" / "votacao_secao_2026_BR.csv", encoding="latin-1",
              newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        cab = next(rd)
        i = {c: k for k, c in enumerate(cab)}
        for L in rd:
            if L[i["CD_CARGO"]] != "1" or L[i["NR_TURNO"]] != "1":
                continue
            tot[(L[i["SG_UF"]], L[i["CD_MUNICIPIO"]], L[i["NR_ZONA"]],
                 L[i["NR_SECAO"]], L[i["NR_VOTAVEL"]])] += int(L[i["QT_VOTOS"]])
    return tot


# --------------------------------------------------------------------------
# estatistica
# --------------------------------------------------------------------------

def z_robusto(valores: list[float]) -> list[float]:
    """(x - mediana) / (1,4826 * MAD). Imune aos proprios outliers."""
    if len(valores) < 5:
        return [0.0] * len(valores)
    med = st.median(valores)
    mad = st.median(abs(v - med) for v in valores) * 1.4826
    return [(v - med) / mad if mad else 0.0 for v in valores]


def ultimo_digito(valores, minimo: int = 100) -> dict:
    """Ultimo digito deve ser uniforme -- se a densidade for plana dentro de
    cada dezena. Com minimo 40, Lula em RR (contagens 40-59, caindo pela
    metade de uma dezena para a outra) dava p~0 por puro truncamento."""
    c = Counter(v % 10 for v in valores if v >= minimo)
    n = sum(c.values())
    if n < 100:
        return {"n": n, "p": None, "freq": {}}
    f = [c.get(d, 0) / n for d in range(10)]
    chi2 = sum((c.get(d, 0) - n / 10) ** 2 / (n / 10) for d in range(10))
    # densidade decrescente inclina os finais (0 > 9) sem fabricacao nenhuma.
    # fabricacao = 0 e 5 acima da reta ajustada aos outros oito digitos
    xs = [d for d in range(10) if d not in (0, 5)]
    mx, my = st.fmean(xs), st.fmean(f[d] for d in xs)
    incl = sum((d - mx) * (f[d] - my) for d in xs) / sum((d - mx) ** 2 for d in xs)
    reta = lambda d: my + incl * (d - mx)
    exc = (f[0] - reta(0)) + (f[5] - reta(5))
    se = math.sqrt(2 * 0.1 * 0.9 / n)
    return {"n": n, "p": bf.chi2_sf(chi2, 9), "freq": {str(d): f[d] for d in range(10)},
            "inclinacao": incl, "excesso_0_5": exc, "z_0_5": exc / se}


def share(v: Counter, nr: str) -> float | None:
    val = sum(q for k, q in v.items() if k not in ("95", "96"))
    return v.get(nr, 0) / val if val else None


# --------------------------------------------------------------------------
# investigacao
# --------------------------------------------------------------------------

def main() -> None:
    ufs = [u.upper() for u in sys.argv[1:]]          # vazio = todas
    zips = [z for z in sorted(BU_DIR.glob("bweb_1t_*.zip")) if not ufs or z.name[8:10] in ufs]
    print(f"lendo {len(zips)} arquivos de BU...", flush=True)
    secoes: dict = {}
    with ProcessPoolExecutor(max_workers=8) as ex:
        tot_fut = ex.submit(ler_totalizacao)
        for z, s in zip(zips, ex.map(ler_uf, map(str, zips))):
            secoes.update(s)
            print(f"  {z.name[8:10]}: {len(s):,} secoes", flush=True)
        tot = tot_fut.result()

    # ---- nivel 0: BU x totalizacao ---------------------------------------
    bu_reg = {k + (nr,): q for k, s in secoes.items() for nr, q in s["votos"].items()}
    if ufs:
        tot = Counter({k: v for k, v in tot.items() if k[0] in ufs})
    difs = [(k, bu_reg.get(k, 0), tot.get(k, 0)) for k in bu_reg.keys() | tot.keys()
            if bu_reg.get(k, 0) != tot.get(k, 0)]
    integ_uf: dict = defaultdict(lambda: {"secoes": 0, "registros": 0, "votos_bu": 0,
                                          "votos_tot": 0, "difs": 0})
    for k, q in bu_reg.items():
        u = integ_uf[k[0]]
        u["registros"] += 1
        u["votos_bu"] += q
    for k, q in tot.items():
        integ_uf[k[0]]["votos_tot"] += q
    for k in secoes:
        integ_uf[k[0]]["secoes"] += 1
    for k, _a, _b in difs:
        integ_uf[k[0]]["difs"] += 1
    print(f"nivel 0: {len(bu_reg):,} registros BU, {len(tot):,} totalizacao, "
          f"{len(difs)} diferencas", flush=True)

    # ---- indicadores por secao ------------------------------------------
    urnas = Counter(s["urna"] for s in secoes.values())
    # horario de referencia por municipio: o oeste do AM usa UTC-5 (fuso do Acre),
    # entao um fuso por UF erra. A MODA da hora de abertura nao erra; a mediana
    # arredondada errava onde varias secoes abriram atrasadas (MT, PR)
    ab_mun: dict = defaultdict(list)
    for k, s in secoes.items():
        m = minutos(s["abre"])
        if m is not None:
            ab_mun[k[:2]].append(m)
    ref_mun = {m: Counter(x // 60 for x in v).most_common(1)[0][0] * 60
               for m, v in ab_mun.items()}
    por_local: dict = defaultdict(list)
    for k, s in secoes.items():
        s["votos_pres"] = sum(s["votos"].values())
        s["turn"] = s["comp"] / s["aptos"] if s["aptos"] else None
        s["sA"], s["sB"] = share(s["votos"], A), share(s["votos"], B)
        s["biom_tx"] = s["biom"] / s["comp"] if s["comp"] > 0 and s["biom"] >= 0 else None
        ab, fe, em = minutos(s["abre"]), minutos(s["fecha"]), minutos(s["emite"])
        s["problemas"] = p = []
        ref = ref_mun.get(k[:2])
        if k[0] != "ZZ" and ab is not None and ref is not None and ab < ref - 10:
            p.append("abriu antes do horário")
        if k[0] != "ZZ" and fe is not None and ref is not None and fe < ref + 9 * 60:
            p.append("encerrou antes do horário")
        if k[0] != "ZZ" and ab is not None and ref is not None and ab > ref + 30:
            p.append("abertura atrasada (> 30 min)")
        if em is not None and fe is not None and em < fe:
            p.append("BU emitido antes do encerramento")
        if s["comp"] > s["aptos"]:
            p.append("comparecimento maior que aptos")
        if s["votos_pres"] != s["comp"] and s["tipo"] == "1":
            p.append("votos para presidente ≠ comparecimento")
        if s["tipo"] != "1":
            p.append({"2": "urna não apurada", "3": "anulada e apurada em separado",
                      "4": "urna anulada", "5": "urna não instalada"}.get(s["tipo"], "tipo " + s["tipo"]))
        if urnas[s["urna"]] > 1 and s["urna"] not in ("", "-1", "#NULO#"):
            # exterior com cedula: o sistema de apuracao aparece como uma so "urna"
            p.append("apurada por cédula (sem urna)" if not s["abre"] else
                     "mesmo número de urna em outra seção")
        por_local[k[:3] + (s["local"],)].append(k)

    # nivel 4: secao x outras secoes da mesma escola (deixa-uma-fora)
    for ks in por_local.values():
        for k in ks:
            s = secoes[k]
            viz = [secoes[j] for j in ks if j != k and secoes[j]["sA"] is not None]
            s["resA"] = s["resT"] = None
            if len(viz) >= 2 and s["sA"] is not None and s["comp"] >= 50:
                vv = sum(v["comp"] for v in viz)
                s["resA"] = s["sA"] - sum(v["sA"] * v["comp"] for v in viz) / vv
                if s["turn"] is not None and all(v["turn"] is not None for v in viz):
                    s["resT"] = s["turn"] - sum(v["turn"] * v["comp"] for v in viz) / vv
    # desvio tipico do residuo: robusto, nacional
    resA = [s["resA"] for s in secoes.values() if s["resA"] is not None]
    sdA = st.median(abs(r) for r in resA) * 1.4826
    resT = [s["resT"] for s in secoes.values() if s["resT"] is not None]
    sdT = st.median(abs(r) for r in resT) * 1.4826
    for s in secoes.values():
        s["zA"] = s["resA"] / sdA if s["resA"] is not None else None
        s["zT"] = s["resT"] / sdT if s["resT"] is not None else None

    salvar_secoes(secoes)

    # ---- 2022 por municipio (mesmo candidato: Lula) ----------------------
    m22, _ = historico.carregar(2022)
    m26, _ = historico.carregar(2026)

    # ---- agregacoes -------------------------------------------------------
    def agrega(ks):
        ss = [secoes[k] for k in ks]
        apt = sum(s["aptos"] for s in ss)
        comp = sum(s["comp"] for s in ss)
        vt = Counter()
        for s in ss:
            vt.update(s["votos"])
        val = sum(q for nr, q in vt.items() if nr not in ("95", "96"))
        bio = [s for s in ss if s["biom"] >= 0]
        return {
            "secoes": len(ss), "aptos": apt, "comp": comp,
            "turn": comp / apt if apt else 0,
            "votos": {A: vt.get(A, 0), B: vt.get(B, 0), "95": vt.get("95", 0),
                      "96": vt.get("96", 0)},
            "validos": val,
            "sA": vt.get(A, 0) / val if val else 0, "sB": vt.get(B, 0) / val if val else 0,
            "biom_tx": sum(s["biom"] for s in bio) / max(1, sum(s["comp"] for s in bio)),
            "problemas": Counter(p for s in ss for p in s["problemas"]),
            "alertas_escola": sum(1 for s in ss if s["zA"] is not None and abs(round(s["zA"], 2)) > Z_ALERTA),
        }

    por_uf, por_mun, por_zona = defaultdict(list), defaultdict(list), defaultdict(list)
    for k in secoes:
        por_uf[k[0]].append(k)
        por_mun[k[:2]].append(k)
        por_zona[k[:3]].append(k)

    # nivel 1: estados
    estados = {}
    for uf, ks in sorted(por_uf.items()):
        e = agrega(ks)
        ss = [secoes[k] for k in ks]
        e["integridade"] = integ_uf[uf]
        e["ultimo_digito"] = {nr: ultimo_digito([s["votos"].get(nr, 0) for s in ss])
                              for nr in (A, B)}
        e["ultimo_digito"]["aptos"] = ultimo_digito([s["aptos"] for s in ss])
        e["klimek"] = {nr: klimek(ss, "sA" if nr == A else "sB") for nr in (A, B)}
        e["extremos"] = {nr: sum(1 for s in ss if s["turn"] and s["turn"] >= .95 and
                                 (s["sA" if nr == A else "sB"] or 0) >= .9 and s["aptos"] >= 50)
                         for nr in (A, B)}
        mun22 = [m for m in m22 if m.startswith(uf)]
        v22 = sum(sum(m22[m].values()) for m in mun22)
        e["sA_2022"] = sum(m22[m].get("13", 0) for m in mun22) / v22 if v22 else None
        e["sB_2022"] = sum(m22[m].get("22", 0) for m in mun22) / v22 if v22 else None
        e["biom_vies"] = vies_biometria(ss)
        estados[uf] = e
    # swing estadual vs nacional
    sw = {uf: e["sA"] - e["sA_2022"] for uf, e in estados.items() if e["sA_2022"] is not None}
    zsw = dict(zip(sw, z_robusto(list(sw.values()))))
    for uf, e in estados.items():
        e["swing"] = sw.get(uf)
        e["z_swing"] = zsw.get(uf)

    # nivel 2: municipios (z dentro do proprio estado)
    municipios = {}
    for uf in estados:
        mks = [m for m in por_mun if m[0] == uf]
        linhas = []
        for m in mks:
            a = agrega(por_mun[m])
            chave = m[0] + m[1]
            v22 = m22.get(chave)
            tot22 = sum(v22.values()) if v22 else 0
            a["sA_2022"] = v22.get("13", 0) / tot22 if tot22 else None
            a["swing"] = a["sA"] - a["sA_2022"] if a["sA_2022"] is not None else None
            # crescimento de votos validos 2022 -> 2026 (eleitor fantasma infla isso)
            a["cresc"] = (a["validos"] / tot22 - 1) if tot22 else None
            a["nome"] = secoes[por_mun[m][0]]["mun_nome"]
            a["mun"] = m[1]
            linhas.append(a)
        for campo, zc in (("swing", "z_swing"), ("turn", "z_turn"),
                          ("biom_tx", "z_biom"), ("cresc", "z_cresc")):
            ok = [x for x in linhas if x[campo] is not None]
            for x, z in zip(ok, z_robusto([x[campo] for x in ok])):
                x[zc] = z
        # alerta = improvavel (z robusto) E grande (piso de efeito); com poucos
        # municipios o MAD fica minusculo e o z sozinho alarma por 2 pontos
        meds = {c: st.median([x[c] for x in linhas if x[c] is not None] or [0])
                for c, _ in PISO.values()}
        for x in linhas:
            x["alertas"] = [zc for zc, (c, piso) in PISO.items()
                            if abs(x.get(zc) or 0) > Z_ALERTA and x[c] is not None
                            and abs(x[c] - meds[c]) >= piso]
        municipios[uf] = linhas

    # nivel 3: zonas dos municipios com alerta + todas as zonas com alerta de escola
    zonas = {}
    for uf, linhas in municipios.items():
        for x in linhas:
            if not x["alertas"] and not x["alertas_escola"] and not sum(x["problemas"].values()):
                continue
            zs = []
            for zk in sorted(k for k in por_zona if k[:2] == (uf, x["mun"])):
                a = agrega(por_zona[zk])
                a["zona"] = zk[2]
                zs.append(a)
            zonas[f"{uf}-{x['mun']}"] = zs

    # nivel 4: secoes que destoam da escola ou tem problema de processo
    destaque = []
    for k, s in secoes.items():
        forte = s["zA"] is not None and abs(round(s["zA"], 2)) > Z_ALERTA
        if forte or s["problemas"]:
            destaque.append(ficha(k, s))
    destaque.sort(key=lambda d: -(abs(d["zA"] or 0) + 10 * len(d["problemas"])))

    # testes globais de vies (biometria e escola)
    out = {
        "gerado": "1º turno 2026 · Presidente",
        "candidatos": NOMES,
        "nacional": {"secoes": len(secoes), "registros_bu": len(bu_reg),
                     "registros_tot": len(tot), "diferencas": len(difs),
                     "difs_exemplo": [list(d[0]) + [d[1], d[2]] for d in difs[:50]],
                     "sd_residuo_escola": sdA, "sd_residuo_turn": sdT,
                     "problemas": Counter(p for s in secoes.values() for p in s["problemas"]),
                     "alertas_escola": sum(1 for s in secoes.values()
                                           if s["zA"] is not None and abs(round(s["zA"], 2)) > Z_ALERTA),
                     "secoes_testaveis_escola": len(resA),
                     "dist_residuo": histograma(resA, -0.3, 0.3, 60),
                     "biom_vies": vies_biometria(list(secoes.values()))},
        "estados": estados, "municipios": municipios, "zonas": zonas,
        "secoes": destaque[:3000], "secoes_total_destaque": len(destaque),
    }
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, default=float))
    print(f"-> {SAIDA.relative_to(RAIZ)} ({SAIDA.stat().st_size/1e6:.1f} MB)")
    resumo(out)


def klimek(ss, campo: str, n: int = 20) -> list[list[int]]:
    """Histograma 2D comparecimento x share (impressao digital de Klimek 2012).
    Enchimento de urna aparece como massa no canto (100%, 100%)."""
    h = [[0] * n for _ in range(n)]
    for s in ss:
        if s["turn"] is None or s[campo] is None or s["aptos"] < 50:
            continue
        i = min(n - 1, int(s["turn"] * n))
        j = min(n - 1, int(s[campo] * n))
        h[i][j] += 1
    return h


def vies_biometria(ss) -> dict:
    """Secoes com muita liberacao sem biometria votam diferente das vizinhas
    de escola? Mesario votando por ausentes deixaria o residuo deslocado."""
    alto = [s for s in ss if s["biom_tx"] is not None and s["biom_tx"] >= .2 and s["resA"] is not None]
    baixo = [s for s in ss if s["biom_tx"] is not None and s["biom_tx"] < .05 and s["resA"] is not None]
    if len(alto) < 30:
        return {"n_alto": len(alto), "media_alto": None, "media_baixo": None, "z": None}
    ma = st.fmean(s["resA"] for s in alto)
    mb = st.fmean(s["resA"] for s in baixo)
    se = math.sqrt(st.pvariance([s["resA"] for s in alto]) / len(alto) +
                   st.pvariance([s["resA"] for s in baixo]) / len(baixo))
    return {"n_alto": len(alto), "n_baixo": len(baixo), "media_alto": ma,
            "media_baixo": mb, "z": (ma - mb) / se if se else None}


def histograma(v, a, b, n):
    h = [0] * n
    for x in v:
        if a <= x < b:
            h[int((x - a) / (b - a) * n)] += 1
    return {"de": a, "ate": b, "h": h}


def ficha(k, s) -> dict:
    return {"uf": k[0], "mun": k[1], "mun_nome": s["mun_nome"], "zona": k[2],
            "secao": k[3], "local": s["local"], "aptos": s["aptos"], "comp": s["comp"],
            "turn": s["turn"], "votos": {A: s["votos"].get(A, 0), B: s["votos"].get(B, 0),
                                         "95": s["votos"].get("95", 0), "96": s["votos"].get("96", 0)},
            "sA": s["sA"], "zA": s["zA"], "zT": s["zT"], "biom": s["biom"],
            "urna": s["urna"], "carga": s["carga"], "dt_carga": s["dt_carga"],
            "abre": s["abre"], "fecha": s["fecha"], "emite": s["emite"],
            "recebe": s["recebe"], "tipo": s["tipo"], "agreg": s["agreg"],
            "problemas": s["problemas"]}


def salvar_secoes(secoes) -> None:
    DERIV.mkdir(parents=True, exist_ok=True)
    cols = ["uf", "mun", "zona", "secao", "local", "mun_nome", "aptos", "comp",
            "votos_13", "votos_22", "brancos", "nulos", "biom", "tipo", "urna",
            "carga", "dt_carga", "abre", "fecha", "emite", "recebe", "agreg",
            "res_escola_lula", "z_escola_lula", "problemas"]
    with gzip.open(DERIV / "secoes_pres_1t_2026.csv.gz", "wt", newline="",
                   encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(cols)
        for k, s in sorted(secoes.items()):
            v = s["votos"]
            w.writerow([*k, s["local"], s["mun_nome"], s["aptos"], s["comp"],
                        v.get(A, 0), v.get(B, 0), v.get("95", 0), v.get("96", 0),
                        s["biom"], s["tipo"], s["urna"], s["carga"], s["dt_carga"],
                        s["abre"], s["fecha"], s["emite"], s["recebe"], s["agreg"],
                        "" if s["resA"] is None else f"{s['resA']:.5f}",
                        "" if s["zA"] is None else f"{s['zA']:.2f}",
                        " | ".join(s["problemas"])])


def resumo(out) -> None:
    n = out["nacional"]
    print(f"\nNIVEL 0  BU x totalizacao: {n['diferencas']} diferencas em "
          f"{n['registros_bu']:,} registros ({n['secoes']:,} secoes)")
    print(f"         problemas de processo: {dict(n['problemas'])}")
    print(f"         secoes que destoam da escola (|z|>{Z_ALERTA}): {n['alertas_escola']} "
          f"de {n['secoes_testaveis_escola']:,}  (sd residuo={n['sd_residuo_escola']:.4f})")
    print(f"         vies biometria: {n['biom_vies']}")
    print("\nNIVEL 1  estados")
    for uf, e in out["estados"].items():
        ud = e["ultimo_digito"]
        print(f"  {uf} secoes={e['secoes']:>6,} turn={e['turn']:.3f} "
              f"Lula={e['sA']:.3f} (2022 {e['sA_2022'] or 0:.3f}, z={e['z_swing'] or 0:+.1f}) "
              f"biom={e['biom_tx']:.3f} ultdig p: L={fmtp(ud[A]['p'])} F={fmtp(ud[B]['p'])} "
              f"aptos={fmtp(ud['aptos']['p'])} extremos L/F={e['extremos'][A]}/{e['extremos'][B]} "
              f"escola={e['alertas_escola']} difs={e['integridade']['difs']} "
              f"prob={sum(e['problemas'].values())}")
    print("\nNIVEL 2  municipios com alerta")
    for uf, ls in out["municipios"].items():
        for x in ls:
            if x["alertas"]:
                print(f"  {uf} {x['nome']:<28} {x['alertas']} swing={x['swing']:+.3f} "
                      f"turn={x['turn']:.3f} biom={x['biom_tx']:.3f} cresc={x['cresc'] or 0:+.2f}")


def fmtp(p):
    return "  -  " if p is None else f"{p:.3f}"


if __name__ == "__main__":
    main()
