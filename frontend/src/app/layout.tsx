import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agente de Simulação Tributária — RTC",
  description: "Simulador determinístico CBS, IBS e Imposto Seletivo (LC 214/2025)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}