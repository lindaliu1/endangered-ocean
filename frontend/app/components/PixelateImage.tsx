"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
	src: string;
	alt: string;
	pixelSize?: number;
	width?: number;
	height?: number;
	className?: string;
};

export default function PixelateImage({
	src,
	alt,
	pixelSize = 2,
	width = 80,
	height = 80,
	className,
}: Props) {
	const canvasRef = useRef<HTMLCanvasElement | null>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let cancelled = false;
		setError(null);

		const canvas = canvasRef.current;
		if (!canvas) return;

		const ctx = canvas.getContext("2d");
		if (!ctx) {
			setError("canvas not supported");
			return;
		}

		const img = new Image();
		img.crossOrigin = "anonymous";

		img.onload = () => {
			if (cancelled) return;

			canvas.width = width;
			canvas.height = height;

			// Draw to a tiny offscreen canvas then scale up without smoothing.
			const w = width;
			const h = height;
			const px = Math.max(1, Math.floor(pixelSize));
			const tinyW = Math.max(1, Math.floor(w / px));
			const tinyH = Math.max(1, Math.floor(h / px));

			const off = document.createElement("canvas");
			off.width = tinyW;
			off.height = tinyH;
			const offCtx = off.getContext("2d");
			if (!offCtx) {
				setError("canvas not supported");
				return;
			}

			offCtx.clearRect(0, 0, tinyW, tinyH);
			offCtx.imageSmoothingEnabled = true;
			offCtx.drawImage(img, 0, 0, tinyW, tinyH);

			ctx.clearRect(0, 0, w, h);
			(ctx as any).imageSmoothingEnabled = false;
			// Some browsers use vendor-prefixed flags
			(ctx as any).mozImageSmoothingEnabled = false;
			(ctx as any).webkitImageSmoothingEnabled = false;
			(ctx as any).msImageSmoothingEnabled = false;

			ctx.drawImage(off, 0, 0, tinyW, tinyH, 0, 0, w, h);
		};

		img.onerror = () => {
			if (cancelled) return;
			setError("image failed to load");
		};

		img.src = src;

		return () => {
			cancelled = true;
		};
	}, [src, pixelSize, width, height]);

	if (error) {
		return (
			<div
				className={
					className ??
					"flex items-center justify-center rounded bg-zinc-100 text-xs text-zinc-600"
				}
				style={{ width, height }}
				aria-label={alt}
			>
				(image)
			</div>
		);
	}

	return (
		<canvas
			ref={canvasRef}
			className={className}
			style={{ width, height }}
			role="img"
			aria-label={alt}
		/>
	);
}
