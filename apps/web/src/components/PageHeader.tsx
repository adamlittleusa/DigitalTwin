import Link from "next/link";

interface PageHeaderProps {
  eyebrow?: string;
  eyebrowHref?: string;
  title: string;
  lede?: string;
}

export function PageHeader({ eyebrow, eyebrowHref, title, lede }: PageHeaderProps) {
  return (
    <div className="page-header">
      {eyebrow ? (
        <p className="mono page-header__eyebrow">
          {eyebrowHref ? <Link href={eyebrowHref}>{eyebrow}</Link> : eyebrow}
        </p>
      ) : null}
      <h1 className="page-header__title">{title}</h1>
      {lede ? <p className="page-header__lede">{lede}</p> : null}
    </div>
  );
}
