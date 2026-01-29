"use client";

import { useEffect, useMemo, useState } from "react";

import { apiFetch, bgRemovedImageUrl } from "../lib/api";
import type { SpeciesOut, ThreatOut } from "../lib/types";
import PixelateImage from "./PixelateImage";

// px per meter for positioning animals vertically
const PX_PER_M = 7;
const HEADER_SPACE_PX = 300;
// smaller pad before 0m starts inside the ocean.
const OCEAN_TOP_PADDING_PX = 20;

// Layout tuning to reduce overlap
const LANES = 9; // more lanes across the screen
const LANE_WIDTH_PX = 150; // slightly tighter lane width
const LEFT_MARGIN_PX = 120; // left padding from the depth axis
const BUCKET_M = 50; // finer buckets for crowded shallow depths
const ROW_GAP_PX = 90; // more vertical spacing when a bucket is crowded

// In very shallow water, crowding is worst. Add extra vertical spacing there.
const SHALLOW_M = 120;
const SHALLOW_ROW_GAP_PX = 90;

type Props = {
	initialSpecies: SpeciesOut[];
};

type StatusFilter = "" | "Endangered" | "Threatened";

type LoadState = {
	loading: boolean;
	error: string | null;
};

export default function SpeciesFiltersPage({ initialSpecies }: Props) {
	const [status, setStatus] = useState<StatusFilter>("");
	const [threat, setThreat] = useState<string>("");
	const [threatOptions, setThreatOptions] = useState<ThreatOut[]>([]);

	const [species, setSpecies] = useState<SpeciesOut[]>(initialSpecies);
	const [state, setState] = useState<LoadState>({
		loading: false,
		error: null,
	});

	// fetch threat options once.
	useEffect(() => {
		let cancelled = false;

		(async () => {
			try {
				const resp = await apiFetch("/api/threats");
				if (!resp.ok) throw new Error(String(resp.status));
				const data = (await resp.json()) as ThreatOut[];
				if (!cancelled) setThreatOptions(data);
			} catch {
				// non-fatal; filters still work if user types a threat manually later.
				if (!cancelled) setThreatOptions([]);
			}
		})();

		return () => {
			cancelled = true;
		};
	}, []);

	// refetch species when filters change.
	useEffect(() => {
		let cancelled = false;

		(async () => {
			setState({ loading: true, error: null });
			try {
				const resp = await apiFetch(
					"/api/species",
					{},
					{
						limit: 200,
						offset: 0,
						status: status || null,
						threat: threat || null,
					},
				);
				if (!resp.ok) {
					throw new Error(`API error: ${resp.status}`);
				}
				const data = (await resp.json()) as SpeciesOut[];
				if (!cancelled) setSpecies(data);
				if (!cancelled) setState({ loading: false, error: null });
			} catch (e) {
				if (!cancelled)
					setState({
						loading: false,
						error: e instanceof Error ? e.message : "Failed to load species",
					});
			}
		})();

		return () => {
			cancelled = true;
		};
	}, [status, threat]);

	const speciesWithDepth = useMemo(
		() => species.filter((s) => s.min_depth_m != null || s.max_depth_m != null),
		[species],
	);

	const positioned = useMemo(() => {
		// Keep only species with BOTH bounds so the midpoint anchorDepthM is defined.
		const base = speciesWithDepth
			.filter((s) => s.min_depth_m != null && s.max_depth_m != null)
			.map((s) => {
				const min = s.min_depth_m as number;
				const max = s.max_depth_m as number;
				const anchorDepthM = Math.floor((min + max) / 2);
				return { s, anchorDepthM };
			})
			.sort((a, b) => a.anchorDepthM - b.anchorDepthM);

		// Group into depth buckets so placement is "in the ballpark".
		const buckets = new Map<number, typeof base>();
		for (const item of base) {
			const bucketM = Math.round(item.anchorDepthM / BUCKET_M) * BUCKET_M;
			const arr = buckets.get(bucketM) ?? [];
			arr.push(item);
			buckets.set(bucketM, arr);
		}

		// Assign lanes + stagger within each bucket to avoid overlap.
		const out: Array<{
			s: SpeciesOut;
			anchorDepthM: number;
			bucketM: number;
			topPx: number;
			leftPx: number;
		}> = [];

		const sortedBuckets = Array.from(buckets.keys()).sort((a, b) => a - b);
		for (const bucketM of sortedBuckets) {
			const items = buckets.get(bucketM) ?? [];

			// Use larger row gap near the surface.
			const rowGapPx = bucketM <= SHALLOW_M ? SHALLOW_ROW_GAP_PX : ROW_GAP_PX;

			for (let i = 0; i < items.length; i++) {
				const { s, anchorDepthM } = items[i];

				// Spread items across lanes, then wrap.
				const lane = i % LANES;

				// If more than LANES items in the same bucket, push additional rows down.
				const row = Math.floor(i / LANES);

				const leftPx = LEFT_MARGIN_PX + lane * LANE_WIDTH_PX;
				// Start 0m close to the top of the ocean, NOT below the full header height.
				const topPx =
					OCEAN_TOP_PADDING_PX + bucketM * PX_PER_M + row * rowGapPx;

				out.push({ s, anchorDepthM, bucketM, topPx, leftPx });
			}
		}

		return out;
	}, [speciesWithDepth]);

	const maxAnchorDepthM = useMemo(() => {
		let max = 0;
		for (const p of positioned) {
			if (p.anchorDepthM > max) max = p.anchorDepthM;
		}
		return max;
	}, [positioned]);

	const oceanHeightPx = useMemo(() => {
		// add a little bottom padding so last card isn't flush with the edge
		return Math.max(800, (maxAnchorDepthM + 50) * PX_PER_M);
	}, [maxAnchorDepthM]);

	const depthTicks = useMemo(() => {
		const ticks: number[] = [];
		const stepM = 100;
		const maxM = Math.ceil(maxAnchorDepthM / stepM) * stepM;
		for (let d = 0; d <= maxM; d += stepM) ticks.push(d);
		return ticks;
	}, [maxAnchorDepthM]);

	return (
		<div className="min-h-screen bg-zinc-50 font-sans text-zinc-900">
			<main className="w-full">
				{/* header area (fixed-height spacer for title/description/filters) */}
				<div
					className="w-full"
					style={{
						height: HEADER_SPACE_PX,
						background: "rgb(190, 218, 255)",
					}}
				>
					<div className="mx-auto w-full max-w-5xl px-6 pt-10 ml-9">
						<div className="mb-4">
							<h1 className="text-3xl font-semibold tracking-tight">
								our endangered oceans
							</h1>
							<p className="mt-2 text-sm text-zinc-600 max-w-2xl">
								dive down and explore the depths where endangered and threatened
								marine species live. filter by status or threat discover what
								endangers our aquatic friends.
							</p>
						</div>

						{/* match filters width to the paragraph above (max-w-2xl) */}
						<div className="max-w-2xl">
							<div className="grid grid-cols-1 gap-3 rounded-lg border border-zinc-200 bg-white/40 p-4 sm:grid-cols-2">
								<label className="flex flex-col gap-1 text-sm">
									<span className="text-xs font-medium text-zinc-700">
										status
									</span>
									<select
										className="h-10 rounded border border-zinc-200 bg-white px-3"
										value={status}
										onChange={(e) => setStatus(e.target.value as StatusFilter)}
									>
										<option value="">all</option>
										<option value="Endangered">endangered</option>
										<option value="Threatened">threatened</option>
									</select>
								</label>

								<label className="flex flex-col gap-1 text-sm sm:col-span-2">
									<span className="text-xs font-medium text-zinc-700">
										threat
									</span>
									<select
										className="h-10 rounded border border-zinc-200 bg-white px-3"
										value={threat}
										onChange={(e) => setThreat(e.target.value)}
									>
										<option value="">all</option>
										{threatOptions.map((t) => (
											<option key={t.id} value={t.name}>
												{t.name}
											</option>
										))}
									</select>
								</label>

								<div className="text-xs text-zinc-600 sm:col-span-3">
									{state.loading ? (
										<span>Loading…</span>
									) : state.error ? (
										<span className="text-red-700">{state.error}</span>
									) : (
										<span>
											<span className="font-medium">{positioned.length}</span>{" "}
											species displayed
										</span>
									)}
								</div>
							</div>
						</div>
					</div>
				</div>

				{/* full-width ocean area; page scrolls */}
				{positioned.length === 0 ? (
					<div className="mx-auto w-full max-w-5xl px-6 pb-12">
						<div className="rounded border border-zinc-200 bg-white p-4 text-sm text-zinc-700">
							no species meet the filter requirements!
						</div>
					</div>
				) : (
					<div
						className="relative w-full ocean"
						style={{
							height: oceanHeightPx + OCEAN_TOP_PADDING_PX,
							backgroundRepeat: "no-repeat",
							background:
								"linear-gradient(to bottom,rgb(103, 160, 234) 0px,rgb(29, 76, 134) 1400px,rgb(10, 25, 66) 4900px,rgb(4, 6, 12) 7000px)",
						}}
					>
						{/* depth axis */}
						<div
							className="pointer-events-none absolute left-0 top-0 h-full w-20 border-r border-white/20 bg-white/5 backdrop-blur"
							style={{ paddingTop: OCEAN_TOP_PADDING_PX }}
						>
							{depthTicks.map((d) => (
								<div
									key={d}
									className="absolute left-0 w-full"
									style={{ top: OCEAN_TOP_PADDING_PX + d * PX_PER_M }}
								>
									<div className="flex items-center gap-2 pl-3">
										<div className="h-px w-4 bg-white/40" />
										<div className="text-[10px] text-white/70 tabular-nums">
											{d}m
										</div>
									</div>
								</div>
							))}
						</div>

						{/* species photo */}
						{positioned.slice(0, 180).map(({ s, topPx, leftPx }, idx) => {
							return (
								<div
									key={s.id}
									className="absolute flex flex-col items-center"
									style={{ top: topPx, left: leftPx }}
								>
									<PixelateImage
										src={bgRemovedImageUrl(s.image_url)}
										alt={s.common_name}
										width={80}
										height={80}
										pixelSize={2}
										className="rounded"
									/>
								</div>
							);
						})}
					</div>
				)}
			</main>
		</div>
	);
}
