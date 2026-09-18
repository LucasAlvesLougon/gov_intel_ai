import Link from "next/link";

interface ProductBrandProps {
  href?: string;
}

/** Shared wordmark used by public entry points and authenticated shells. */
export function ProductBrand({ href }: ProductBrandProps) {
  const content = (
    <>
      <span aria-hidden="true" className="brand-symbol" />
      <span>GovIntel AI</span>
    </>
  );

  return href ? (
    <Link href={href} className="brand">
      {content}
    </Link>
  ) : (
    <span className="brand">{content}</span>
  );
}
