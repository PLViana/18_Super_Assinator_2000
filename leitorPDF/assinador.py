"""Assinador automático de PDFs.

Fluxo: pasta "assinar" -> assina -> pasta "assinados" (+ log CSV).
Uso:
    python assinador.py           # fica monitorando a pasta
    python assinador.py --uma-vez # processa o que houver e sai
"""
import argparse
import csv
import hashlib
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from pyhanko import stamp
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import fields, signers

import certificados
import config
from localizador import localizar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("assinador")

CAMPOS_LOG = ["data_hora", "arquivo", "status", "empresa", "pagina",
              "sha256_original", "sha256_assinado", "detalhe"]


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def registrar(**linha):
    novo = not config.ARQUIVO_LOG.exists()
    with open(config.ARQUIVO_LOG, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_LOG, delimiter=";")
        if novo:
            w.writeheader()
        w.writerow({"data_hora": datetime.now().isoformat(timespec="seconds"), **linha})


def destino_livre(pasta: Path, nome: str) -> Path:
    """Evita sobrescrever: CONTRATO_ASSINADO.pdf, CONTRATO_ASSINADO_2.pdf..."""
    alvo = pasta / nome
    n = 2
    while alvo.exists():
        alvo = pasta / f"{Path(nome).stem}_{n}{Path(nome).suffix}"
        n += 1
    return alvo


def assinar_pdf(entrada: Path, saida: Path, local) -> None:
    signer = certificados.obter_signer(local.certificado)
    nome_campo = f"Assinatura_{local.certificado['nome']}_{datetime.now():%Y%m%d%H%M%S}"

    with open(entrada, "rb") as f_in:
        writer = IncrementalPdfFileWriter(f_in, strict=False)
        fields.append_signature_field(
            writer, fields.SigFieldSpec(nome_campo, on_page=local.pagina, box=local.caixa))

        meta = signers.PdfSignatureMetadata(
            field_name=nome_campo,
            md_algorithm="sha256",
            subfilter=fields.SigSeedSubFilter.PADES,   # padrão PAdES (aceito pelo ITI/Acrobat)
            reason="Assinatura do documento",
            location="Curitiba/PR",
        )
        estilo = stamp.TextStampStyle(stamp_text=config.TEXTO_CARIMBO, border_width=0)
        pdf_signer = signers.PdfSigner(meta, signer=signer, stamp_style=estilo)

        with open(saida, "wb") as f_out:
            pdf_signer.sign_pdf(writer, output=f_out)


def processar(arquivo: Path) -> None:
    log.info("Processando %s", arquivo.name)
    hash_orig = sha256(arquivo)
    try:
        local = localizar(arquivo)
        if local is None:
            raise LookupError("Nenhum nome de empresa conhecido encontrado; revisar manualmente")

        saida = destino_livre(config.PASTA_ASSINADOS, f"{arquivo.stem}_ASSINADO.pdf")
        assinar_pdf(arquivo, saida, local)

        shutil.move(arquivo, destino_livre(config.PASTA_ORIGINAIS, arquivo.name))
        registrar(arquivo=arquivo.name, status="ASSINADO", empresa=local.certificado["nome"],
                  pagina=local.pagina + 1, sha256_original=hash_orig,
                  sha256_assinado=sha256(saida), detalhe=saida.name)
        log.info("OK -> %s", saida.name)

    except Exception as e:  # qualquer falha manda o arquivo para "erro"
        log.error("Falha em %s: %s", arquivo.name, e)
        shutil.move(arquivo, destino_livre(config.PASTA_ERRO, arquivo.name))
        registrar(arquivo=arquivo.name, status="ERRO", empresa="", pagina="",
                  sha256_original=hash_orig, sha256_assinado="", detalhe=str(e))


def arquivo_estavel(arquivo: Path, espera=1.0) -> bool:
    """Garante que o arquivo terminou de ser copiado para a pasta."""
    tamanho = arquivo.stat().st_size
    time.sleep(espera)
    return arquivo.exists() and arquivo.stat().st_size == tamanho


def ciclo():
    for pdf in sorted(config.PASTA_ASSINAR.glob("*.pdf")):
        if arquivo_estavel(pdf):
            processar(pdf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uma-vez", action="store_true")
    args = ap.parse_args()

    for p in (config.PASTA_ASSINAR, config.PASTA_ASSINADOS, config.PASTA_ORIGINAIS, config.PASTA_ERRO):
        p.mkdir(parents=True, exist_ok=True)

    if args.uma_vez:
        ciclo()
        return
    log.info("Monitorando %s a cada %ss", config.PASTA_ASSINAR, config.INTERVALO_SEGUNDOS)
    while True:
        ciclo()
        time.sleep(config.INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    main()
