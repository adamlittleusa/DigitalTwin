import { OpenTwinButton } from "@/components/twin/OpenTwinButton";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container site-footer__row">
        <p className="mono">Adam Little · Boston</p>
        <div className="site-footer__links">
          <a
            className="mono"
            href="https://www.linkedin.com/in/adamlittleusa"
            target="_blank"
            rel="noreferrer"
          >
            LinkedIn
          </a>
          <a
            className="mono"
            href="https://github.com/adamlittleusa"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
          <OpenTwinButton className="mono">Ask the twin</OpenTwinButton>
        </div>
      </div>
    </footer>
  );
}
