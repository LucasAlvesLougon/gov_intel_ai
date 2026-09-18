# Modelo de ameaças e controles

## Trust boundaries

| Fronteira | Entrada não confiável | Controle obrigatório |
|---|---|---|
| Browser → DRF | JSON, multipart, JWT, headers | serializers, autenticação, CORS restrito e limite de tamanho |
| DRF → PostgreSQL | filtros e IDs da URL | ORM parametrizado e queryset tenant-aware |
| DRF → RabbitMQ | IDs de edital/job | schema versionado, sem conteúdo bruto e validação de UUID |
| Worker → PDF parser | bytes enviados pelo usuário | MIME/magic bytes, limite de tamanho, timeout e isolamento de erro |
| Worker/API → OpenCode | chunks recuperados e pergunta | chave em secret, HTTPS, validação exata de modelo, timeout, retry limitado e prompts sem conteúdo integral |
| Worker → modelo local | texto do PDF | artefato fixado por revisão, cache privado, CPU sem chamada de embedding externa e fingerprint persistido |
| LLM → API/UI | texto e estrutura gerados | parse/schema validation, escape na renderização e nunca executar como código |
| API → Redis | chaves derivadas de usuário/query | namespace com tenant, TTL e ausência de PII desnecessária |

## Assets

- Senhas, tokens JWT e chaves OpenCode/providers legados.
- PDFs de editais e seus trechos.
- Email e identificadores de usuários.
- Separação de dados entre empresas.
- Disponibilidade e orçamento das chamadas de IA.

## Abuse cases e mitigação

- **Spoofing:** roubo de token; access token curto, refresh em cookie `httpOnly`, `secure` e `sameSite`, rotação/expiração documentada.
- **Tampering:** alterar `companyId` ou `tenderId`; nunca confiar no tenant do payload e aplicar filtros no servidor.
- **Repudiation:** negar login ou upload; registrar eventos de segurança sem tokens, senhas ou conteúdo integral do PDF.
- **Information disclosure:** enumeração de usuários/editais; erros genéricos, respostas tenant-aware e allowlist de campos.
- **Denial of service:** PDFs enormes, polling e prompts longos; limites de bytes/tokens, throttling, timeout e retry limitado.
- **Elevation of privilege:** mudar role ou acessar outro tenant; role não vem do cliente e cada endpoint verifica autorização.
- **Prompt injection:** instruções maliciosas dentro do PDF; contexto é dado, não instrução, e o LLM não recebe ferramentas destrutivas.
- **Poisoned retrieval:** chunks de outro tenant ou espaço vetorial; filtro por tenant e identidade completa do embedding antes da busca, citações somente de chunks persistidos.

## Controles de sessão

Exceção aprovada pelo usuário em 2026-09-16: o cadastro mantém HTTP 409 com
mensagem genérica para duplicidade de email, aceitando a inferência pelo status.
A exceção não se aplica a login ou refresh. Ver docs/implementation-decisions.md.

- Access token curto, mantido somente em memória no frontend.
- Refresh token em cookie `httpOnly`, `secure` fora de localhost e `sameSite=Lax`.
- Endpoint de refresh valida CSRF token e origem permitida; access expira em 15 minutos, refresh em 7 dias, cada refresh é rotacionado e o anterior é blacklistado. Logout revoga o refresh atual e reuse detectado invalida a cadeia.
- CORS limitado a origens configuradas; nunca `*` com credenciais.
- Headers: CSP, HSTS em HTTPS, `X-Content-Type-Options`, `X-Frame-Options` e `Referrer-Policy`.
- Login e refresh com throttling; respostas não revelam se um email existe.

## Upload seguro

- Permitir somente PDF, conferindo MIME e assinatura/magic bytes.
- Limitar tamanho configurável e rejeitar arquivo vazio.
- Gerar nome interno; nunca usar nome enviado como caminho.
- Armazenar fora da árvore pública e não servir PDF por URL sem autorização.
- Parser sem acesso a comandos do sistema; timeout e captura de exceções.
- Limitar páginas, caracteres e memória; tratar PDFs criptografados, polyglots e decompression bombs como falhas do domínio.
- Não enviar PDF inteiro ao LLM quando chunks suficientes forem recuperados.
- Conteúdo do PDF é delimitado como dado não confiável; nenhum tool call, URL fetch, shell ou `innerHTML` usa texto do modelo.

## Secrets, dependências e privacidade

- Commitar somente `.env.example`; ignorar `.env`, `.env.local`, `*.key` e `*.pem`.
- Não registrar tokens, senhas, chaves, prompts completos ou PDF integral.
- Logs usam correlation ID sem PII, com redaction e retenção definida; stack traces ficam somente em armazenamento de acesso restrito.
- Classificar email como PII; definir retenção e exclusão para usuário, PDF, chunks, cache e conversas antes do deploy.
- Fixar lockfiles e executar auditoria nativa do gerenciador no CI; não usar `audit fix --force`.

## Security acceptance gate

- [x] Nenhum segredo em fonte ou histórico.
- [x] Testes cobrem autenticação, autorização e cross-tenant.
- [x] Upload tem limite, magic bytes e erro seguro.
- [x] CORS, headers e cookies estão configurados.
- [x] Auth, busca e chat têm rate limiting.
- [x] Saída do LLM é tratada como dado não confiável.
- [x] Auditoria de dependências não possui falha crítica/alta alcançável sem mitigação.

Evidência 2026-09-18: `pip-audit --strict --disable-pip` sobre o requirements
exportado do lock (com o wheel `torch` CPU-only explicitamente separado por não
existir no índice PyPI) retornou zero vulnerabilidades conhecidas; a checagem
também exige `torch` com sufixo `+cpu`. Os dois `npm audit --audit-level=high`
retornaram zero findings. A workspace não possui histórico Git; a checagem de
fonte e a varredura de arquivos rastreados no CI não encontraram padrões de
credenciais.
