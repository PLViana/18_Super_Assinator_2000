"""Configuração do assinador. Ajuste os caminhos e certificados aqui."""
from pathlib import Path

BASE = Path(r"C:\Users\bezao\Desktop\teste")          # pasta raiz na máquina dedicada

PASTA_ASSINAR   = BASE / "assinar"         # CEO coloca os PDFs validados aqui
PASTA_ASSINADOS = BASE / "assinados"       # saída com o sufixo _ASSINADO
PASTA_ORIGINAIS = BASE / "originais"       # cópia do arquivo original
PASTA_ERRO      = BASE / "erro"            # falhou ou não achou onde assinar
ARQUIVO_LOG     = BASE / "log_assinaturas.csv"

INTERVALO_SEGUNDOS = 30                    # de quanto em quanto tempo verifica a pasta

# ---------------------------------------------------------------------------
# Certificados. No vídeo aparecem duas empresas. O programa escolhe o
# certificado procurando o "texto_ancora" (nome da empresa abaixo da linha de
# assinatura) dentro do PDF.
#
# tipo = "windows": usa o certificado instalado no Windows (como o Acrobat faz).
#                   Informe a impressão digital (thumbprint) do certificado.
# tipo = "pfx":     usa um arquivo .pfx exportado + senha.
# ---------------------------------------------------------------------------
CERTIFICADOS = [
    {
        "nome": "CAW",
        "texto_ancora": "CAW PROJETOS E CONSULTORIA INDUSTRIAL LTDA",
        "tipo": "windows",
        "thumbprint": "568D1894D16A72C0EE21012602A41736C16E2217",
        # "tipo": "pfx", "pfx": r"C:\certs\caw.pfx", "senha_env": "SENHA_CERT_CAW",
    },
    {
        "nome": "PROJETA",
        "texto_ancora": "PROJETA IMOVEIS LTDA",
        "tipo": "windows",
        "thumbprint": "COLE_AQUI_O_THUMBPRINT_DO_CERT_PROJETA",
    },
]

# Tamanho do retângulo de assinatura (em pontos; 1 cm ≈ 28,35 pt)
LARGURA_ASSINATURA = 210
ALTURA_ASSINATURA = 55

# Texto da assinatura visível (igual ao "Texto padrão" do Acrobat)
TEXTO_CARIMBO = "Assinado de forma digital por\n%(signer)s\nDados: %(ts)s"
