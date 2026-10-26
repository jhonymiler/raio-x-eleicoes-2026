#!/usr/bin/env python3
"""Analise forense de Benford sobre votacao por secao do TSE.

Uso:
    python3 analisar.py <csv_por_secao> <rotulo> [--out DIR]

O CSV e o 'votacao_secao_<ano>_BR.csv' do portal de dados abertos do TSE
(latin-1, delimitado por ';').

Dois niveis de agregacao, porque a lei de Benford so vale num deles:

  SECAO     ~400 eleitores, votos de 0 a ~400. Faixa estreita: sigma em
            decadas pequeno => PRIMEIRO digito NAO se aplica. Usa-se o
            teste do SEGUNDO digito (2BL, padrao em election forensics),
            dois ultimos digitos e duplicacao.

  MUNICIPIO totais variam de ~10^2 a ~10^6. Faixa larga => primeiro digito
            e dois primeiros digitos sao validos.

O script imprime o gate de aplicabilidade antes de cada teste e se recusa
a interpretar um teste fora do seu dominio.
"""

from __future__ import annotations

import csv
import math
import sys
from array import array
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import benford as bf  # noqa: E402

CSV_CAMPOS = {
    "SG_UF": 10, "CD_MUNICIPIO": 13, "NM_MUNICIPIO": 14,
    "NR_ZONA": 15, "NR_SECAO": 16, "CD_CARGO": 17,
    "NR_VOTAVEL": 19, "NM_VOTAVEL": 20, "QT_VOTOS": 21,
}


def carregar(caminho: Path):
    """Le o CSV uma vez e devolve (por_secao, por_municipio, meta)."""
    por_secao: dict[str, array] = defaultdict(lambda: array("i"))
    por_mun: dict[tuple[str, str], int] = defaultdict(int)
    nomes: dict[str, str] = {}
    secoes: set = set()
    uf_de_mun: dict[str, str] = {}

    with open(caminho, encoding="latin-1", newline="") as fh:
        leitor = csv.reader(fh, delimiter=";", quotechar='"')
        next(leitor)
        for linha in leitor:
            if len(linha) < 22 or linha[CSV_CAMPOS["CD_CARGO"]] != "1":
                continue
            if linha[CSV_CAMPOS["SG_UF"]] == "ZZ":        # exterior nao e municipio
                continue
            nr = linha[CSV_CAMPOS["NR_VOTAVEL"]]
            try:
                votos = int(linha[CSV_CAMPOS["QT_VOTOS"]])
            except ValueError:
                continue
            mun = linha[CSV_CAMPOS["CD_MUNICIPIO"]]
            por_secao[nr].append(votos)
            por_mun[(nr, mun)] += votos
            nomes.setdefault(nr, linha[CSV_CAMPOS["NM_VOTAVEL"]])
            uf_de_mun.setdefault(mun, linha[CSV_CAMPOS["SG_UF"]])
            secoes.add((mun, linha[CSV_CAMPOS["NR_ZONA"]],
                        linha[CSV_CAMPOS["NR_SECAO"]]))

    meta = {"n_secoes": len(secoes), "n_municipios": len(uf_de_mun),
            "nomes": nomes, "uf_de_mun": uf_de_mun}
    return por_secao, por_mun, meta


# --------------------------------------------------------------------------
# relatorio
# --------------------------------------------------------------------------

def linha_gate(valores, rotulo: str) -> tuple[str, bool]:
    """Dois gates: o lognormal (otimista) e o de Fourier empirico (exato).

    O que decide e o empirico. Se |phi(2pi)| for muito maior que o ruido
    amostral sqrt(1/n), a propria forma da distribuicao nao e Benford, e
    qualquer desvio nos digitos e estrutural -- nao e sinal de fraude.
    """
    sd, desv_ln, n = bf.sigma_decadas(valores)
    f = bf.fourier_empirico(valores)
    exc = f["excesso_k1"]
    if exc < 3:
        veredito = "APLICAVEL (forma compativel com Benford)"
    elif exc < 10:
        veredito = "MARGINAL (forma so parcialmente Benford)"
    else:
        veredito = "NAO APLICAVEL (a forma do dado nao e Benford)"
    txt = (
        f"  gate lognormal : sigma = {sd:.3f} decadas -> desvio previsto "
        f"{desv_ln*100:.3f} pp\n"
        f"  gate de Fourier: |phi(2pi)| = {f['phi'][1]:.4f}  "
        f"(ruido amostral {f['ruido']:.4f}, excesso {exc:.1f}x)\n"
        f"                   |phi(4pi)| = {f['phi'][2]:.4f}   "
        f"desvio previsto na mantissa <= {f['desvio_previsto']:.2f} pp\n"
        f"  veredito: {veredito}   (n={n:,})"
    )
    return txt, exc < 10


def bloco(res: bf.Resultado, tipo_mad: str, top: int = 6) -> str:
    if res.n == 0:
        return f"  {res.nome}: sem dados\n"
    cls = bf.classificar_mad(res.mad, tipo_mad)
    out = [f"  {res.nome}  (n={res.n:,})",
           f"    chi2 = {res.chi2:,.1f}  gl={res.gl}  p = {res.p_chi2:.3g}",
           f"    MAD  = {res.mad:.5f}  -> {cls}"]
    if res.kuiper_v:
        out.append(f"    Kuiper V = {res.kuiper_v:.5f}  p = {res.p_kuiper:.3g}")
    out.append("    maiores desvios (bin: obs vs esp, pp, z):")
    for b, obs, esp, pp, z in res.desvios(top):
        marca = " <<<" if abs(z) > 3 else ""
        out.append(f"      {str(b):>3}: {obs:>9,} vs {esp:>11,.0f}  "
                   f"{pp:+6.2f}pp  z={z:+7.2f}{marca}")
    return "\n".join(out) + "\n"


def analisar(caminho: Path, rotulo: str, saida: Path) -> str:
    L: list[str] = []
    w = L.append

    w("=" * 78)
    w(f"ANALISE FORENSE DE BENFORD -- {rotulo}")
    w(f"fonte: {caminho.name}")
    w("=" * 78)

    por_secao, por_mun, meta = carregar(caminho)
    w(f"\nsecoes distintas: {meta['n_secoes']:,}")
    w(f"municipios:       {meta['n_municipios']:,}")
    w(f"votaveis:         {len(por_secao)}")

    # ordena por total de votos
    totais = {nr: sum(v) for nr, v in por_secao.items()}
    ordem = sorted(totais, key=lambda k: -totais[k])
    w("\ntotais nacionais:")
    gt = sum(totais.values())
    for nr in ordem:
        w(f"  {nr:>3} {meta['nomes'][nr][:38]:<38} {totais[nr]:>12,}  "
          f"{totais[nr]/gt*100:5.2f}%")

    # ---------------- nivel municipio: primeiro digito ----------------
    w("\n" + "=" * 78)
    w("NIVEL 1 -- TOTAIS POR MUNICIPIO  (primeiro digito)")
    w("=" * 78)
    for nr in ordem:
        serie = [v for (c, _m), v in por_mun.items() if c == nr and v > 0]
        if len(serie) < 500:
            continue
        w(f"\n[{nr}] {meta['nomes'][nr]}")
        g, aplicavel = linha_gate(serie, "municipio")
        w(g)
        if not aplicavel:
            w("  -> 1o digito NAO interpretado: a distribuicao do proprio dado nao e Benford")
            continue
        r1 = bf.avaliar("1o digito", serie, bf.primeiro_digito,
                        bf.p_primeiro_digito())
        r1.kuiper_v, r1.p_kuiper, _ = bf.kuiper_mantissa(serie)
        w(bloco(r1, "primeiro digito"))
        r2 = bf.avaliar("2 primeiros digitos", serie, bf.dois_primeiros,
                        bf.p_dois_primeiros())
        w(bloco(r2, "dois primeiros", top=8))
        inv = bf.invariancia_soma(serie)
        pior = max(inv.items(), key=lambda kv: abs(kv[1] - 1 / 9))
        w(f"    invariancia de soma: fracao por digito inicial "
          f"(esperado 11.11% cada)")
        w("      " + "  ".join(f"{d}:{inv[d]*100:5.2f}%" for d in range(1, 10)))
        w(f"      maior desvio: digito {pior[0]} em {pior[1]*100:.2f}% "
          f"({(pior[1]-1/9)*100:+.2f}pp)\n")

    # ---------------- nivel secao: segundo digito (2BL) ----------------
    w("=" * 78)
    w("NIVEL 2 -- VOTOS POR SECAO  (segundo digito / 2BL)")
    w("=" * 78)
    w("O primeiro digito NAO se aplica aqui: secoes tem ~400 eleitores e a")
    w("faixa e estreita demais. O teste do 2o digito (Mebane) e o padrao da")
    w("literatura de election forensics -- e mesmo ele e contestado.\n")
    for nr in ordem:
        serie = [v for v in por_secao[nr] if v > 0]
        if len(serie) < 1000:
            continue
        w(f"[{nr}] {meta['nomes'][nr]}")
        g, _ = linha_gate(serie, "secao")
        w(g)
        r = bf.avaliar("2o digito (2BL)", serie, bf.segundo_digito,
                       bf.p_segundo_digito())
        w(bloco(r, "segundo digito", top=10))
        ru = bf.uniformidade_dois_ultimos(serie)
        if not ru.n:
            w("    dois ultimos digitos: NAO APLICAVEL "
              "(exige >=4 digitos; votos por secao tem 2-3)")
        else:
            cls = "uniforme" if ru.p_chi2 > 0.01 else "NAO uniforme"
            w(f"    dois ultimos digitos: chi2={ru.chi2:,.0f} gl={ru.gl} "
              f"p={ru.p_chi2:.3g} -> {cls}")
            picos = ru.desvios(5)
            w("      picos: " + ", ".join(
                f"{b:02d} (z={z:+.1f})" for b, _o, _e, _pp, z in picos))
        mais, frac = bf.duplicacao(serie, 8)
        w(f"    duplicacao: top-8 valores = {frac*100:.1f}% das secoes -> "
          + ", ".join(f"{v}x{q:,}" for v, q in mais))
        w("")

    texto = "\n".join(L)
    saida.write_text(texto, encoding="utf-8")
    return texto


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    csv_path = Path(sys.argv[1])
    rotulo = sys.argv[2]
    out_dir = Path(sys.argv[4]) if len(sys.argv) > 4 else \
        Path(__file__).parent.parent / "resultados"
    out_dir.mkdir(parents=True, exist_ok=True)
    destino = out_dir / f"benford_{rotulo.lower().replace(' ', '_')}.txt"
    print(analisar(csv_path, rotulo, destino))
    print(f"\n[gravado em {destino}]")
