import type { Metadata } from "next";
import { Ubuntu_Mono } from "next/font/google";
import "./globals.css";

const ubuntuMono = Ubuntu_Mono({
	weight: "400",
});

export const metadata: Metadata = {
	title: "Our Endangered Oceans",
	description: "Explore the ocean and its endangered species.",
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="en">
			<body className={ubuntuMono.className}>{children}</body>
		</html>
	);
}
