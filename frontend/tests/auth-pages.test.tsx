import { describe, expect, it, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// Mock next/link
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => React.createElement("a", { href, ...props }, children),
}));

describe("Auth Pages Rendering and Accessibility (Task 24)", () => {
  it("renders accessible login form with labels, inputs and submit button", async () => {
    const { default: LoginPage } = await import("../app/login/page");
    const html = renderToString(React.createElement(LoginPage));

    // Header / Brand
    expect(html).toContain("GovIntel AI");
    expect(html).toContain("Entrar na plataforma");

    // Accessible labels linked to inputs by id
    expect(html).toContain('for="login-email"');
    expect(html).toContain('id="login-email"');
    expect(html).toContain('type="email"');

    expect(html).toContain('for="login-password"');
    expect(html).toContain('id="login-password"');
    expect(html).toContain('type="password"');

    // Submit button
    expect(html).toContain('type="submit"');
    expect(html).toContain("Entrar");

    // Link to register
    expect(html).toContain('href="/register"');
    expect(html).toContain("Cadastre-se");
  });

  it("renders accessible register form with company, email, password and submit button", async () => {
    const { default: RegisterPage } = await import("../app/register/page");
    const html = renderToString(React.createElement(RegisterPage));

    // Header / Brand
    expect(html).toContain("GovIntel AI");
    expect(html).toContain("Criar nova conta");

    // Accessible labels linked to inputs by id
    expect(html).toContain('for="register-company"');
    expect(html).toContain('id="register-company"');

    expect(html).toContain('for="register-email"');
    expect(html).toContain('id="register-email"');
    expect(html).toContain('type="email"');

    expect(html).toContain('for="register-password"');
    expect(html).toContain('id="register-password"');
    expect(html).toContain('type="password"');

    // Submit button
    expect(html).toContain('type="submit"');
    expect(html).toContain("Criar conta");

    // Link to login
    expect(html).toContain('href="/login"');
    expect(html).toContain("Entrar");
  });
});
