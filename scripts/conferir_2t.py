#!/usr/bin/env python3
"""Conferencias do 2o turno com o boletim de urna (BU) assinado de cada secao.

O TSE publica, para cada secao, o BU em ASN.1 (bu.dat) em
resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/. Este script decodifica
o BU (DER generico, sem dependencias) e responde tres perguntas:

1. integridade: em municipios inteiros sorteados (todas as secoes), a soma dos
   BUs bate com o total oficial do municipio no 2o turno?
2. escola: as 185 secoes que destoaram da propria escola no 1o turno continuam
   destoando no 2o? (composicao do eleitorado persiste; urna mexida no 1T nao)
3. viradas: nas 7 cidades que viraram desde 2022, todas as secoes andaram
   juntas tambem no 2o turno?

Ritmo: o mesmo throttle de logs_urna (8 req/s, pausa de 10 min em 429).
Uso:  python3 scripts/conferir_2t.py
Saida: resultados/conferir_2t.{txt,json}
"""

from __future__ import annotations

import csv
import gzip
import json
import random
import statistics as st
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from logs_urna import baixar  # noqa: E402

RAIZ = Path(__file__).parent.parent
PLEITO, ELEICAO = "3221", 6258
BASE = f"https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{PLEITO}/dados"
DEST = RAIZ / "dados/urnas/3221bu"
POR_UF = 150                       # secoes por UF na amostra de municipios inteiros


# ---------- DER minimo ----------
def _tlv(b: bytes, i: int):
    t = b[i]; i += 1
    tn = t & 0x1F
    if tn == 0x1F:
        tn = 0
        while True:
            x = b[i]; i += 1
            tn = tn << 7 | (x & 0x7F)
            if not x & 0x80:
                break
    n = b[i]; i += 1
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(b[i:i + k], "big"); i += k
    return t, tn, n, i


def _filhos(b: bytes):
    i, out = 0, []
    while i < len(b):
        t, tn, n, j = _tlv(b, i)
        out.append((t, tn, b[j:j + n]))
        i = j + n
    return out


def _int(v: bytes) -> int:
    return int.from_bytes(v, "big", signed=True)


def ler_bu(dado: bytes) -> dict:
    """Votos de Presidente (eleicao 6258): {13: n, 22: n, 'branco': n, 'nulo': n}."""
    env = _filhos(_filhos(dado)[0][2])
    bu = _filhos(next(v for t, tn, v in env if t == 0x04))[0][2]
    votos: dict = {}

    def busca(b: bytes):
        for t, tn, v in _filhos(b):
            if not t & 0x20:
                continue
            f = _filhos(v)
            # ResultadoVotacaoPorEleicao: idEleicao, qtdAptos, ..., [resultados]
            if len(f) >= 4 and f[0][0] == 0x02 and _int(f[0][2]) == ELEICAO:
                _coleta(next(x[2] for x in f if x[0] == 0x30))
                return True
            if busca(v):
                return True
        return False

    def _coleta(b: bytes):
        for t, tn, v in _filhos(b):
            if not t & 0x20:
                continue
            f = _filhos(v)
            tags = {(x[0], x[1]): x[2] for x in f}
            if (0x81, 1) in tags and (0x82, 2) in tags:          # VotoVotavel
                tipo, qtd = _int(tags[(0x81, 1)]), _int(tags[(0x82, 2)])
                if tipo == 1:
                    cod = _int(_filhos(tags[(0xA3, 3)])[1][2])
                    votos[cod] = votos.get(cod, 0) + qtd
                else:
                    k = {2: "branco", 3: "nulo"}.get(tipo, f"tipo{tipo}")
                    votos[k] = votos.get(k, 0) + qtd
            else:
                _coleta(v)

    busca(bu)
    return votos


# ---------- download ----------
def bu_da_secao(chave: str) -> tuple[str, dict | None]:
    uf, mun, zona, secao = chave.split("-")
    u, m, z, s = uf.lower(), mun.zfill(5), zona.zfill(4), secao.zfill(4)
    destino = DEST / uf / f"{m}-{z}-{s}-bu.dat"
    if not destino.exists():
        aux = baixar(f"{BASE}/{u}/{m}/{z}/{s}/p00{PLEITO}-{u}-m{m}-z{z}-s{s}-aux.json")
        if not aux:
            return chave, None
        hashes = json.loads(aux).get("hashes", [])
        ok = [h for h in hashes if h.get("st") == "Totalizado"] or hashes
        if not ok:
            return chave, None
        h = ok[-1]
        nome = next((a["nm"] for a in h["arq"] if a["tp"] == "bu"), None)
        dado = baixar(f"{BASE}/{u}/{m}/{z}/{s}/{h['hash']}/{nome}") if nome else None
        if not dado:
            return chave, None
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dado)
    try:
        return chave, ler_bu(destino.read_bytes())
    except Exception:
        return chave, None


def main() -> None:
    secoes = {}
    with gzip.open(RAIZ / "dados/derivados/secoes_pres_1t_2026.csv.gz", "rt", encoding="utf-8") as fh:
        for L in csv.DictReader(fh, delimiter=";"):
            if L["uf"] != "ZZ":
                secoes["-".join((L["uf"], L["mun"], L["zona"], L["secao"]))] = L
    tot2 = {}
    for r in csv.DictReader(open(RAIZ / "dados/totais_2t_municipio_6258.csv", encoding="utf-8")):
        tot2[f"{r['uf']}-{int(r['cd_municipio'])}"] = r
    dossie = RAIZ / "dados/derivados/dossie"
    escola = json.load(open(dossie / "escola_atipicas.json", encoding="utf-8"))
    viradas = json.load(open(dossie / "viradas_casos.json", encoding="utf-8"))

    por_mun = defaultdict(list)
    for k, L in secoes.items():
        por_mun[f"{L['uf']}-{int(L['mun'])}"].append(k)

    # 1. municipios inteiros sorteados, ate ~POR_UF secoes por UF
    rnd = random.Random(20261025)
    amostra_mun = []
    for uf in sorted({k[:2] for k in secoes}):
        muns = sorted(m for m in por_mun if m.startswith(uf + "-") and m in tot2)
        rnd.shuffle(muns)
        n = 0
        for m in muns:
            if n + len(por_mun[m]) > POR_UF and n:
                continue
            amostra_mun.append(m)
            n += len(por_mun[m])
            if n >= POR_UF * .8:
                break
    # 2. secoes que destoam + vizinhas do mesmo local de votacao
    alvo_escola = {}
    for e in escola:
        uf, mun, zona, sec = e["id"].split("-")
        k = f"{uf}-{mun}-{zona}-{sec}"
        if k not in secoes:
            continue
        loc = secoes[k]["local"]
        viz = [x for x in por_mun[f"{uf}-{mun}"] if secoes[x]["zona"] == zona and secoes[x]["local"] == loc]
        alvo_escola[k] = viz
    # 3. viradas: cidades inteiras
    mun_viradas = [v["id"] for v in viradas]

    chaves = set()
    for m in amostra_mun + mun_viradas:
        chaves.update(por_mun[m])
    for viz in alvo_escola.values():
        chaves.update(viz)
    chaves = sorted(chaves)
    print(f"{len(chaves)} secoes ({len(amostra_mun)} municipios sorteados, "
          f"{len(alvo_escola)} secoes de escola, {len(mun_viradas)} viradas)", flush=True)

    bus = {}
    with ThreadPoolExecutor(8) as ex:
        for i, (k, v) in enumerate(ex.map(bu_da_secao, chaves), 1):
            if v is not None:
                bus[k] = v
            if i % 500 == 0:
                print(f"  {i}/{len(chaves)}", flush=True)
    print(f"BUs lidos: {len(bus)}/{len(chaves)}", flush=True)

    out: dict = {"pleito": PLEITO, "bus_lidos": len(bus), "secoes_pedidas": len(chaves)}

    # --- 1. integridade
    linhas, dif_total = [], 0
    for m in amostra_mun + mun_viradas:
        ks = por_mun[m]
        falt = [k for k in ks if k not in bus]
        s = defaultdict(int)
        for k in ks:
            for c, v in (bus.get(k) or {}).items():
                s[c] += v
        t = tot2[m]
        dif = {"lula": s[13] - int(t["lula"]), "flavio": s[22] - int(t["flavio"]),
               "brancos": s["branco"] - int(t["brancos"]), "nulos": s["nulo"] - int(t["nulos"])}
        linhas.append({"id": m, "municipio": t["nm_municipio"], "secoes": len(ks), "sem_bu": len(falt),
                       "bu_lula": s[13], "bu_flavio": s[22], "tot_lula": int(t["lula"]),
                       "tot_flavio": int(t["flavio"]), "dif": dif})
        if not falt:
            dif_total += sum(abs(x) for x in dif.values())
    completos = [x for x in linhas if not x["sem_bu"]]
    out["integridade"] = {
        "municipios": len(linhas), "municipios_completos": len(completos),
        "secoes": sum(x["secoes"] for x in completos),
        "votos": sum(x["bu_lula"] + x["bu_flavio"] for x in completos),
        "diferencas": dif_total, "lista": linhas}

    # --- 2. escola: residuo da secao contra as vizinhas, 1T e 2T
    def share(v1, v2):
        return v1 / (v1 + v2) if v1 + v2 else None
    res = []
    for k, viz in alvo_escola.items():
        outros = [x for x in viz if x != k]
        if k not in bus or not outros:
            continue
        L = secoes[k]
        s1 = share(int(L["votos_13"]), int(L["votos_22"]))
        v1 = [share(int(secoes[x]["votos_13"]), int(secoes[x]["votos_22"])) for x in outros]
        b2 = [bus[x] for x in outros if x in bus]
        if not b2:
            continue
        s2 = share(bus[k].get(13, 0), bus[k].get(22, 0))
        v2 = [share(b.get(13, 0), b.get(22, 0)) for b in b2]
        v1 = [x for x in v1 if x is not None]
        v2 = [x for x in v2 if x is not None]
        if s1 is None or s2 is None or not v1 or not v2:
            continue
        e = next(x for x in escola if x["id"].startswith(k))
        res.append({"id": k, "a_favor": e["a_favor"], "nova": e["nova"], "vizinhas": len(outros),
                    "res_1t": round(s1 - st.median(v1), 4), "res_2t": round(s2 - st.median(v2), 4)})
    mesmo = [r for r in res if r["res_1t"] * r["res_2t"] > 0 and abs(r["res_2t"]) >= .05]
    out["escola"] = {
        "secoes": len(res), "mesmo_lado_2t": len(mesmo),
        "mediana_abs_1t": round(st.median(abs(r["res_1t"]) for r in res), 4) if res else None,
        "mediana_abs_2t": round(st.median(abs(r["res_2t"]) for r in res), 4) if res else None,
        "correlacao": round(st.correlation([r["res_1t"] for r in res], [r["res_2t"] for r in res]), 3) if len(res) > 2 else None,
        "lista": res}

    # --- 3. viradas: direcao de cada secao 1T->2T nao se aplica (candidatos mudam);
    #        mede a dispersao entre secoes da parcela do Lula no 2T, contra a cidade
    vir = []
    for m in mun_viradas:
        sh = [share(bus[k].get(13, 0), bus[k].get(22, 0)) for k in por_mun[m] if k in bus]
        sh = [x for x in sh if x is not None]
        t = tot2[m]
        cid = int(t["lula"]) / (int(t["lula"]) + int(t["flavio"]))
        vir.append({"id": m, "municipio": t["nm_municipio"], "secoes": len(sh), "lula_2t": round(cid, 4),
                    "mesmo_vencedor": sum(1 for x in sh if (x > .5) == (cid > .5)),
                    "desvio_padrao": round(st.pstdev(sh), 4) if sh else None})
    out["viradas_2t"] = vir

    (RAIZ / "resultados/conferir_2t.json").write_text(json.dumps(out, ensure_ascii=False))
    i = out["integridade"]
    txt = [f"CONFERENCIA DO 2o TURNO COM O BU ASSINADO (pleito {PLEITO})",
           f"BUs lidos: {len(bus)} de {len(chaves)} secoes pedidas", "",
           f"1. Integridade: {i['municipios_completos']} de {i['municipios']} municipios com todas as secoes; "
           f"{i['secoes']} secoes, {i['votos']} votos em Lula+Flavio; diferencas BU x total oficial: {i['diferencas']}"]
    for x in linhas:
        if x["sem_bu"] or any(x["dif"].values()):
            txt.append(f"   {x['id']} {x['municipio']}: sem_bu={x['sem_bu']} dif={x['dif']}")
    e = out["escola"]
    txt += ["", f"2. Escola: {e['secoes']} secoes medidas; continuam destoando do mesmo lado no 2T (>= 5 pts): "
            f"{e['mesmo_lado_2t']}; |residuo| mediano 1T {e['mediana_abs_1t']} -> 2T {e['mediana_abs_2t']}; "
            f"correlacao 1T x 2T {e['correlacao']}"]
    txt += ["", "3. Viradas no 2T:"] + [
        f"   {v['id']} {v['municipio']}: Lula {v['lula_2t']:.1%}, {v['mesmo_vencedor']}/{v['secoes']} secoes com o mesmo vencedor da cidade, dp {v['desvio_padrao']}"
        for v in vir]
    (RAIZ / "resultados/conferir_2t.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
