# Melhorias do Assinador de PDF — divisão de tarefas

Levantamento feito a partir do código atual (`assinador.py`, `certificados.py`, `localizador.py`, `config.py`)
e dos testes de 20/10/2026, que assinaram o `CONTRATO_TESTE.pdf` com um certificado de teste do Windows.

São quatro grupos independentes, um por integrante (ou dupla). Cada item traz:
- **Atual:** como funciona hoje;
- **Desejado:** onde queremos chegar;
- **Como fazer:** uma sugestão de implementação.

| Grupo | Tema | Arquivos principais |
|---|---|---|
| 1 | Robustez e operação | `assinador.py` |
| 2 | Validade jurídica e certificados | `assinador.py`, `certificados.py` |
| 3 | Localização da assinatura | `localizador.py` |
| 4 | Configuração, testes e repositório | `config.py`, `tests/`, raiz |

> **Ordem sugerida:**
> 1. O **Grupo 4** começa pela base de testes (item 4.4). Ela ajuda todos a validar o que fizerem.
> 2. Os outros grupos podem trabalhar em paralelo.
> 3. Cada grupo deve fazer suas mudanças numa branch própria (`feature/grupoN-...`) para evitar conflito.

---

## Grupo 1 — Robustez e operação

Objetivo: o programa nunca deixa um arquivo errado na saída, nunca para sozinho e sempre avisa quando algo dá errado.

### 1.1 Gravação segura do PDF assinado
- **Atual:**
  - `assinar_pdf()` abre `saida` (`open(saida, "wb")`) antes de assinar.
  - Se a assinatura falhar no meio (token sem PIN, certificado vencido, PDF estranho), sobra em `assinados/` um PDF vazio ou corrompido.
  - Enquanto isso, o original vai para `erro/`.
- **Desejado:** em `assinados/` só entra um PDF completo e válido.
- **Como fazer:**
  - Assinar para um arquivo temporário na mesma pasta (`saida.with_suffix(".tmp")`).
  - Só no final chamar `os.replace(tmp, saida)`.
  - No `except`, apagar o `.tmp` se ele existir.

### 1.2 Loop principal à prova de falhas
- **Atual:**
  - Se o `log_assinaturas.csv` estiver aberto no Excel, `registrar()` lança `PermissionError`.
  - Como `registrar()` também é chamado dentro do `except` de `processar()`, e o `while True` do `main()` não tem proteção, o monitor encerra sem ninguém saber.
- **Desejado:** nenhum erro isolado derruba o monitor.
- **Como fazer:**
  - Envolver `ciclo()` em `try/except Exception` dentro do `while`, com `log.exception(...)`.
  - Em `registrar()`, tentar algumas vezes com pausa. Se continuar bloqueado, gravar a linha num arquivo reserva (`log_pendente.csv`) e mesclar depois.

### 1.3 Log em arquivo
- **Atual:**
  - O `logging.basicConfig` escreve só no console.
  - Rodando com `pythonw` pelo Agendador de Tarefas não existe console, então as mensagens se perdem.
- **Desejado:** um log técnico persistente, com rotação, ao lado do CSV.
- **Como fazer:**
  - Usar `logging.handlers.RotatingFileHandler(BASE / "assinador.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")`.
  - Manter também o `StreamHandler` para quando rodar pelo terminal.

### 1.4 Aviso quando um arquivo cai em `erro/`
- **Atual:** é preciso abrir a pasta `erro/` ou o CSV para descobrir que algo falhou.
- **Desejado:** o responsável recebe um aviso com o nome do arquivo e o motivo.
- **Como fazer:**
  - Criar uma função `notificar(assunto, texto)` chamada no `except` de `processar()`.
  - Para e-mail, usar `smtplib` com os dados do SMTP na config e a senha em variável de ambiente.
  - Para Teams, usar um webhook (`urllib.request` com POST em JSON).
  - Deixar ligar e desligar na config.

### 1.5 Não assinar o mesmo PDF duas vezes
- **Atual:** se o mesmo arquivo for colocado de novo, é assinado de novo e vira `_ASSINADO_2.pdf` (isso aconteceu nos nossos testes).
- **Desejado:** reconhecer o duplicado pelo conteúdo e não assinar outra vez.
- **Como fazer:**
  - Antes de assinar, procurar o `sha256_original` no CSV com status `ASSINADO`.
  - Se já existir, mover para `originais/` e registrar o status `DUPLICADO`, apontando para o arquivo já assinado.

### 1.6 Sinal de que o monitor está rodando
- **Atual:** não dá para saber se o monitor está rodando sem olhar o Gerenciador de Tarefas.
- **Desejado:** um sinal simples de que o programa está ativo.
- **Como fazer:**
  - A cada ciclo, gravar a data e hora em `BASE / "ultimo_ciclo.txt"`.
  - Opcional: se esse arquivo estiver com mais de 5 minutos, outro script ou o próprio Agendador reinicia o processo.

---

## Grupo 2 — Validade jurídica e certificados

Objetivo: a assinatura continuar válida e verificável por anos, e problemas de certificado aparecerem antes do primeiro PDF real.

### 2.1 Carimbo do tempo (TSA)
- **Atual:**
  - A assinatura é PAdES básica (B-B), sem carimbo do tempo.
  - A data mostrada no carimbo visível vem do relógio do próprio computador.
- **Desejado:**
  - Uma data e hora certificada por uma Autoridade de Carimbo do Tempo (PAdES B-T).
  - Isso prova que a assinatura foi feita enquanto o certificado era válido.
- **Como fazer:**
  ```python
  from pyhanko.sign import timestamps
  tsa = timestamps.HTTPTimeStamper(config.URL_TSA)
  pdf_signer = signers.PdfSigner(meta, signer=signer, stamp_style=estilo, timestamper=tsa)
  ```
  - Para testes, usar uma TSA gratuita (ex.: `http://timestamp.digicert.com`).
  - Em produção, usar a TSA da ICP-Brasil contratada junto com a certificadora (geralmente é paga). Verificar isso com o CEO.

### 2.2 Validação de longo prazo (LTV — PAdES B-LT/LTA)
- **Atual:** o PDF leva só o certificado e a cadeia, sem as informações de revogação (CRL/OCSP).
- **Desejado:** o PDF continua validável mesmo depois que o certificado vencer ou a AC sair do ar.
- **Como fazer:**
  ```python
  from pyhanko_certvalidator import ValidationContext
  meta = signers.PdfSignatureMetadata(
      ...,
      embed_validation_info=True,
      validation_context=ValidationContext(allow_fetching=True),
      use_pades_lta=True,   # exige a TSA do item 2.1
  )
  ```
  - Testar no [Verificador do ITI](https://validar.iti.gov.br) com o certificado real.

### 2.3 Validar o PDF logo depois de assinar
- **Atual:** o programa considera sucesso assim que `sign_pdf()` termina, sem conferir o resultado.
- **Desejado:** só mover para `assinados/` e registrar `ASSINADO` se a assinatura estiver íntegra.
- **Como fazer:**
  - Criar `validar(saida)` usando o mesmo código do teste de 20/10:
    ```python
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    with open(saida, "rb") as f:
        sig = PdfFileReader(f).embedded_signatures[-1]
        status = validate_pdf_signature(sig, ValidationContext(allow_fetching=False))
    ok = status.intact and status.valid
    ```
  - Se `ok` for falso, lançar uma exceção, o que manda o arquivo para `erro/`.
  - Integra com o item 1.1: validar o `.tmp` antes do `os.replace`.

### 2.4 Checar certificados ao iniciar
- **Atual:**
  - Certificado ausente, vencido ou com thumbprint de exemplo (`COLE_AQUI_O_THUMBPRINT_DO_CERT_PROJETA`) só dá erro quando chega um PDF daquela empresa.
  - Foi exatamente o erro `Certificado 568D... não encontrado no Windows` dos nossos testes.
- **Desejado:** ao iniciar, o programa lista cada certificado com OK ou o problema encontrado e avisa com antecedência sobre o vencimento.
- **Como fazer:**
  - Criar em `certificados.py` uma função `verificar_todos()` que, para cada item de `config.CERTIFICADOS`:
    - tenta carregar o signer;
    - confere se a chave privada está disponível;
    - lê `signing_cert.not_valid_after`.
  - Chamar no início do `main()`.
  - Se faltar menos de 30 dias para vencer, registrar um aviso no log e chamar `notificar()` (item 1.4).

### 2.5 Certificado A3 (token) e execução sem ninguém na máquina
- **Atual:**
  - Com token A3, o Windows abre uma janela pedindo o PIN.
  - Rodando com `pythonw` pelo Agendador sem ninguém na frente, o processo fica parado esperando.
- **Desejado:** um comportamento definido e documentado.
- **Como fazer:**
  - Descobrir qual tipo de certificado o CEO usa.
  - Se for A3, documentar que alguém precisa digitar o PIN, ou ver se o driver do token permite lembrar o PIN por sessão.
  - Recomendar um A1 (`.pfx`) dedicado para a máquina automática.
  - Colocar um tempo limite na assinatura: se passar do limite, o arquivo vai para `erro/` com a mensagem "aguardando PIN".

---

## Grupo 3 — Localização da assinatura (`localizador.py`)

Objetivo: achar o lugar certo em qualquer contrato real e, na dúvida, mandar para revisão em vez de assinar no lugar errado.

### 3.1 Mais de uma empresa no mesmo PDF
- **Atual:**
  - `localizar()` devolve o primeiro nome que encontra (da última página para a primeira) e para.
  - Um contrato com CAW e PROJETA sai com uma assinatura só.
- **Desejado:** definir a regra com o CEO e implementar. As opções são:
  - (a) assinar por todas as empresas encontradas;
  - (b) assinar só por uma e avisar.
- **Como fazer:**
  - Fazer `localizar()` devolver uma `list[Local]`.
  - Em `processar()`, assinar em sequência: cada assinatura é incremental sobre a anterior, com a saída de uma virando a entrada da próxima.
  - A coluna `empresa` do CSV passa a aceitar vários nomes (`CAW|PROJETA`).

### 3.2 Busca de texto tolerante
- **Atual:**
  - `pagina.search_for(texto_ancora)` exige o texto exato.
  - Falha com diferenças de maiúsculas e minúsculas, acentos, espaços duplos ou nome quebrado em duas linhas.
  - Também pode achar o nome no meio de uma cláusula (ex.: "CONTRATADA: CAW PROJETOS..." na página 1).
- **Desejado:** achar o nome mesmo com essas variações e preferir o que está num bloco de assinatura.
- **Como fazer:**
  - Extrair as palavras com `pagina.get_text("words")`.
  - Normalizar (maiúsculas, sem acentos via `unicodedata`, espaços colapsados) e comparar sequências de palavras.
  - Dar preferência à ocorrência que tem uma linha logo acima (`_linha_acima`) e descartar as que estão no meio de um parágrafo.

### 3.3 Não assinar "às cegas" quando não há linha
- **Atual:** se `_linha_acima()` não acha a linha, o código usa o próprio nome como referência e assina assim mesmo.
- **Desejado:** sem linha de assinatura, o arquivo vai para `erro/` (ou `revisar/`) com o motivo "linha de assinatura não encontrada".
- **Como fazer:**
  - Em `localizar()`, quando `linha is None`, não retornar o `Local`. Retornar um motivo, ou lançar uma exceção específica que `processar()` registra no CSV.
  - Opcional: deixar isso ligado ou desligado na config (`EXIGIR_LINHA = True`).

### 3.4 PDF escaneado (sem texto)
- **Atual:** num PDF que é só imagem, `search_for` nunca acha nada, e o erro diz "Nenhum nome de empresa conhecido encontrado", o que engana.
- **Desejado:** identificar o caso e dar uma mensagem clara. Opcional: tentar OCR.
- **Como fazer:**
  - Se `"".join(p.get_text() for p in doc).strip()` vier vazio, lançar o erro "PDF sem camada de texto (escaneado)".
  - Para o OCR (opcional), instalar o Tesseract e usar `pagina.get_textpage_ocr(language="por")` no PyMuPDF.

### 3.5 Tamanho e posição do retângulo
- **Atual:**
  - O retângulo tem sempre 210×55 pt, a partir do início da linha.
  - Não verifica se ele sai da página ou cobre texto do contrato (ex.: a data "Curitiba/PR, 20 de outubro..." logo acima).
- **Desejado:** o carimbo se ajusta à largura da linha e nunca cobre texto.
- **Como fazer:**
  - Usar `largura = min(config.LARGURA_ASSINATURA, linha.width)`.
  - Antes de devolver, checar se há texto dentro do retângulo com `pagina.get_text("words", clip=ret)`. Se houver, reduzir a altura ou mandar para revisão.
  - Garantir que o retângulo fica dentro de `pagina.rect`.

---

## Grupo 4 — Configuração, testes e repositório

Objetivo: o projeto roda em qualquer máquina sem editar arquivo versionado, e toda mudança é testada automaticamente.

### 4.1 Configuração por máquina fora do git
- **Atual:**
  - `BASE` e os thumbprints ficam fixos no `config.py`, que está no git.
  - Para testar foi preciso trocar `C:\Users\bezao\...` por `C:\Users\caudo\...` e o thumbprint, com risco de commitar isso e quebrar a máquina do CEO.
- **Desejado:** o `config.py` só tem valores padrão, e cada máquina tem seu próprio arquivo local ignorado pelo git.
- **Como fazer:**
  - No fim do `config.py`, carregar `config_local.py` se ele existir:
    ```python
    try:
        from config_local import *   # noqa
    except ImportError:
        pass
    ```
  - Versionar um `config_local.exemplo.py` e colocar `config_local.py` no `.gitignore`.
  - Alternativa: ler `BASE` de uma variável de ambiente (`os.environ.get("ASSINADOR_BASE", ...)`).

### 4.2 Motivo, local e texto por empresa
- **Atual:** `reason="Assinatura do documento"` e `location="Curitiba/PR"` estão fixos em `assinar_pdf()`.
- **Desejado:** configurar por certificado ou empresa no `config.py`.
- **Como fazer:**
  - Adicionar `"motivo"` e `"local"` em cada item de `CERTIFICADOS`, com padrão global.
  - Em `assinar_pdf()`, usar `local.certificado.get("local", config.LOCAL_PADRAO)`.

### 4.3 Versões fixas das dependências
- **Atual:**
  - O `requirements.txt` usa `>=`.
  - Na nossa máquina veio pymupdf 2.0 e pyhanko 0.38, e a máquina do CEO pode receber outras versões.
- **Desejado:** a mesma versão em todas as máquinas.
- **Como fazer:**
  - Depois de tudo funcionando, rodar `pip freeze` no `.venv` e fixar com `==` as versões de `pyhanko`, `pyhanko-certvalidator`, `pymupdf` e `pythonnet`.
  - Documentar a versão do Python (3.14 nos testes).

### 4.4 Testes automatizados (pytest) — começar por aqui
- **Atual:**
  - Não existe nenhum teste.
  - A validação foi feita à mão: gerar o PDF, criar o certificado, rodar e conferir.
- **Desejado:** `pytest` cobre o localizador e o fluxo completo sem precisar de certificado real.
- **Como fazer:**
  - Criar `tests/conftest.py` com:
    - uma fixture que gera PDFs de exemplo com PyMuPDF (com linha, com `____`, sem linha, duas empresas, só imagem);
    - uma fixture que gera um certificado em memória com a biblioteca `cryptography` e devolve um `SimpleSigner`, igual ao `run_teste.py` usado em 20/10.
  - Usar `monkeypatch` para apontar `config.BASE` para `tmp_path` e trocar `certificados.obter_signer` pelo signer de teste.
  - Testes mínimos:
    - assina e cria o arquivo em `assinados/`;
    - move o original para `originais/`;
    - grava a linha `ASSINADO` no CSV;
    - a assinatura é íntegra (`validate_pdf_signature`);
    - um PDF sem empresa vai para `erro/`.
  - Cada grupo acrescenta testes para os seus itens.

### 4.5 `.gitignore` e higiene do repositório
- **Atual:** não existe `.gitignore`. Pastas de teste, `.pfx`, logs e `__pycache__` podem acabar commitados.
- **Desejado:** nada sensível ou gerado vai para o git.
- **Como fazer:** criar um `.gitignore` com:
  ```
  __pycache__/
  .venv/
  *.pfx
  *.p12
  *.pem
  config_local.py
  log_*.csv
  *.log
  teste/
  ```

### 4.6 Documentação
- **Atual:** existe só o `instrucao.txt`, que não traz o roteiro de teste nem os problemas mais comuns.
- **Desejado:** um `README.md` em `leitorPDF/` com instalação, configuração, teste e solução de problemas.
- **Como fazer:** transformar o `instrucao.txt` em README e acrescentar:
  - o roteiro de teste com `New-SelfSignedCertificate` (criar, colar o thumbprint, rodar, remover com `Remove-Item Cert:\CurrentUser\My\<THUMBPRINT>`);
  - o que significa "validade desconhecida" no Acrobat;
  - como rodar o `pytest`;
  - a tabela de erros comuns, por exemplo "Certificado ... não encontrado no Windows" → thumbprint errado ou certificado não instalado.

---

## Checklist de entrega (todos os grupos)
- [ ] Mudança feita na branch do grupo.
- [ ] Teste automatizado cobrindo o item (com a base do item 4.4).
- [ ] `python assinador.py --uma-vez` rodado com o `CONTRATO_TESTE.pdf` e um certificado de teste.
- [ ] PDF assinado aberto no Acrobat (assinatura presente, documento não alterado).
- [ ] README atualizado, se o item mudar o uso ou a configuração.
