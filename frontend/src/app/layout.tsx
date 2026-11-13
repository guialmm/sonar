import type { Metadata } from "next";
import { Bricolage_Grotesque, DM_Sans } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const dmSans = DM_Sans({ variable: "--font-dm-sans", subsets: ["latin"] });
const bricolage = Bricolage_Grotesque({ variable: "--font-bricolage", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Sonar · vagas que encaixam no seu currículo",
  description:
    "Mande o currículo e veja as vagas de tecnologia que encaixam, com os motivos citados e o alerta de vaga fantasma.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${dmSans.variable} ${bricolage.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <header className="border-b border-linha">
          <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-6 px-5 py-4 sm:px-12">
            <Link href="/" className="flex items-center gap-2.5 font-display text-2xl font-bold tracking-tight">
              <span className="relative size-[22px] rounded-full border-2 border-verde">
                <span className="absolute inset-[4px] rounded-full bg-verde" />
              </span>
              Sonar
            </Link>
            <a href="https://github.com/guialmm/sonar" className="text-sm text-apagado transition-colors hover:text-tinta">
              Como funciona
            </a>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="mx-auto w-full max-w-[1440px] px-5 py-8 text-xs leading-relaxed text-apagado sm:px-12">
          Vagas da Gupy, das comunidades do GitHub e das páginas de carreira das empresas. O currículo é lido e descartado: nada
          fica guardado. Projeto de portfólio.
        </footer>
      </body>
    </html>
  );
}
