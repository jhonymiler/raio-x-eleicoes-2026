#!/usr/bin/env python3
"""Coleta os resultados do 2o turno pela API de divulgacao do TSE.

O portal de dados abertos so publica o CSV consolidado do 2o turno dias
depois do pleito. Ate la, a unica fonte por municipio e a API que alimenta
resultados.tse.jus.br:

    /oficial/ele2026/<cd_eleicao>/config/mun-e00<cd>-cm.json   lista de municipios
    /oficial/ele2026/<cd_eleicao>/dados/<uf>/<uf><mun>-c0001-e00<cd>-u.json

Grava um CSV com uma linha por (municipio, votavel) e um JSON de metadados
com o percentual apurado no instante da coleta.

Uso:  python3 coletar_2t.py [cd_eleicao]   (padrao 6258 = Presidente 2T)
"""

from __future__ import annotations

import csv
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
DESTINO = Path(__file__).parent.parent / "dados"
TIMEOUT = 25
WORKERS = 6


# --------------------------------------------------------------------------
# throttle global -- o TSE devolve 429 e bloqueia o IP se abusarmos
# --------------------------------------------------------------------------
# Aprendido do jeito ruim: 24 conexoes varrendo 5.757 municipios a cada 5 min
# (~19 req/s sustentados) levou a HTTP 429 em ~40 min, derrubando tambem os
# endpoints estaticos. Mantenha o teto baixo.
REQ_POR_S = 4.0
_ultima_req = [0.0]
_trava_req = threading.Lock()
_bloqueado_ate = [0.0]
ESPERA_429 = 600          # 10 min de descanso ao tomar 429


class Bloqueado(Exception):
    """O TSE devolveu 429. Parar de pedir ate o cooldown passar."""


def _throttle() -> None:
    with _trava_req:
        agora = time.monotonic()
        espera = _ultima_req[0] + 1.0 / REQ_POR_S - agora
        if espera > 0:
            time.sleep(espera)
            agora += espera
        _ultima_req[0] = agora


def em_cooldown() -> float:
    """Segundos restantes de bloqueio, 0 se livre."""
    return max(0.0, _bloqueado_ate[0] - time.monotonic())


def pegar(url: str, tentativas: int = 3):
    if em_cooldown():
        raise Bloqueado(f"cooldown por {em_cooldown():.0f}s")
    for i in range(tentativas):
        _throttle()
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "benford-audit/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _bloqueado_ate[0] = time.monotonic() + ESPERA_429
                raise Bloqueado("HTTP 429 do TSE") from None
            if i == tentativas - 1:
                return None
        except Exception:
            if i == tentativas - 1:
                return None
            time.sleep(1.5 * (i + 1))
    return None


def municipios(cd: str) -> list[tuple[str, str, str]]:
    cfg = pegar(f"{BASE}/{cd}/config/mun-e00{cd}-cm.json")
    if not cfg:
        raise SystemExit("nao consegui baixar a lista de municipios")
    out = []
    for uf in cfg["abr"]:
        for m in uf["mu"]:
            out.append((uf["cd"], m["cd"], m["nm"]))
    return out


def resultado_municipio(args):
    cd, uf, mun, nome = args
    try:
        d = pegar(f"{BASE}/{cd}/dados/{uf}/{uf}{mun}-c0001-e00{cd}-u.json")
    except Bloqueado:
        return None
    if not d:
        return None
    linhas = []
    carg = (d.get("carg") or [{}])[0]
    for agr in carg.get("agr", []):
        for par in agr.get("par", []):
            for cand in par.get("cand", []):
                linhas.append({
                    "uf": uf.upper(), "cd_municipio": mun, "nm_municipio": nome,
                    "nr_votavel": cand.get("n"), "nm_votavel": cand.get("nmu"),
                    "qt_votos": int(cand.get("vap") or 0),
                    "situacao": cand.get("st", ""),
                })
    # brancos e nulos ficam fora de 'agr'
    for chave, rotulo, numero in (("vb", "VOTO BRANCO", "95"),
                                  ("tvn", "VOTO NULO", "96")):
        if chave in d:
            linhas.append({
                "uf": uf.upper(), "cd_municipio": mun, "nm_municipio": nome,
                "nr_votavel": numero, "nm_votavel": rotulo,
                "qt_votos": int(d.get(chave) or 0), "situacao": "",
            })
    return linhas


def main(cd: str = "6258") -> None:
    resumo = pegar(f"{BASE}/{cd}/dados/br/br-c0001-e00{cd}-u.json")
    if not resumo:
        raise SystemExit("eleicao sem dados publicados")
    s = resumo.get("s", {})
    meta = {
        "cd_eleicao": cd,
        "turno": resumo.get("t"),
        "coletado_em": datetime.now().isoformat(timespec="seconds"),
        "gerado_tse": f"{resumo.get('dg')} {resumo.get('hg')}",
        "secoes_totalizadas": s.get("st"),
        "secoes_esperadas": s.get("ts"),
        "pct_totalizado": s.get("pst"),
        "totalizacao_encerrada": resumo.get("tf") == "s",
    }
    print(f"eleicao {cd} turno {meta['turno']} | "
          f"{meta['pct_totalizado']}% das secoes | "
          f"encerrada={meta['totalizacao_encerrada']}")

    muns = municipios(cd)
    print(f"baixando {len(muns):,} municipios com {WORKERS} conexoes...")
    tarefas = [(cd, uf, mun, nome) for uf, mun, nome in muns]

    todas: list[dict] = []
    falhas = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, r in enumerate(ex.map(resultado_municipio, tarefas), 1):
            if r is None:
                falhas += 1
            else:
                todas.extend(r)
            if i % 500 == 0:
                print(f"  {i:,}/{len(tarefas):,}  (falhas: {falhas})")

    meta["municipios_baixados"] = len(muns) - falhas
    meta["municipios_com_falha"] = falhas

    DESTINO.mkdir(parents=True, exist_ok=True)
    csv_path = DESTINO / f"resultado_2t_municipio_{cd}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(todas[0].keys()))
        wr.writeheader()
        wr.writerows(todas)
    (DESTINO / f"resultado_2t_meta_{cd}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{len(todas):,} linhas -> {csv_path}")
    print(f"falhas: {falhas}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "6258")
