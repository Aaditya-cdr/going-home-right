import type { Metadata } from "next";
import "./style.css";

export const metadata: Metadata = { title: "AAYU | Going Home Right", description: "A source-linked synthetic discharge care demo." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
