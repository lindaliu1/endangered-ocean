import { apiFetch } from "./lib/api";
import type { SpeciesOut } from "./lib/types";
import SpeciesFiltersPage from "./components/SpeciesFiltersPage";

export default async function Home() {
	let species: SpeciesOut[] = [];

	try {
		const resp = await apiFetch("/api/species", {}, { limit: 200, offset: 0 });
		if (resp.ok) {
			species = (await resp.json()) as SpeciesOut[];
		}
	} catch {
		// Filters client component will show an error on refetch if API isn't reachable.
	}

	return <SpeciesFiltersPage initialSpecies={species} />;
}
