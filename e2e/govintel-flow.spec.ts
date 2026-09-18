import { expect, test } from "@playwright/test";

/**
 * Fluxo ponta a ponta da demo:
 * cadastro → upload de PDF → processamento assíncrono → busca semântica → chat com citações.
 *
 * Pré-requisitos: `docker compose up -d --build` com api/worker/frontend saudáveis.
 * Provider de IA deve ser mockado no CI (GEMINI_API_KEY ausente ou "mock").
 */

const FIXTURE_PATH = "./e2e/fixtures/edital-demo.pdf";

function uniqueEmail(prefix = "e2e") {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@teste.com`;
}

test("register keeps CSRF working on local hosts", async ({
  page,
}) => {
  await page.goto("/register");
  await page.fill("#register-company", "Empresa CSRF Teste");
  await page.fill("#register-email", uniqueEmail("csrf"));
  await page.fill("#register-password", "x");

  const responsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/auth/register/"),
  );
  await page.click("button[type=submit]");
  const response = await responsePromise;

  // A 400 confirma que o pedido chegou ao serializer; 403 indicaria falha CSRF.
  expect(response.status()).toBe(400);
});

test("login keeps CSRF working on local hosts", async ({
  page,
}) => {
  await page.goto("/login");
  await page.fill("#login-email", uniqueEmail("csrf-login"));
  await page.fill("#login-password", "Password123!");

  const responsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/auth/token/"),
  );
  await page.click("button[type=submit]");
  const response = await responsePromise;

  // Credenciais inexistentes geram 401; 403 apontaria para quebra do CSRF.
  expect(response.status()).toBe(401);
});

test("govintel demo flow: register, upload, process, search and chat", async ({
  page,
}) => {
  const email = uniqueEmail();
  const password = "Password123!";
  const companyName = `Empresa E2E ${Date.now()}`;
  const tenderTitle = "Pregão Eletrônico 001/2026";

  // 1. Cadastro -------------------------------------------------------------
  await page.goto("/register");
  await page.fill("#register-company", companyName);
  await page.fill("#register-email", email);
  await page.fill("#register-password", password);
  await page.click("button[type=submit]");

  // Deve redirecionar ao dashboard
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 20_000 });

  // 2. Upload do PDF ---------------------------------------------------------
  await page.fill("#upload-title", tenderTitle);
  await page.setInputFiles("#upload-file", FIXTURE_PATH);
  await page.click("#upload-submit-btn");

  // 3. Processamento assíncrono com polling ----------------------------------
  // O dashboard exibe o status do edital; aguardamos PROCESSED.
  await expect(page.locator("#tenders-list .tender-item").first()).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.locator("#tenders-list .tender-status--processed").first(),
  ).toBeVisible({ timeout: 120_000 });

  const tenderLink = page.locator(
    "#tenders-list .tender-item a[href^='/search']",
  );
  await expect(tenderLink.first()).toBeVisible();

  // 4. Busca semântica ---------------------------------------------------------
  // Navegação client-side via link (preserva o access token em memória).
  await tenderLink.first().click();
  await expect(page).toHaveURL(/\/search/, { timeout: 10_000 });
  await page.fill("#search-query", "prazo de entrega");
  await page.click("#search-submit-btn");

  await expect(page.locator("#search-results-list .search-result-item").first())
    .toBeVisible({ timeout: 30_000 });
  const snippet = page.locator(".search-result-snippet").first();
  await expect(snippet).toBeVisible();
  const snippetText = (await snippet.textContent()) || "";
  expect(snippetText.length).toBeGreaterThan(0);

  // 5. Chat com citações --------------------------------------------------------
  const chatLink = page.locator(
    "#search-results-list .search-result-item a[href^='/chat']",
  );
  await expect(chatLink.first()).toBeVisible();
  await chatLink.first().click();
  await expect(page).toHaveURL(/\/chat/, { timeout: 10_000 });
  await page.fill("#chat-input", "Qual o prazo de entrega?");
  await page.click("#chat-send-btn");

  // A mensagem do assistente chega com citações verificáveis
  await expect(
    page.locator("#chat-messages .chat-message--assistant").last(),
  ).toBeVisible({ timeout: 60_000 });

  // O painel de fontes exibe página e trecho citado
  const citations = page.locator("#citations-list .chat-citation-item");
  await expect(citations.first()).toBeVisible({ timeout: 20_000 });
  const pageText = await page.locator(".chat-citation-page").first().textContent();
  expect(pageText).toMatch(/Página \d+/);
  const quote = await page.locator(".chat-citation-quote").first().textContent();
  expect((quote || "").length).toBeGreaterThan(0);
});
