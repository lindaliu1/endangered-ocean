# Our Endangered Oceans

An interactive visualization displaying endangered ocean species data sourced from the NOAA species directory.

Data source: https://www.fisheries.noaa.gov/species-directory

## Running Locally

### 0. Required installations: 
- Docker Desktop
- Python 3.12+
- Node.js 18+

### 1. Starting Postgres

In repo root, run the following:

```bash
docker compose up -d {POSTGRES_SERVICE_NAME}
```

Check it’s running:
```bash
docker compose ps
```

### 2. Configuring backend environment

Set the `DATABASE_URL` environment variable. If all compose values are default (as set in docker-compose.yml), use: 

```bash
export DATABASE_URL="postgresql://ocean:ocean@127.0.0.1:5432/ocean_db"
```

### 3. Creating tables

From the repo root, run the following:

```bash
python backend/create_tables.py
``` 

Sanity checks:
```bash
python backend/smoke_test_db.py
```

### 4. Loading NOAA data via pipeline

From the repo root, you can run the following:

#### To load data: 
```bash
python pipeline/run_pipeline.py --load
```

#### To just run the scraper: 
```bash
python pipeline/run_pipeline.py
```

#### To run each pipeline step manually, run the following:

a. Scrape directory list
```bash
python pipeline/scrape_noaa_list.py
```

b. Scrape species details pages:
```bash
python pipeline/scrape_noaa_details.py
```

c. Load data into Postgres:
```bash
python backend/load_to_db.py
```

### 5. Running the backend (FastAPI)

From the repo root, run the following:

```bash
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

Sanity checks: 
- Health: `http://127.0.0.1:8000/api/health`
- Species: `http://127.0.0.1:8000/api/species?limit=5`

### 6. Running the frontend (Next.js)

From the repo root, run the following:

```bash
cd frontend
npm install
npm run dev
```

Open: `http://localhost:3000`

### 7. Additional notes

- Images scraped from NOAA site are transformed vis the backend to remove backgroun using the `rembg` package. This may be slow when run the first time, but subsequent requests will be cached in `backend/.cache/` to speed up subsequent requests.