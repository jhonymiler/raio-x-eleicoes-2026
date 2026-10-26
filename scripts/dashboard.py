#!/usr/bin/env python3
"""Servidor do dashboard de acompanhamento em tempo real.

A API do TSE responde 403 a requisicoes com cabecalho Origin, entao uma
pagina no navegador nao consegue chama-la direto. Este servidor faz o
proxy e serve a pagina.

Rotas:
    /                 dashboard.html
    /api/status       resumo nacional (proxy direto, cache de 10s)
    /api/benford      estatisticas de Benford dos totais municipais,
                      recalculadas em background a cada SWEEP_S segundos
    /api/historico    resultados/historico.json (gerado por historico.py)

Uso:  python3 scripts/dashboard.py [porta]     (padrao 8765)
"""

from __future__ import annotations

import json
import math
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import benford as bf  # noqa: E402
from coletar_2t import (Bloqueado, em_cooldown, municipios,  # noqa: E402
                         pegar, resultado_municipio)
from historico import veredito  # noqa: E402

CD = "6258"
BASE = "https://resultados.tse.jus.br/oficial/ele2026"
RAIZ = Path(__file__).parent.parent
PAGINA = Path(__file__).parent / "dashboard.html"
HISTORICO = RAIZ / "resultados" / "historico.json"
# A varredura custa 5.757 requisicoes; o resumo nacional custa 1. Por isso
# o resumo e continuo e a varredura e SOB DEMANDA (botao) ou em intervalo
# longo via --auto. Varrer de 5 em 5 min com 24 conexoes nos rendeu um
# HTTP 429 do TSE -- nao repetir.
AUTO_SWEEP_S = 0       # 0 = so sob demanda; --auto N define N minutos
STATUS_TTL = 30        # cache do resumo nacional

_estado: dict = {"benford": None, "status": None, "status_em": 0.0,
                 "historico": [], "varrendo": False, "erro": None}
_trava = threading.Lock()


# --------------------------------------------------------------------------
# coleta
# --------------------------------------------------------------------------

def status_nacional() -> dict | None:
    with _trava:
        if _estado["status"] and time.time() - _estado["status_em"] < STATUS_TTL:
            return _estado["status"]
    try:
        d = pegar(f"{BASE}/{CD}/dados/br/br-c0001-e00{CD}-u.json")
    except Bloqueado:
        with _trava:
            _estado["erro"] = "TSE bloqueou por excesso de requisicoes (429)"
        return _estado.get("status")
    if not d:
        return None
    s = d.get("s", {})
    carg = (d.get("carg") or [{}])[0]
    cands = []
    for agr in carg.get("agr", []):
        for par in agr.get("par", []):
            for c in par.get("cand", []):
                cands.append({
                    "numero": c.get("n"), "nome": c.get("nmu"),
                    "votos": int(c.get("vap") or 0),
                    "pct": float((c.get("pvapn") or "0").replace(",", ".")),
                })
    cands.sort(key=lambda c: -c["votos"])
    out = {
        "hora_tse": f"{d.get('dg')} {d.get('hg')}",
        "encerrada": d.get("tf") == "s",
        "secoes_totalizadas": int(s.get("st") or 0),
        "secoes_esperadas": int(s.get("ts") or 0),
        "pct": float((s.get("pstn") or "0").replace(",", ".")),
        "candidatos": cands,
    }
    with _trava:
        _estado["status"] = out
        _estado["status_em"] = time.time()
    return out


def varrer() -> None:
    """Baixa todos os municipios e recalcula as estatisticas de Benford."""
    from concurrent.futures import ThreadPoolExecutor

    muns = municipios(CD)
    tarefas = [(CD, uf, mun, nome) for uf, mun, nome in muns]
    por_mun: dict[str, dict[str, int]] = {}
    nomes: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for linhas in ex.map(resultado_municipio, tarefas):
            if not linhas or linhas[0]["uf"].upper() == "ZZ":   # exterior nao e municipio
                continue
            chave = f"{linhas[0]['uf']}-{linhas[0]['cd_municipio']}"
            d = por_mun.setdefault(chave, {})
            for L in linhas:
                if L["qt_votos"] > 0:
                    d[L["nr_votavel"]] = L["qt_votos"]
                    nomes.setdefault(L["nr_votavel"], L["nm_votavel"])

    chaves = [m for m in por_mun if sum(por_mun[m].values()) > 0]
    tot = {m: sum(por_mun[m].values()) for m in chaves}
    base_phi = bf.fourier_empirico([tot[m] for m in chaves])["phi"][1]

    esperado = bf.p_primeiro_digito()
    saida = {
        "em": datetime.now().isoformat(timespec="seconds"),
        "municipios": len(chaves),
        "base_phi": base_phi,
        "esperado": {str(d): esperado[d] for d in esperado},
        "candidatos": [],
    }
    for nr in sorted(nomes, key=lambda k: -sum(
            por_mun[m].get(k, 0) for m in chaves)):
        serie = [por_mun[m][nr] for m in chaves if por_mun[m].get(nr, 0) > 0]
        if len(serie) < 500:
            continue
        share = [por_mun[m][nr] / tot[m] for m in chaves
                 if por_mun[m].get(nr, 0) > 0]
        r = bf.avaliar("1d", serie, bf.primeiro_digito, esperado)
        f = bf.fourier_empirico(serie)
        ps = bf.fourier_empirico(share)["phi"][1]
        esp = base_phi * ps
        saida["candidatos"].append({
            "numero": nr, "nome": nomes[nr], "n": r.n,
            "observado": {str(d): r.observado.get(d, 0) / r.n
                          for d in range(1, 10)},
            "chi2": r.chi2, "p": r.p_chi2, "mad": r.mad,
            "phi": f["phi"][1], "excesso": f["excesso_k1"],
            "phi_share": ps, "razao": (f["phi"][1] / esp) if esp else 0.0,
            "veredito": veredito(r.n, f["excesso_k1"], r.p_chi2, r.mad),
        })

    with _trava:
        _estado["benford"] = saida
        _estado["erro"] = None
        st = _estado.get("status") or {}
        _estado["historico"].append({
            "em": saida["em"], "pct": st.get("pct", 0),
            "razoes": {c["numero"]: round(c["razao"], 3)
                       for c in saida["candidatos"]},
        })
        _estado["historico"] = _estado["historico"][-60:]


def rodar_varredura() -> None:
    """Uma varredura. Nao lanca -- registra o erro no estado."""
    with _trava:
        if _estado["varrendo"]:
            return
        _estado["varrendo"] = True
    try:
        varrer()
    except Bloqueado as e:
        with _trava:
            _estado["erro"] = f"TSE bloqueou (429): {e}. Varredura suspensa."
    except Exception as e:
        with _trava:
            _estado["erro"] = f"{type(e).__name__}: {e}"
    finally:
        with _trava:
            _estado["varrendo"] = False


def laco_varredura() -> None:
    while True:
        time.sleep(AUTO_SWEEP_S)
        if em_cooldown():
            continue
        rodar_varredura()


# --------------------------------------------------------------------------
# http
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def _responder(self, corpo: bytes, tipo: str, codigo: int = 200) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, obj, codigo: int = 200) -> None:
        self._responder(json.dumps(obj, ensure_ascii=False).encode(),
                        "application/json; charset=utf-8", codigo)

    def do_GET(self) -> None:                        # noqa: N802
        rota = self.path.split("?")[0]
        if rota in ("/", "/index.html"):
            if not PAGINA.exists():
                self._responder(b"dashboard.html nao encontrado", "text/plain", 404)
                return
            self._responder(PAGINA.read_bytes(), "text/html; charset=utf-8")
        elif rota == "/api/status":
            s = status_nacional()
            if s is None:
                self._json({"erro": "TSE indisponivel"}, 502)
            else:
                self._json(s)
        elif rota == "/api/benford":
            with _trava:
                self._json({"dados": _estado["benford"],
                            "historico": _estado["historico"],
                            "varrendo": _estado["varrendo"],
                            "erro": _estado["erro"],
                            "cooldown_s": round(em_cooldown()),
                            "auto_s": AUTO_SWEEP_S})
        elif rota == "/api/historico":
            if not HISTORICO.exists():
                self._json({"erro": "rode scripts/historico.py"}, 404)
            else:
                self._responder(HISTORICO.read_bytes(),
                                "application/json; charset=utf-8")
        elif rota == "/api/varrer":
            if em_cooldown():
                self._json({"ok": False,
                            "motivo": f"cooldown de {em_cooldown():.0f}s"}, 429)
                return
            with _trava:
                ja = _estado["varrendo"]
            if ja:
                self._json({"ok": False, "motivo": "ja varrendo"})
                return
            threading.Thread(target=rodar_varredura, daemon=True).start()
            self._json({"ok": True, "motivo": "varredura iniciada"})
        else:
            self._responder(b"nao encontrado", "text/plain", 404)

    def log_message(self, *_args) -> None:           # silencia o access log
        pass


def main(porta: int = 8765) -> None:
    if AUTO_SWEEP_S:
        threading.Thread(target=laco_varredura, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    modo = (f"varredura automatica a cada {AUTO_SWEEP_S//60} min"
            if AUTO_SWEEP_S else "varredura sob demanda (botao na pagina)")
    print(f"dashboard em http://127.0.0.1:{porta}  ({modo})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--auto" in args:
        i = args.index("--auto")
        minutos = max(20, int(args[i + 1]))     # nunca abaixo de 20 min
        AUTO_SWEEP_S = minutos * 60
        del args[i:i + 2]
    main(int(args[0]) if args else 8765)
