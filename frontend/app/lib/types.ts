export type SpeciesOut = {
	id: number;
	source: string;
	source_record_id: string;
	detail_url?: string | null;
	common_name: string;
	scientific_name: string;
	status: string;
	image_url: string;
	min_depth_m?: number | null;
	max_depth_m?: number | null;
	threats: string[];
};

export type ThreatOut = {
	id: number;
	name: string;
};
