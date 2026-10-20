"""Carrega o certificado digital, seja de um .pfx ou do repositório do Windows."""
import os

from asn1crypto import x509 as asn1_x509
from pyhanko.sign import signers
from pyhanko_certvalidator.registry import SimpleCertificateStore

_cache = {}


def obter_signer(cert_cfg: dict) -> signers.Signer:
    nome = cert_cfg["nome"]
    if nome not in _cache:
        if cert_cfg["tipo"] == "pfx":
            _cache[nome] = _signer_pfx(cert_cfg)
        elif cert_cfg["tipo"] == "windows":
            _cache[nome] = WindowsStoreSigner(cert_cfg["thumbprint"])
        else:
            raise ValueError(f"Tipo de certificado desconhecido: {cert_cfg['tipo']}")
    return _cache[nome]


def _signer_pfx(cfg):
    senha = os.environ.get(cfg.get("senha_env", ""), "")    # senha fica fora do código
    signer = signers.SimpleSigner.load_pkcs12(cfg["pfx"], passphrase=senha.encode() or None)
    if signer is None:
        raise RuntimeError(f"Não consegui abrir o PFX {cfg['pfx']} (senha errada?)")
    return signer


class WindowsStoreSigner(signers.Signer):
    """Assina usando um certificado instalado no Windows ("ID digital do Windows").

    É o mesmo certificado que aparece no Acrobat no vídeo. Funciona com A1 e com
    A3: no A3, o próprio Windows abre a janela pedindo o PIN do token.
    Requer: pip install pythonnet (somente Windows).
    """

    def __init__(self, thumbprint: str):
        import clr  # noqa: F401  (pythonnet)
        clr.AddReference("System.Security")
        from System.Security.Cryptography.X509Certificates import (
            X509Store, StoreName, StoreLocation, OpenFlags, X509FindType, X509Chain,
            RSACertificateExtensions,
        )
        from System.Security.Cryptography import HashAlgorithmName, RSASignaturePadding

        store = X509Store(StoreName.My, StoreLocation.CurrentUser)
        store.Open(OpenFlags.ReadOnly)
        try:
            achados = store.Certificates.Find(
                X509FindType.FindByThumbprint, thumbprint.replace(" ", ""), False)
            if achados.Count == 0:
                raise RuntimeError(f"Certificado {thumbprint} não encontrado no Windows")
            self._cert_net = achados[0]
        finally:
            store.Close()

        self._rsa = RSACertificateExtensions.GetRSAPrivateKey(self._cert_net)
        self._hashes = {"sha256": HashAlgorithmName.SHA256,
                        "sha384": HashAlgorithmName.SHA384,
                        "sha512": HashAlgorithmName.SHA512}
        self._padding = RSASignaturePadding.Pkcs1

        # Monta a cadeia (AC SyngularID -> AC raiz) para embutir no PDF
        cadeia = X509Chain()
        cadeia.Build(self._cert_net)
        certs = [asn1_x509.Certificate.load(bytes(el.Certificate.RawData))
                 for el in cadeia.ChainElements]
        super().__init__(signing_cert=certs[0],
                         cert_registry=SimpleCertificateStore.from_certs(certs))

    async def async_sign_raw(self, data: bytes, digest_algorithm: str, dry_run=False) -> bytes:
        tamanho = self._rsa.KeySize // 8
        if dry_run:
            return bytes(tamanho)
        from System import Array, Byte
        dados_net = Array[Byte](data)
        assinatura = self._rsa.SignData(dados_net, self._hashes[digest_algorithm], self._padding)
        return bytes(assinatura)
