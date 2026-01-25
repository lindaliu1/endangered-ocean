import json
from pathlib import Path

IN_PATH = Path("pipeline/out/noaa_details.json")
OUT_PATH = Path("pipeline/out/threats.json")
OUT_PATH_NORMALIZED = Path("pipeline/out/normalized_threats.json")

# json file w only threats for analysis + normalization
def isolate_threats():
    with IN_PATH.open("r", encoding="utf-8") as f:
        species_data = json.load(f)

    threats_list = []
    seen = {}
    for item in species_data:
        threats = item.get("threats", [])
        if threats:
            for threat in threats:
                threat = threat.lower().strip()
                if threat not in seen:
                    seen[threat] = seen.get(threat, 0) + 1
                else:
                    seen[threat] += 1

    for threat, count in seen.items():
        threats_list.append({
            "threat": threat,
            "count": count
        })

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(threats_list, f, indent=2)

def extract_normalized_threats():
    with IN_PATH.open("r", encoding="utf-8") as f:
        species_data = json.load(f)

    '''keywords for each normalized category'''
    #climate change
    cc_keywords = [
        "climate change",
        "ocean acidification",
        "ocean warming",
        "sea level rise",
        "temperatures",
    ]

    # disease
    disease_keywords = [
        "disease",
        "diseases",
    ]
    
    # fishing
    fishing_keywords = [
        "fishing",
        "bycatch",
        "overfishing",
        "fisheries",
        "entanglement",
        "vessel",
        "vessel-based",
        "harvest",
        "overharvest",
    ]

    # habitat loss
    habitat_keywords = [
        "habitat",
        "habitats",
        "dredging",
        "habitat",
    ]

    # oil and general pollution
    pollution_keywords = [
        "oil",
        "spill",
        "gas",
        "pollution",
        "pollutants",
        "contaminants",
        "toxic",
        "toxins",
        "debris",
    ]

    # predation
    predation_keywords = [
        "predation",
        "predators",
        "harassment",
    ]

    # low population
    population_keywords = [
        "population",
    ]

    normalized_threats = []
    for item in species_data:
        threats = item.get("threats", [])
        if threats:
            normalized_threat_list = []
            seen = set()
            for threat in threats:
                threat_lower = threat.lower()
                if any(keyword in threat_lower for keyword in cc_keywords):
                    seen.add("climate change")
                elif any(keyword in threat_lower for keyword in disease_keywords):
                    seen.add("disease")
                elif any(keyword in threat_lower for keyword in fishing_keywords):
                    seen.add("fishing")
                elif any(keyword in threat_lower for keyword in habitat_keywords):
                    seen.add("habitat loss")
                elif any(keyword in threat_lower for keyword in pollution_keywords):
                    seen.add("pollution")
                elif any(keyword in threat_lower for keyword in predation_keywords):
                    seen.add("predation")
                elif any(keyword in threat_lower for keyword in population_keywords):
                    seen.add("low population")
            for n_threat in seen:
                normalized_threat_list.append(n_threat)

            normalized_threats.append({
                "threats": threats,
                "normalized": normalized_threat_list
            })
    
    with OUT_PATH_NORMALIZED.open("w", encoding="utf-8") as f:
        json.dump(normalized_threats, f, indent=2)
        

if __name__ == "__main__":
    isolate_threats()
    extract_normalized_threats()
    print(f"Wrote threats to {OUT_PATH}")
    print(f"Wrote normalized threats to {OUT_PATH_NORMALIZED}")