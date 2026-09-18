"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { authStore } from "../../lib/auth";
import { ApiClientError } from "../../lib/http";
import { ProductBrand } from "../../components/product-brand";

export default function RegisterPage() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await authStore.register({ companyName, email, password });
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError("Não foi possível concluir o cadastro. Tente novamente.");
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
          <Link href="/login" className="btn-nav">
            Entrar
          </Link>
        </div>
      </header>

      <div className="auth-container">
        <section className="auth-card" aria-labelledby="register-title">
          <p className="eyebrow">CADASTRO DE EMPRESA</p>
          <h1 id="register-title">Criar nova conta</h1>
          <p className="intro">
            Cadastre sua empresa para analisar editais públicos com inteligência
            artificial e citações verificáveis.
          </p>

          {error && (
            <div className="alert-error" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate={false}>
            <div className="form-group">
              <label htmlFor="register-company">Nome da Empresa</label>
              <input
                id="register-company"
                name="companyName"
                type="text"
                required
                autoComplete="organization"
                placeholder="Ex.: LicitAção Consultoria Ltda"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                disabled={isLoading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="register-email">Email corporativo</label>
              <input
                id="register-email"
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
              <label htmlFor="register-password">Senha</label>
              <input
                id="register-password"
                name="password"
                type="password"
                required
                autoComplete="new-password"
                placeholder="Mínimo de 8 caracteres"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
              />
            </div>

            <button type="submit" className="btn-primary" disabled={isLoading}>
              {isLoading ? "Criando conta..." : "Criar conta"}
            </button>
          </form>

          <div className="auth-links">
            Já tem uma conta? <Link href="/login">Entrar</Link>
          </div>
        </section>
      </div>

      <footer>GovIntel AI · Projeto demonstrativo</footer>
    </main>
  );
}
