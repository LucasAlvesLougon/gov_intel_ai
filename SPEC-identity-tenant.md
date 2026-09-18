# Spec: identity-tenant

## Objective

Fornecer cadastro de empresa, usuário proprietário e autenticação JWT para que todos os módulos do GovIntel AI tenham uma fronteira de tenant verificável. O usuário nunca escolhe o tenant efetivo por payload; ele é derivado da identidade autenticada.

## Scope

Incluído:

- Criação de uma empresa durante o registro.
- Criação do primeiro usuário como proprietário da empresa.
- Login com email e senha.
- Access token JWT com TTL de 15 minutos e refresh token JWT com TTL de 7 dias.
- Associação obrigatória de recursos a `company_id`.
- Permissão reutilizável para filtrar e autorizar recursos por empresa.
- Endpoint simples para consultar o usuário autenticado.

Fora do escopo:

- SSO, OAuth e MFA.
- Convites, equipes e RBAC avançado.
- Billing, auditoria regulatória e troca de empresa na mesma sessão.

## Domain Model

### Company

- `id`: UUID, gerado pelo servidor.
- `name`: string não vazia, tamanho máximo definido pelo serializer.
- `slug`: único, gerado pelo servidor.
- `created_at`, `updated_at`.

### User

- Usuário customizado do Django com email como identificador de login.
- `id`: UUID.
- `company_id`: foreign key não nula para `Company`.
- `role`: inicialmente `OWNER`, preparado para extensão posterior.
- `is_active`, `created_at`, `updated_at`.

Regras de integridade:

- Email é único globalmente no MVP.
- Uma empresa deve ter ao menos um usuário ativo.
- Exclusão de empresa e usuário não faz parte do MVP.
- Senhas são armazenadas somente pelo hasher do Django.

## API Contract

Os contratos completos vivem em [docs/api-contract.md](docs/api-contract.md).

### `POST /api/auth/register/`

Entrada:

```json
{
  "companyName": "Alfa Saúde",
  "email": "demo@example.com",
  "password": "SenhaForte123!"
}
```

Saída `201`:

```json
{
  "user": {"id": "uuid", "email": "demo@example.com", "role": "OWNER"},
  "company": {"id": "uuid", "name": "Alfa Saúde", "slug": "alfa-saude"},
  "accessToken": "jwt"
}
```

O refresh token não aparece no JSON: é definido pelo backend em cookie `httpOnly`, `secure` fora de localhost e `sameSite=Lax`. O access token é mantido somente em memória pelo frontend e enviado no header `Authorization`.

O endpoint deve ser atômico: se a criação do usuário falhar, a empresa não permanece criada.

### `POST /api/auth/token/`

Recebe `email` e `password`. Retorna `200` com access token e define o refresh token em cookie protegido. Credenciais inválidas retornam o mesmo erro genérico para não revelar se o email existe.

### `POST /api/auth/token/refresh/`

Usa o refresh cookie, rotaciona o refresh a cada uso e coloca o token anterior em blacklist. Refresh inválido, expirado, reutilizado ou pertencente a usuário inativo retorna `401`.

### `GET /api/auth/me/`

Retorna `200` com `user` e `company` derivados do token.

## Acceptance Criteria

- Registro válido cria exatamente uma empresa e um usuário `OWNER`.
- Registro com email existente retorna `409` no envelope de erro comum.
- Registro inválido retorna `422` sem persistir dados parciais.
- Login válido retorna access token e define refresh token em cookie protegido.
- Credenciais inválidas retornam `401` sem distinguir usuário inexistente de senha incorreta.
- Endpoints protegidos rejeitam token ausente, inválido, expirado ou de usuário inativo.
- `GET /api/auth/me/` não aceita `companyId` fornecido pelo cliente.
- Um usuário autenticado só consegue consultar ou alterar recursos cujo `company_id` seja igual ao seu.
- Tentativa cross-tenant retorna `404` para recursos inexistentes na coleção visível ou `403` quando a existência do recurso já foi estabelecida pelo contrato.
- Existe teste com duas empresas que comprova que uma não acessa a outra.
- Senhas e tokens nunca aparecem em logs ou respostas de erro.
- Refresh por cookie exige CSRF token e/ou verificação de `Origin`/`Referer` conforme o ambiente.
- O handler global de exceções mantém o envelope comum para erros de autenticação, parser, throttling e falhas não tratadas.
- Logout revoga o refresh token atual; a chave de assinatura vem do ambiente/secret manager e suporta rotação operacional sem versionar chaves.

## Commands

```text
docker compose exec api python manage.py makemigrations core
docker compose exec api python manage.py migrate
docker compose exec api pytest backend/tests/unit/core backend/tests/integration/test_identity_tenant.py
docker compose exec api ruff check backend/apps/core backend/tests
```

## Project Structure

```text
backend/apps/core/
  models.py              # Company e User
  serializers.py         # Registro, login e respostas públicas
  permissions.py         # Permissões e helpers de tenant
  services.py            # Registro transacional
  urls.py                # Rotas /api/auth/
backend/config/settings.py  # AUTH_USER_MODEL, JWT e hashing
backend/tests/unit/core/
backend/tests/integration/test_identity_tenant.py
```

## Code Style

- Serviços de domínio não retornam respostas HTTP.
- Views validam entrada e delegam ao serviço.
- Queries dependentes de tenant partem de `request.user.company`.
- IDs internos são UUID; JSON público usa `camelCase`.

```python
def visible_tenders(user):
    return Tender.objects.filter(company_id=user.company_id)
```

Não criar um helper que aceite `company_id` arbitrário para substituir essa regra.

## Testing Strategy

Unitários:

- Normalização e validação de email.
- Geração de slug.
- Serviço de registro atômico.
- Regras de role e usuário inativo.

Integração:

- Registro, login, refresh e `/me/`.
- Expiração e invalidação de tokens.
- Rotação, revogação, expiração e reuse detection do refresh token.
- CSRF e origem permitida no endpoint de refresh.
- Respostas `401`, `409` e `422` no envelope padrão.
- Isolamento entre duas empresas em pelo menos um recurso dependente.
- Ausência de credenciais em logs e erros.

## Boundaries

- **Always:** derivar o tenant do usuário autenticado, usar transação no registro, validar payload na API, usar hasher do Django, aplicar o envelope de erro e executar os testes do módulo.
- **Ask first:** trocar o identificador de login, alterar o escopo de unicidade do email, adicionar role, mudar algoritmo/claims JWT ou aceitar login social.
- **Never:** aceitar `companyId` do cliente como autoridade, armazenar senha em texto puro, registrar tokens, desabilitar autenticação para facilitar testes ou remover o teste cross-tenant.

## Success Criteria

- Um novo usuário conclui registro e login via API em uma execução limpa.
- A resposta de `/me/` identifica o mesmo usuário e empresa criados.
- Dois tenants com editais distintos permanecem isolados em consultas e mutations.
- Todos os testes do módulo passam com banco PostgreSQL do Compose.
- Nenhuma credencial aparece no banco em formato reversível, nos logs ou nos payloads de erro.

## Dependencies

- `django.contrib.auth`, `rest_framework`, `rest_framework_simplejwt`.
- PostgreSQL para UUIDs, constraints e transações.
- Os módulos `tender-management`, `document-pipeline` e demais consumidores dependem de `request.user.company`.

## Open Questions

- O email continuará único globalmente se o produto futuramente permitir o mesmo usuário em várias empresas?

## Verification

```text
docker compose exec api pytest backend/tests/unit/core backend/tests/integration/test_identity_tenant.py
```
