# Project brief: Milan Transportation and Health Facilities KG

Context for Claude Code. This is a university team project for the Knowledge Graphs course
(KG 2026, University of Trento, Prof. Fausto Giunchiglia, TA Mayukh Bagchi). Read this before
doing any work in this folder.

## What the project is

- Build a Knowledge Graph (KG) following the course's **iTelos** methodology.
- Topic: **4. Transportation and Health Facilities** (from the official project list).
- Approved by the TA: a single city is acceptable, as long as the spatial and temporal extent is
  clearly stated, datasets and ontologies are gathered, and Competency Questions (CQs) drive all phases.
- Team of at least 2 people (Data Scientist and Knowledge Engineer roles must be different people).
- At least **3 datasets** must be used.

## Domain of Interest (draft)

- **Spatial extent:** Municipality of Milan (Comune di Milano) only, not the Metropolitan City.
  Reason: the datasets come from the Comune di Milano portal and share the same NIL codes;
  ATM runs almost all transport inside the city.
- Milan is split into **88 NIL** (Nuclei di Identita Locale, local neighbourhoods) and **9 municipi**.
- **Temporal extent:** public transport service as of November 2026 (current ATM GTFS feed) and the
  latest available year of healthcare facility data (check the `Anno` column).
- **Focus:** public transport ACCESS to healthcare facilities (which stops and lines serve each
  facility, which neighbourhoods are poorly served). Not "transport between facilities".

## Datasets

| Dataset | Source | Format | Notes |
|---|---|---|---|
| Hospitals and case di cura, beds and disciplines (ds683) | dati.comune.milano.it, dataset `ds683-sanita-posti-letto-delle-strutture-ospedaliere-e-case-di-cura-2010-avanti`, resource `7632c319-4a2a-4ab5-a39d-74d6ecc7323d` | CSV | Columns seen in data dictionary: Codice struttura, Denominazione Struttura/Stabilimento, Descrizione tipo struttura, Descrizione disciplina, Indirizzo, CAP, MUNICIPIO, NIL, ID_NIL, LONG_X_4326, LAT_Y_4326, Location, bed counts (ordinaria, a pagamento, Day Hospital, Day Surgery, Totale), N Reparti, Anno, Codice Azienda, Tipo Azienda. Multiple years, filter to latest. Licence IODL 2.0 / CC BY. |
| Pharmacies (ds501) | dati.comune.milano.it, dataset `ds501_farmacie-nel-comune-di-milano`, resource `0c9f45b3-373e-4528-ac40-c8e474aad605` | CSV (already downloaded by the user) | WGS84 coordinates likely present (page has a map). NIL is given as TEXT, not ID: map it to ID_NIL (spatial join preferred, name normalisation as fallback). |
| ATM public transport timetable (GTFS) | dati.comune.milano.it ds929 "Orari del trasporto pubblico locale nel comune di Milano in formato GTFS"; also Mobility Database feed `mdb-2666` | ZIP of CSV .txt files | Use stops.txt, routes.txt, agency.txt; trips.txt and stop_times.txt only to compute aggregates (frequency). route_type: 0 tram, 1 metro, 3 bus. |
| NIL neighbourhoods (ds61) | dati.comune.milano.it `ds61_infogeo_nil_localizzazione_`, resource `4888f702-3b5a-4908-b80e-f51a64402936` | GeoJSON preferred | Needed for area and point-in-polygon joins. |
| Nursing homes (RSA) | NOT FOUND YET | | Keep NursingHome only if a dataset is found (Milan or Lombardy portal). |
| Population per NIL | NOT FOUND YET | | Optional, for per-resident metrics. |

The Milan portal is CKAN. Data API: `https://dati.comune.milano.it/api/3/action/datastore_search`
with `resource_id`, `limit`, `offset`. Default limit is 100 rows, so always paginate. The portal's
own Python example is Python 2; use `requests`.

## Data handling rules

- Never edit raw files. Raw data goes in `Phase 1/raw/` (dated snapshot, e.g. `pharmacies_2026-11-11.csv`),
  cleaned data in a separate `clean/` folder. All cleaning in scripts that can be rerun.
- Italian CSV quirks: separator often `;`, encoding `utf-8-sig` or `latin-1`, decimal commas.
- Drop the CKAN `_id` column.
- Log row counts before and after every cleaning step and every transformation. The report's
  Phase 1 qualitative evaluation needs "dataset-level formatting and transformations".
- Use pandas; geopandas for spatial joins and distances (project to a metric CRS such as
  EPSG:32632 before measuring distances).
- Do not model GTFS trips or stop_times as entities (millions of rows). Compute aggregates in Python
  and store them as data properties.

## Computed accessibility measures (planned)

- Per facility: distanceToNearestStop, distance to nearest metro station, linesWithin500m,
  departures per hour (weekday 07:00 to 20:00) from stops within 500 m.
- Per NIL: stopsPerKm2, departuresPerHour, whether it has a hospital.
- Thresholds (rule of thumb, cite a source in the report): ~400 to 500 m to bus/tram stop,
  ~800 m to metro. A simplified PTAL (London's Public Transport Accessibility Level) is the
  most defensible established metric.

## Entity types (draft, EER model with is-a hierarchies)

The TA confirmed the hierarchy idea and that the diagram is an **EER** model (Enhanced ER),
not a classical ER model.

Inheritance (is-a):
- HealthcareFacility -> Hospital, Pharmacy, NursingHome (disjoint; partial or total to decide)
- Stop -> BusStop, TramStop, MetroStation (probably overlapping; decide and justify)
- AdministrativeArea -> Neighbourhood (NIL), Municipio, City (disjoint, total)

Other ETypes: Route (transport mode is the attribute routeMode, not an EType), TransportOperator (ATM),
MedicalSpecialty (from "disciplina"), HealthAuthority (ASST, from Codice/Tipo Azienda).

Categories: Core = HealthcareFacility, Hospital, Pharmacy, NursingHome, Stop and subtypes, Route.
Common = City, TransportOperator, HealthAuthority. Contextual = MedicalSpecialty, Neighbourhood, Municipio.

Relationships: Hospital hasSpecialty MedicalSpecialty; Hospital managedBy HealthAuthority;
Route servesStop Stop; Route operatedBy TransportOperator; HealthcareFacility locatedIn Neighbourhood;
Stop locatedIn Neighbourhood; HealthcareFacility nearStop Stop (within 500 m, computed);
Neighbourhood partOf Municipio; Municipio partOf City.

Example CQs:
1. Which hospitals in Milan have a cardiology department, and which bus, tram or metro stops are within 500 m of each?
2. Which NIL neighbourhoods have the fewest hospital beds per resident, and which lines serve them? (needs population data)

## Ontologies provided by the course ("KG Composable Fragments")

- LTLO-KG.owl and KTLO-KG.owl: same 829-class OpenStreetMap-based hierarchy (root `openstreetmap_place`).
  LTLO = class tree (language layer, Phase 2). KTLO = same plus 16 data properties and 1 object property
  with domain and range (knowledge layer, Phase 3). osm.owl is essentially KTLO.
  IRI base: `http://www.semanticweb.org/lixiaoyue/ontologies/2023/2/untitled-ontology-26#`.
  Relevant classes: pois > health > hospital, pharmacy, clinic, doctors, dentist; public > nursing_home;
  transport > bus_stop, tram_stop, subway_station (GO_6000028), railway_station; places > city, suburb.
  Each place class has point_ and polygon_ variants.
- GTFS.n3 (`http://vocab.gtfs.org/terms#`): Stop, Station, Route, RouteType, Trip, Agency, StopTime and properties.
- schema.org fragments: Hospital, Pharmacy, MedicalClinic are only in full-schema-org.owl;
  MedicalSpecialty in intangible-schema-org.owl; AdministrativeArea, City, BusStop, SubwayStation in place-schema-org.owl.
  name, latitude, longitude, address, telephone are declared as object properties there (conversion oddity; ask TA).
- Gaps needing enrichment: Route, TransportOperator, MedicalSpecialty, NIL neighbourhood.

## iTelos phases and checkpoints

| Phase | Lecture / Q&A | Deliverable |
|---|---|---|
| 1 Purpose Definition | 11 Nov / 16 Nov | DoI, informal purpose, scenarios, personas, CQs, informal ETypes and properties (core/common/contextual), EER diagram, information gathering (KG/KnowDive vs external sources x knowledge vs data layer), qualitative evaluation (initial vs final counts), Appendix A LLM questionnaire |
| 2 Language Definition | 18 / 23 Nov | Terms aligned to LTLO, enrichment, cleaned data |
| 3 Knowledge Definition | 25 / 30 Nov | Teleology from fragments aligned to KTLO, Protege .owl |
| 4 Entity Definition | 2 / 9 Dec | Karma mappings, RDF .ttl, GraphDB |
| Evaluation + Metadata | 14 Dec | SPARQL per CQ, metrics, metadata, open issues |

Send each phase to the TA around its Q&A date. Repo structure follows the TA's template:
`Phase 1`, `Phase 2`, `Phase 3`, `Phase 4`, `Evaluation`, `Metadata`, `Documentation`.
Report written in Overleaf from the course template.

## LLM rules (course policy, mandatory)

- Allowed: code for downloading and cleaning, formatting tables, checking naming consistency,
  explaining tools, brainstorming that the team then verifies.
- Not allowed: inventing facts, data, ConceptIDs/UKC IDs/ontology links, query results or metric values;
  producing final OWL/RDF/mappings/SPARQL without the team checking them.
- The report's running text must be the team's own words (mandatory AI declaration says no
  AI-generated sentences in the submitted text). Do not write report prose for submission.
- Keep a short log of LLM use per phase for the Appendix A questionnaire.

## Writing style for anything drafted

Plain, simple English. No jargon-heavy or over-constructed sentences. Avoid unnecessary em and en dashes.

## Next steps

1. Load the pharmacy CSV: print shape, columns, missing values; confirm coordinates; map NIL text to ID_NIL.
2. Download hospitals (ds683), NIL (ds61 GeoJSON) and the ATM GTFS zip; inspect columns and years.
3. Write one cleaning script per dataset with logged row counts.
4. Draft scenarios, personas and CQs (team writes them), then check each CQ against the real columns.
