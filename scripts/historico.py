#!/usr/bin/env python3
"""Serie historica 1994-2026: a mesma bateria de testes em toda eleicao
presidencial, do papel (1994) a urna eletronica (parcial em 1998, total
a partir de 2002).

Nivel: total do candidato por municipio (exterior excluido). Testes:
1o digito (chi2, MAD), 2o digito (2BL), dois ultimos digitos (uniforme),
gate de Fourier e a decomposicao porte x share de decomposicao.py.

Entradas:
  dados/historico/munzona_<ano>.zip   votacao_candidato_munzona do TSE
  dados/votacao_secao_<ano>_BR.csv    2022 e 2026 (ja usados em analisar.py)
Saida:
  resultados/historico.json           lido pelo dashboard (/api/historico)

Uso:  python3 scripts/historico.py
"""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import benford as bf  # noqa: E402

RAIZ = Path(__file__).parent.parent
DADOS = RAIZ / "dados"
SAIDA = RAIZ / "resultados" / "historico.json"

# ano -> como a urna funcionava
MEIO = {1994: "papel", 1998: "misto", 2002: "urna", 2006: "urna",
        2010: "urna", 2014: "urna", 2018: "urna", 2022: "urna", 2026: "urna"}


def _linhas(ano: int):
    """Linhas (dict) do arquivo de presidente de cada ano."""
    zp = DADOS / "historico" / f"munzona_{ano}.zip"
    if zp.exists():
        z = zipfile.ZipFile(zp)
        nomes = z.namelist()
        alvo = next((n for n in nomes if n.endswith("_BR.csv")), None) or \
            next(n for n in nomes if n.endswith("_BRASIL.csv"))
        fh = io.TextIOWrapper(z.open(alvo), encoding="latin-1", newline="")
    else:
        fh = open(DADOS / f"votacao_secao_{ano}_BR.csv",
                  encoding="latin-1", newline="")
    with fh:
        yield from csv.DictReader(fh, delimiter=";", quotechar='"')


def carregar(ano: int, turno: str = "1"):
    mun: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    nomes: dict[str, str] = {}
    for L in _linhas(ano):
        if L["CD_CARGO"] != "1" or L["NR_TURNO"] != turno or L["SG_UF"] == "ZZ":
            continue
        nr = L.get("NR_CANDIDATO") or L["NR_VOTAVEL"]
        if int(nr) >= 95:                             # branco/nulo no CSV por secao
            continue
        # 1998 zera QT_VOTOS_NOMINAIS e grava tudo em _VALIDOS
        v = max(int(L.get("QT_VOTOS_NOMINAIS") or L["QT_VOTOS"]),
                int(L.get("QT_VOTOS_NOMINAIS_VALIDOS") or 0))
        mun[L["SG_UF"] + L["CD_MUNICIPIO"]][nr] += v
        nomes.setdefault(nr, L.get("NM_URNA_CANDIDATO") or L["NM_VOTAVEL"])
    return mun, nomes


# veredito para leigos -- um lar so, o painel apenas exibe
N_MIN = 110      # abaixo disso o digito 9 espera < 5 ocorrencias: chi2 invalido
EXC_MAX = 3.0    # gate de Fourier: acima disso a forma do dado nao e Benford
MAD_MAT = 0.012  # Nigrini: acima de "aceitavel" -- com n grande, p sozinho alarma a toa


def veredito(n: int, excesso: float, p: float, mad: float) -> str:
    if n < N_MIN:
        return "poucos"
    if excesso > EXC_MAX:
        return "nao_se_aplica"
    return "desvio" if p < 0.01 and mad >= MAD_MAT else "segue"


def bateria(serie) -> dict:
    p1 = bf.p_primeiro_digito()
    r1 = bf.avaliar("1d", serie, bf.primeiro_digito, p1)
    r2 = bf.avaliar("2d", serie, bf.segundo_digito, bf.p_segundo_digito())
    ru = bf.uniformidade_dois_ultimos(serie)
    f = bf.fourier_empirico(serie)
    return {
        "n": r1.n,
        "observado": {str(d): r1.observado.get(d, 0) / r1.n for d in range(1, 10)},
        "chi2": r1.chi2, "p": r1.p_chi2, "mad": r1.mad,
        "nigrini": bf.classificar_mad(r1.mad, "primeiro digito"),
        "mad_2d": r2.mad, "p_2d": r2.p_chi2,
        "p_ultimos": ru.p_chi2, "n_ultimos": ru.n,
        "phi": f["phi"].get(1, 0.0), "excesso": f["excesso_k1"],  # DF: n=1
        "veredito": veredito(r1.n, f["excesso_k1"], r1.p_chi2, r1.mad),
    }


def analisar(ano: int) -> dict:
    mun, nomes = carregar(ano)
    muns = [m for m in mun if sum(mun[m].values()) > 0]
    tot = {m: sum(mun[m].values()) for m in muns}
    base = bateria(list(tot.values()))
    out = {"ano": ano, "meio": MEIO[ano], "municipios": len(muns),
           "base": base, "candidatos": []}
    total_br = sum(tot.values())
    for nr in sorted(nomes, key=lambda c: -sum(mun[m].get(c, 0) for m in muns)):
        serie = [mun[m][nr] for m in muns if mun[m].get(nr, 0) > 0]
        if len(serie) < 1000:
            continue
        ps = bf.fourier_empirico([mun[m][nr] / tot[m] for m in muns
                                  if mun[m].get(nr, 0) > 0])["phi"][1]
        c = bateria(serie)
        esp = base["phi"] * ps
        c.update(numero=nr, nome=nomes[nr], share=sum(serie) / total_br,
                 phi_share=ps, razao=c["phi"] / esp if esp else 0.0)
        out["candidatos"].append(c)

    # 1o e 2o colocados, estado por estado (chave do municipio = UF + codigo)
    out["estados"] = {}
    for c in out["candidatos"][:2]:
        por_uf: dict[str, list[int]] = defaultdict(list)
        for m in muns:
            if mun[m].get(c["numero"], 0) > 0:
                por_uf[m[:2]].append(mun[m][c["numero"]])
        out["estados"][c["numero"]] = {
            uf: {k: b[k] for k in ("n", "observado", "p", "mad", "excesso", "veredito")}
            for uf, b in ((uf, bateria(v)) for uf, v in sorted(por_uf.items()))}
    return out


def main() -> None:
    anos = [a for a in MEIO if (DADOS / "historico" / f"munzona_{a}.zip").exists()
            or (DADOS / f"votacao_secao_{a}_BR.csv").exists()]
    res = []
    for a in anos:
        r = analisar(a)
        res.append(r)
        print(f"{a} {r['meio']:<18} {r['municipios']:>5} mun  base MAD="
              f"{r['base']['mad']:.4f} exc={r['base']['excesso']:.1f}", flush=True)
        for c in r["candidatos"]:
            print(f"    {c['nome'][:22]:<22} share={c['share']:5.1%} n={c['n']:>5} "
                  f"MAD={c['mad']:.4f} {c['nigrini']:<20} p={c['p']:.1e} "
                  f"exc={c['excesso']:5.1f} razao={c['razao']:.2f} {c['veredito']}",
                  flush=True)
        for nr, ufs in r["estados"].items():
            cont = defaultdict(list)
            for uf, b in ufs.items():
                cont[b["veredito"]].append(uf)
            print(f"    estados {nr}: " + "  ".join(
                f"{k}={len(v)}" + (f" {v}" if k == "desvio" else "")
                for k, v in sorted(cont.items())), flush=True)
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"-> {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
