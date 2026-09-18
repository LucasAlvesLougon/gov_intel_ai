"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { authStore } from "../../lib/auth";
import { ApiClientError } from "../../lib/http";
import { ProductBrand } from "../../components/product-brand";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await authStore.login({ email, password });
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError(
          "Não foi possível realizar o login. Verifique suas credenciais.",
        );
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <header>
        <ProductBrand href="/" />
        <div className="nav-links">
          <Link href="/register" className="btn-nav">
            Criar conta
          </Link>
        </div>
      </header>

      <div className="auth-container">
        <section className="auth-card" aria-labelledby="login-title">
          <p className="eyebrow">ACESSO AO SISTEMA</p>
          <h1 id="login-title">Entrar na plataforma</h1>
          <p className="intro">
            Acesse o ambiente da sua empresa para gerenciar editais e realizar
            consultas inteligentes.
          </p>

          {error && (
            <div className="alert-error" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate={false}>
            <div className="form-group">
              <label htmlFor="login-email">Email corporativo</label>
              <input
                id="login-email"
                name="email"
                type="email"
                required
                autoComplete="email"
                placeholder="seu.email@empresa.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="login-password">Senha</label>
              <input
                id="login-password"
                name="password"
                type="password"
                required
                autoComplete="current-password"
                placeholder="Sua senha de acesso"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
              />
            </div>

            <button type="submit" className="btn-primary" disabled={isLoading}>
              {isLoading ? "Entrando..." : "Entrar"}
            </button>
          </form>

          <div className="auth-links">
            Não tem uma conta? <Link href="/register">Cadastre-se</Link>
          </div>
        </section>
      </div>

      <footer>GovIntel AI · Projeto demonstrativo</footer>
    </main>
  );
}
