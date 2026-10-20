"""Localiza onde a assinatura deve ficar no PDF.

Reproduz o que o CEO faz no vídeo: desenhar o retângulo logo acima da linha
que fica sobre o nome da empresa.
"""
from dataclasses import dataclass

import pymupdf

import config


@dataclass
class Local:
    pagina: int                        # índice da página (0 = primeira)
    caixa: tuple                       # (x1, y1, x2, y2) em coordenadas PDF
    certificado: dict                  # certificado escolhido pela âncora


def _linha_acima(pagina, ancora, distancia_max=25):
    """Procura uma linha (desenhada ou feita com ____) logo acima da âncora."""
    melhor = None
    for desenho in pagina.get_drawings():
        r = desenho["rect"]
        horizontal = r.height < 3 and r.width > 60
        if horizontal and 0 <= ancora.y0 - r.y1 <= distancia_max:
            melhor = r if melhor is None or r.y1 > melhor.y1 else melhor
    for r in pagina.search_for("_____"):
        if 0 <= ancora.y0 - r.y1 <= distancia_max:
            melhor = r if melhor is None or r.y1 > melhor.y1 else melhor
    return melhor


def localizar(caminho_pdf) -> Local | None:
    """Retorna onde assinar ou None se não encontrou nenhuma âncora conhecida."""
    with pymupdf.open(caminho_pdf) as doc:
        # Percorre da última página para a primeira: o bloco de assinatura
        # quase sempre está no fim do documento.
        for idx in range(len(doc) - 1, -1, -1):
            pagina = doc[idx]
            for cert in config.CERTIFICADOS:
                achados = pagina.search_for(cert["texto_ancora"])
                if not achados:
                    continue
                ancora = achados[-1]                      # última ocorrência
                linha = _linha_acima(pagina, ancora)
                base = (linha.y0 if linha else ancora.y0) - 1
                x0 = linha.x0 if linha else ancora.x0
                ret = pymupdf.Rect(x0, base - config.ALTURA_ASSINATURA,
                                   x0 + config.LARGURA_ASSINATURA, base)
                # Converte do sistema do PyMuPDF (origem no topo) para o do
                # PDF (origem embaixo), já tratando rotação e margens.
                ret_pdf = ret * ~pagina.transformation_matrix
                ret_pdf.normalize()
                return Local(idx, (ret_pdf.x0, ret_pdf.y0, ret_pdf.x1, ret_pdf.y1), cert)
    return None
