#!/usr/bin/env python3
"""Auditoria dos LOGS das urnas: a fonte primaria, eleitor por eleitor.

Para cada secao baixa do TSE o log da urna (log.jez, um zip com logd.dat) e
mede, so com o que a propria urna registrou:
  votos computados no log x comparecimento no BU (tem de bater)
  habilitacoes por digital x liberacoes manuais pelo mesario
  maior sequencia de liberacoes manuais seguidas (mesario votando por ausentes)
  votos com menos de 20 s desde o anterior (rapido demais para 6 cargos)
  fracao dos votos na ultima hora antes do encerramento

Grupos: secoes de cada pista do dossie x amostra aleatoria de controle.

Entradas: resultados/aprofundamento.json, dados/derivados/secoes_pres_1t_2026.csv.gz
Saida:    resultados/logs_urna.json ; logs em dados/urnas/<uf>/
Uso:      python3 scripts/logs_urna.py [tamanho_controle]
          python3 scripts/logs_urna.py nacional <urnas_por_uf> [pleito]
            amostra aleatoria estratificada por UF (3220 = 1o turno, 3221 = 2o)
            -> resultados/logs_nacional_<pleito>.json
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import random
import statistics as st
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
PLEITO = "3220"                                   # 1o turno 2026 (CD_PLEITO do BU)
BASE = f"https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{PLEITO}/dados"
DEST = RAIZ / "dados" / "urnas"


REQ_POR_S = 8.0            # o TSE ja bloqueou este IP com 429 a ~19 req/s
_trava, _prox = threading.Lock(), [0.0]


def _esperar_vez() -> None:
    with _trava:
        agora = time.monotonic()
        t = max(agora, _prox[0])
        _prox[0] = t + 1 / REQ_POR_S
    time.sleep(max(0.0, t - agora))


def baixar(url: str) -> bytes | None:
    for tentativa in range(4):
        _esperar_vez()
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url, headers={"User-Agent": "benford-eleicoes-2026"}), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:                      # bloqueio: pausa longa para todos
                with _trava:
                    _prox[0] = time.monotonic() + 600
                print("  429 do TSE: pausa de 10 min", flush=True)
            time.sleep(2 * (tentativa + 1))
        except Exception:                          # rede instavel: tenta de novo
            time.sleep(2 * (tentativa + 1))
    return None


def log_da_secao(chave: str, pleito: str = PLEITO) -> tuple[str, bytes | None, int]:
    uf, mun, zona, secao = chave.split("-")
    uf_l, m, z, s = uf.lower(), mun.zfill(5), zona.zfill(4), secao.zfill(4)
    base = f"https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{pleito}/dados"
    pasta = DEST / uf if pleito == PLEITO else DEST / pleito / uf
    destino = pasta / f"{m}-{z}-{s}-log.jez"
    if destino.exists():
        return chave, destino.read_bytes(), -1
    aux = baixar(f"{base}/{uf_l}/{m}/{z}/{s}/p00{pleito}-{uf_l}-m{m}-z{z}-s{s}-aux.json")
    if not aux:
        return chave, None, 0
    hashes = json.loads(aux).get("hashes", [])
    ok = [h for h in hashes if h.get("st") == "Totalizado"] or hashes
    if not ok:
        return chave, None, 0
    h = ok[-1]
    nome = next((a["nm"] for a in h["arq"] if a["tp"] == "log"), None)
    dado = baixar(f"{base}/{uf_l}/{m}/{z}/{s}/{h['hash']}/{nome}") if nome else None
    if dado:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dado)
    return chave, dado, len(hashes)


def linhas_log(dado: bytes) -> tuple[list[str], int]:
    """logd.dat e logs aninhados (.jez de outra urna/midia da mesma secao)."""
    z = zipfile.ZipFile(io.BytesIO(dado))
    out, partes = [], 0
    for nome in z.namelist():
        if nome.endswith(".dat"):
            out += z.read(nome).decode("latin-1").splitlines()
            partes += 1
        elif nome.endswith(".jez"):
            sub, n = linhas_log(z.read(nome))
            out += sub
            partes += n
    return out, partes


DIA_PLEITO = {"3220": "04/10/2026", "3221": "25/10/2026"}


def medir(dado: bytes, dia: str = DIA_PLEITO[PLEITO]) -> dict:
    """Um voto e 'manual' quando a urna pediu dado pessoal para habilitacao manual
    depois que o mesario digitou o identificador; 'bio' quando a digital bateu.
    O log do 2o turno acumula o 1o (mesma urna), por isso o filtro pelo dia."""
    linhas, partes = linhas_log(dado)
    linhas.sort(key=lambda L: (L[6:10], L[3:5], L[0:2], L[11:19]))  # cronologico entre logs
    votos: list[tuple[datetime, str]] = []
    tipo = None
    for L in linhas:
        p = L.split("\t")
        if len(p) < 5 or not p[0].startswith(dia):
            continue
        msg = p[4]
        if msg == "Identificador do eleitor digitado pelo mesário":
            tipo = None
        elif msg.startswith("Solicitação de dado pessoal do eleitor para habilitação manual"):
            tipo = "manual"
        elif msg.startswith("Tipo de habilitação do eleitor [biométrica]") and tipo is None:
            tipo = "bio"
        elif msg == "O voto do eleitor foi computado":
            votos.append((datetime.strptime(p[0], "%d/%m/%Y %H:%M:%S"), tipo or "outro"))
            tipo = None
    if not votos:
        return {"votos_log": 0, "partes_log": partes}
    t0, fim = votos[0][0], votos[-1][0]
    manual = [t for t, k in votos if k == "manual"]
    seq = maior = 0
    for _, k in votos:
        seq = seq + 1 if k == "manual" else 0
        maior = max(maior, seq)
    gaps = [(b[0] - a[0]).total_seconds() for a, b in zip(votos, votos[1:])]
    cedo = [k for t, k in votos if (t - t0).total_seconds() <= 7200]
    # encerramento oficial local = hora cheia da abertura + 9h (8h-17h de Brasilia)
    fecha = t0.replace(minute=0, second=0) + timedelta(hours=9)
    apos = [t for t, _ in votos if t > fecha]
    ult = [k for t, k in votos if (fim - t).total_seconds() <= 3600]
    return {
        "votos_log": len(votos), "partes_log": partes,
        "hab_bio": sum(1 for _, k in votos if k == "bio"), "hab_manual": len(manual),
        "maior_seq_manual": maior, "rapidos_20s": sum(1 for g in gaps if g < 20),
        "intervalo_mediano": st.median(gaps) if gaps else None,
        "ultima_hora": len(ult) / len(votos),
        # padrao no tempo: defeito falha desde cedo; fraude concentra as liberacoes
        "manual_primeiras_2h": cedo.count("manual") / len(cedo) if cedo else None,
        "manual_ultima_hora": ult.count("manual") / len(ult) if ult else None,
        "manual_na_ultima_hora": (sum(1 for t in manual if (fim - t).total_seconds() <= 3600) /
                                  len(manual)) if manual else None,
        "votos_apos_17h": len(apos),
        "minutos_apos_17h": round((fim - fecha).total_seconds() / 60) if fim > fecha else 0,
        "primeiro": t0.strftime("%H:%M:%S"), "ultimo": fim.strftime("%H:%M:%S")}


def padrao(x: dict) -> str | None:
    """So para urnas com >= 30% de liberacao manual."""
    if not x.get("votos_log") or x["hab_manual"] / x["votos_log"] < .3:
        return None
    if (x["manual_primeiras_2h"] or 0) >= .3 and (x["manual_na_ultima_hora"] or 0) <= .25:
        return "defeito desde cedo, espalhado no dia"
    if (x["manual_na_ultima_hora"] or 0) > .5:
        return "concentrado na última hora"
    return "intermediário"


def main(n_controle: int = 600) -> None:
    ap = json.loads((RAIZ / "resultados" / "aprofundamento.json").read_text())
    secoes = {}
    with gzip.open(RAIZ / "dados/derivados/secoes_pres_1t_2026.csv.gz", "rt", encoding="utf-8") as fh:
        for L in csv.DictReader(fh, delimiter=";"):
            secoes["-".join((L["uf"], L["mun"], L["zona"], L["secao"]))] = L
    grupos = {
        "escola_novas": [s["id"] for s in ap["escola"]["lista"] if s["res22"] is None],
        "escola_antigas": [s["id"] for s in ap["escola"]["lista"] if s["res22"] is not None],
        "klimek": [s["id"] for s in ap["klimek_canto"]["lista"]],
        "biometria_alta": sorted((k for k, L in secoes.items() if int(L["comp"]) >= 50 and
                                  int(L["biom"]) / int(L["comp"]) >= .3),
                                 key=lambda k: -int(secoes[k]["biom"]))[:150],
    }
    rnd = random.Random(2026)                         # amostra reproduzivel
    pool = [k for k in secoes if not k.startswith("ZZ") and int(secoes[k]["comp"]) >= 50]
    grupos["controle"] = rnd.sample(pool, n_controle)
    todas = sorted({k for g in grupos.values() for k in g if not k.startswith("ZZ")})
    print(f"baixando logs de {len(todas)} secoes...", flush=True)
    med = {}
    with ThreadPoolExecutor(12) as ex:
        for i, (k, dado, nh) in enumerate(ex.map(log_da_secao, todas), 1):
            if dado:
                try:
                    med[k] = medir(dado) | {"bu_comp": int(secoes[k]["comp"]), "envios": nh}
                    med[k]["padrao"] = padrao(med[k])
                except (zipfile.BadZipFile, KeyError, IndexError):
                    med[k] = {"erro": "log ilegivel"}
            if i % 100 == 0:
                print(f"  {i}/{len(todas)}", flush=True)
    resumo = {}
    for nome, ks in grupos.items():
        m = [med[k] for k in ks if k in med and med[k].get("votos_log")]
        if not m:
            continue
        tot = sum(x["votos_log"] for x in m)
        resumo[nome] = {
            "secoes": len(ks), "com_log": len(m),
            "log_bate_bu": sum(1 for x in m if x["votos_log"] == x["bu_comp"]),
            "manual_pct": sum(x["hab_manual"] for x in m) / tot if tot else None,
            "padroes": dict(Counter(padrao(x) for x in m if padrao(x))),
            "logs_multiplos": sum(1 for x in m if x["partes_log"] > 1),
            "secoes_seq_manual_10+": sum(1 for x in m if x["maior_seq_manual"] >= 10),
            "maior_seq_manual": max(x["maior_seq_manual"] for x in m),
            "rapidos_20s_pct": sum(x["rapidos_20s"] for x in m) / tot if tot else None,
            "ultima_hora_mediana": st.median(x["ultima_hora"] for x in m if x["ultima_hora"] is not None),
            "intervalo_mediano": st.median(x["intervalo_mediano"] for x in m if x["intervalo_mediano"]),
        }
    out = {"grupos": resumo, "secoes": med, "membros": grupos}
    (RAIZ / "resultados/logs_urna.json").write_text(json.dumps(out, ensure_ascii=False))
    for nome, r in resumo.items():
        print(f"{nome:<15} logs={r['com_log']}/{r['secoes']} bate_BU={r['log_bate_bu']} "
              f"manual={r['manual_pct']:.1%} multi={r['logs_multiplos']} padroes={r['padroes']} "
              f"seq10+={r['secoes_seq_manual_10+']} "
              f"maxseq={r['maior_seq_manual']} rapidos<20s={r['rapidos_20s_pct']:.2%} "
              f"ultima_hora={r['ultima_hora_mediana']:.1%} intervalo={r['intervalo_mediano']:.0f}s")


def nacional(por_uf: int, pleito: str) -> None:
    """Amostra aleatoria estratificada: `por_uf` secoes de cada UF (mesma
    semente nos dois turnos, entao as mesmas secoes)."""
    secoes = {}
    with gzip.open(RAIZ / "dados/derivados/secoes_pres_1t_2026.csv.gz", "rt", encoding="utf-8") as fh:
        for L in csv.DictReader(fh, delimiter=";"):
            if L["uf"] != "ZZ" and int(L["comp"]) >= 50:
                secoes["-".join((L["uf"], L["mun"], L["zona"], L["secao"]))] = L
    rnd = random.Random(20261004)
    por = {}
    for k in sorted(secoes):
        por.setdefault(k[:2], []).append(k)
    amostra = [k for uf in sorted(por) for k in rnd.sample(por[uf], min(por_uf, len(por[uf])))]
    print(f"pleito {pleito}: {len(amostra)} urnas em {len(por)} UFs, {REQ_POR_S:.0f} req/s", flush=True)
    med = {}
    with ThreadPoolExecutor(8) as ex:
        for i, (k, dado, nh) in enumerate(ex.map(lambda k: log_da_secao(k, pleito), amostra), 1):
            if dado:
                try:
                    med[k] = medir(dado, DIA_PLEITO[pleito]) | {"envios": nh, "bu_comp_1t": int(secoes[k]["comp"])}
                    med[k]["padrao"] = padrao(med[k])
                except (zipfile.BadZipFile, KeyError, IndexError, ValueError):
                    med[k] = {"erro": "log ilegivel"}
            if i % 500 == 0:
                print(f"  {i}/{len(amostra)}", flush=True)
    por_uf_res = {}
    for uf in sorted(por):
        m = [med[k] for k in med if k.startswith(uf + "-") and med[k].get("votos_log")]
        tot = sum(x["votos_log"] for x in m) or 1
        por_uf_res[uf] = {
            "urnas": len(m), "votos": tot,
            "manual_pct": sum(x["hab_manual"] for x in m) / tot,
            "seq10": sum(1 for x in m if x["maior_seq_manual"] >= 10),
            "concentrado_fim": sum(1 for x in m if x["padrao"] == "concentrado na última hora"),
            "defeito": sum(1 for x in m if x["padrao"] == "defeito desde cedo, espalhado no dia"),
            "rapidos_20s": sum(x["rapidos_20s"] for x in m),
            "votos_apos_17h_pct": sum(x["votos_apos_17h"] for x in m) / tot,
            "urnas_ate_19h": sum(1 for x in m if x["minutos_apos_17h"] >= 90),
            "urnas_fecharam_17h": sum(1 for x in m if x["minutos_apos_17h"] <= 15),
        }
    out = {"pleito": pleito, "por_uf": por_uf_res, "urnas": med}
    (RAIZ / f"resultados/logs_nacional_{pleito}.json").write_text(json.dumps(out, ensure_ascii=False))
    for uf, r in por_uf_res.items():
        print(f"{uf} urnas={r['urnas']:>4} manual={r['manual_pct']:.1%} seq10+={r['seq10']:>3} "
              f"fim={r['concentrado_fim']} defeito={r['defeito']:>3} rapidos={r['rapidos_20s']} "
              f"apos17h={r['votos_apos_17h_pct']:.1%} ate19h={r['urnas_ate_19h']} fechou17h={r['urnas_fecharam_17h']}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["nacional"]:
        nacional(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else PLEITO)
    else:
        main(*(int(a) for a in sys.argv[1:2]))
