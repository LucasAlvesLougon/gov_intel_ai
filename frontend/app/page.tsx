import Link from "next/link";
import { ProductBrand } from "../components/product-brand";

export default function Home() {
  return (
    <main className="home-page">
      <header>
        <ProductBrand />
        <nav className="nav-links" aria-label="Navegação principal">
          <Link href="/login">Entrar</Link>
          <Link href="/register" className="btn-nav">
            Criar conta
          </Link>
        </nav>
      </header>
      <section aria-labelledby="page-title">
        <p className="eyebrow">INTELIGÊNCIA DOCUMENTAL</p>
        <h1 id="page-title">Do edital à evidência.</h1>
        <p className="intro">
          Um espaço para organizar editais públicos, pesquisar seu conteúdo e
          consultar respostas acompanhadas de fontes verificáveis.
        </p>
        <div className="notice">
          <h2>Preparando o ambiente</h2>
          <p>
            A plataforma está em construção. Cadastro, envio de documentos,
            busca e conversa serão disponibilizados após a validação de cada
            etapa.
          </p>
        </div>
      </section>
      <footer>GovIntel AI · Projeto demonstrativo</footer>
    </main>
  );
}
