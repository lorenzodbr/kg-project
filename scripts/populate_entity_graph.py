"""Populate the Milan Transportation and Health Facilities Entity Graph.

This script produces the Entity Definition artifacts from the translated
source CSV files and ATM GTFS tables:

* Phase 4/mappings.json
* Phase 4/entity_graph.ttl
* Phase 4/entity_validation.json

The Entity Graph is written as Turtle without RDF libraries. Source values
are preserved and URI identifiers are generated with a local project base.
No route-stop relationship is inferred because stop_times.txt is absent.
"""

import csv
import json
import math
from pathlib import Path
from urllib.parse import quote


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "Datasets"
PHASE4_DIR = PROJECT_DIR / "Phase 4 - Entity Definition"
BASE = "http://example.org/milan-health-mobility/"


def read_csv(path, delimiter=","):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def iri(kind, identifier=None):
    if identifier is None:
        return BASE + quote(kind, safe="")
    identifier = str(identifier).strip()
    return BASE + quote(kind, safe="") + "/" + quote(identifier, safe="-._~")


def literal(value):
    if value is None:
        return '""'
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace(
        "\n", "\\n"
    ) + '"'


def typed(value, datatype="xsd:string"):
    if not str(value).strip():
        return None
    return literal(str(value).strip()) + "^^" + datatype


def decimal(value):
    try:
        number = float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return None
    if not math.isfinite(number):
        return None
    return f'"{number:.6f}"^^xsd:decimal'


def integer(value):
    try:
        return f'"{int(float(str(value).replace(",", ".")))}"^^xsd:integer'
    except (ValueError, TypeError):
        return None


def point_in_polygon(longitude, latitude, polygon):
    inside = False
    if len(polygon) == 0:
        return False
    ring = polygon[0]
    for index in range(len(ring)):
        x1, y1 = ring[index]
        x2, y2 = ring[(index + 1) % len(ring)]
        if (y1 > latitude) != (y2 > latitude):
            intersection_x = x1 + (latitude - y1) * (x2 - x1) / (y2 - y1)
            if longitude < intersection_x:
                inside = not inside
    return inside


def polygon_contains(polygon, longitude, latitude):
    if not polygon:
        return False
    geometry_type = polygon.get("type")
    coordinates = polygon.get("coordinates")
    if geometry_type == "Polygon":
        return point_in_polygon(longitude, latitude, coordinates)
    if geometry_type == "MultiPolygon":
        return any(point_in_polygon(longitude, latitude, poly) for poly in coordinates)
    return False


def add_triple(triples, subject, predicate, value):
    if subject is not None and predicate is not None and value is not None:
        triples.add((subject, predicate, value))


def source_mappings():
    return [
        {
            "source": "beds_translated.csv",
            "target_entity": "Hospital",
            "identifier": ["facility_code", "facility_subcode"],
            "data_properties": [
                "facilityName", "address", "postcode", "municipio", "nilId",
                "nilName", "latitude", "longitude", "facilityType",
                "year", "numWards", "bedsOrdinaryStay", "bedsPayingStay",
                "bedsDayHospital", "bedsDaySurgery", "bedsTotal"
            ],
            "object_properties": ["locatedIn", "managedBy", "hasSpecialty"],
        },
        {
            "source": "Pharmacy_translated.csv",
            "target_entity": "Pharmacy",
            "identifier": ["pharmacy_code"],
            "data_properties": ["pharmacyName", "address", "postcode", "municipio", "nilId", "nilName", "latitude", "longitude"],
            "object_properties": ["locatedIn"],
        },
        {
            "source": "PublicHealthCentres_translated.csv",
            "target_entity": "PublicHealthCentre",
            "identifier": ["facility_code"],
            "data_properties": ["facilityName", "address", "postcode", "municipio", "nilId", "nilName", "latitude", "longitude"],
            "object_properties": ["locatedIn"],
        },
        {
            "source": "rsa_translated.csv",
            "target_entity": "NursingHome",
            "identifier": ["facility_code"],
            "data_properties": ["facilityName", "address", "postcode", "municipio", "nilId", "nilName", "latitude", "longitude", "authorisedPlaces", "accreditedNonContractedPlaces"],
            "object_properties": ["locatedIn"],
        },
        {
            "source": "NIL.csv",
            "target_entity": "Neighbourhood",
            "identifier": ["ID_NIL"],
            "data_properties": ["nilName", "shapeLength", "shapeArea"],
            "object_properties": ["partOf"],
        },
        {
            "source": "agency.txt",
            "target_entity": "TransportOperator",
            "identifier": ["agency_id"],
            "data_properties": ["agencyName", "agencyURL", "agencyTimezone"],
            "object_properties": [],
        },
        {
            "source": "routes.txt",
            "target_entity": "Route",
            "identifier": ["route_id"],
            "data_properties": ["routeShortName", "routeLongName", "routeType", "routeColor"],
            "object_properties": ["operatedBy"],
        },
        {
            "source": "stops.txt",
            "target_entity": "Stop",
            "identifier": ["stop_id"],
            "data_properties": ["stopName", "stopCode", "latitude", "longitude", "wheelchairBoarding", "parentStation"],
            "object_properties": ["locatedIn"],
        },
        {
            "source": "Computed/nearest_stop.csv",
            "target_entity": "HealthcareFacility",
            "identifier": ["entity_type", "entity_id", "entity_subcode"],
            "data_properties": ["distanceToNearestStop"],
            "object_properties": ["nearStop"],
        },
    ]


def main():
    PHASE4_DIR.mkdir(parents=True, exist_ok=True)
    triples = set()
    city = iri("City", "Milano")
    add_triple(triples, city, "a", iri("City"))
    add_triple(triples, city, iri("cityName"), typed("Milano"))

    # NIL entities
    nil_rows = read_csv(DATA_DIR / "NIL.csv", ";")
    nil_by_id = {}
    for row in nil_rows:
        nil_id = row["ID_NIL"].strip()
        nil_iri = iri("Neighbourhood", nil_id)
        nil_by_id[nil_id] = nil_iri
        add_triple(triples, nil_iri, "a", iri("Neighbourhood"))
        add_triple(triples, nil_iri, iri("nilId"), typed(nil_id))
        add_triple(triples, nil_iri, iri("nilName"), typed(row["NIL"]))
        for source, value, datatype in [
            ("Shape_Length", row["Shape_Length"], "xsd:decimal"),
            ("Shape_Area", row["Shape_Area"], "xsd:decimal"),
        ]:
            converted = decimal(value)
            if converted:
                add_triple(triples, nil_iri, iri("shapeLength" if source == "Shape_Length" else "shapeArea"), converted)

    municipality_by_nil = {}

    def facility_entities(filename, delimiter, entity_type, identifier_column, name_column):
        rows = read_csv(DATA_DIR / filename, delimiter)
        for row in rows:
            identifier = row.get(identifier_column, "").strip()
            if not identifier:
                continue
            subcode = row.get("facility_subcode", "").strip()
            identifier_key = identifier
            if entity_type == "Hospital" and subcode:
                identifier_key = identifier + "-" + subcode
            subject = iri(entity_type, identifier_key)
            add_triple(triples, subject, "a", iri(entity_type))
            add_triple(triples, subject, "a", iri("HealthcareFacility"))

            name = row.get(name_column, "").strip()
            if name:
                add_triple(triples, subject, iri("facilityName"), typed(name))
            for source, predicate in [
                ("address", "address"),
                ("postcode", "postcode"),
                ("municipio", "municipio"),
                ("nil_name", "nilName"),
                ("nil_name", "nilName"),
            ]:
                value = row.get(source, "").strip()
                if value:
                    add_triple(triples, subject, iri(predicate), typed(value))

            longitude = row.get("longitude", "").strip()
            latitude = row.get("latitude", "").strip()
            longitude_value = decimal(longitude)
            latitude_value = decimal(latitude)
            if longitude_value:
                add_triple(triples, subject, iri("longitude"), longitude_value)
            if latitude_value:
                add_triple(triples, subject, iri("latitude"), latitude_value)

            nil_id = row.get("nil_id", "").strip()
            if nil_id in nil_by_id:
                add_triple(triples, subject, iri("locatedIn"), nil_by_id[nil_id])
                municipio = row.get("municipio", "").strip()
                if municipio:
                    municipality_by_nil.setdefault(nil_id, set()).add(municipio)

            return subject

    # Hospital entities are created once per facility in the latest available year.
    hospital_rows = read_csv(DATA_DIR / "beds_translated.csv")
    latest_year = max(int(row["year"]) for row in hospital_rows if row["year"])
    hospitals = {}
    specialties = {}
    authorities = {}
    for row in hospital_rows:
        if row["year"] != str(latest_year):
            continue
        facility_code = row["facility_code"].strip()
        subcode = row["facility_subcode"].strip()
        identifier = facility_code if not subcode else facility_code + "-" + subcode
        subject = iri("Hospital", identifier)
        hospitals[identifier] = subject
        add_triple(triples, subject, "a", iri("Hospital"))
        add_triple(triples, subject, "a", iri("HealthcareFacility"))
        add_triple(triples, subject, iri("facilityCode"), typed(facility_code))
        add_triple(triples, subject, iri("facilitySubcode"), typed(subcode)) if subcode else None
        add_triple(triples, subject, iri("facilityName"), typed(row["facility_name"]))
        add_triple(triples, subject, iri("address"), typed(row["address"]))
        add_triple(triples, subject, iri("postcode"), typed(row["postcode"]))
        add_triple(triples, subject, iri("year"), typed(latest_year, "xsd:gYear"))
        add_triple(triples, subject, iri("facilityType"), typed(row["facility_type"]))

        for source, predicate in [
            ("longitude", "longitude"),
            ("latitude", "latitude"),
        ]:
            converted = decimal(row[source])
            if converted:
                add_triple(triples, subject, iri(predicate), converted)

        nil_id = row["nil_id"].strip()
        if nil_id in nil_by_id:
            add_triple(triples, subject, iri("locatedIn"), nil_by_id[nil_id])
            if row["municipio"].strip():
                municipality_by_nil.setdefault(nil_id, set()).add(row["municipio"].strip())

        specialty_code = row["discipline_code"].strip()
        if specialty_code:
            specialty = iri("MedicalSpecialty", specialty_code)
            specialties[specialty_code] = specialty
            add_triple(triples, specialty, "a", iri("MedicalSpecialty"))
            add_triple(triples, specialty, iri("specialtyCode"), typed(specialty_code))
            add_triple(triples, specialty, iri("specialtyName"), typed(row["discipline"]))
            add_triple(triples, subject, iri("hasSpecialty"), specialty)

        authority_code = row["health_authority_code"].strip()
        if authority_code:
            authority = iri("HealthAuthority", authority_code)
            authorities[authority_code] = authority
            add_triple(triples, authority, "a", iri("HealthAuthority"))
            add_triple(triples, authority, iri("authorityCode"), typed(authority_code))
            add_triple(triples, subject, iri("managedBy"), authority)

    # Aggregate repeated hospital rows for the latest year.
    bed_columns = {
        "bedsOrdinaryStay": "beds_ordinary_stay",
        "bedsPayingStay": "beds_paying_stay",
        "bedsDayHospital": "beds_day_hospital",
        "bedsDaySurgery": "beds_day_surgery",
        "bedsTotal": "beds_total",
        "numWards": "num_wards",
    }
    aggregates = {}
    for row in hospital_rows:
        if row["year"] != str(latest_year):
            continue
        subcode = row["facility_subcode"].strip()
        identifier = row["facility_code"].strip()
        key = identifier if not subcode else identifier + "-" + subcode
        aggregate = aggregates.setdefault(key, {column: 0 for column in bed_columns})
        for predicate, source in bed_columns.items():
            try:
                aggregate[predicate] += int(float(str(row[source]).replace(",", ".") or 0))
            except ValueError:
                pass
    for identifier, values in aggregates.items():
        subject = hospitals[identifier]
        for predicate, value in values.items():
            add_triple(triples, subject, iri(predicate), integer(value))

    facility_iris = dict(hospitals)
    def population(filename, delimiter, entity_type, identifier_column, name_column, extra=None):
        rows = read_csv(DATA_DIR / filename, delimiter)
        for row in rows:
            identifier = row.get(identifier_column, "").strip()
            if not identifier:
                continue
            subject = iri(entity_type, identifier)
            add_triple(triples, subject, "a", iri(entity_type))
            add_triple(triples, subject, "a", iri("HealthcareFacility"))
            add_triple(triples, subject, iri(identifier_column), typed(identifier))
            name = row.get(name_column, "").strip()
            if name:
                add_triple(triples, subject, iri("facilityName"), typed(name))
            if row.get("address"):
                add_triple(triples, subject, iri("address"), typed(row["address"]))
            if row.get("postcode"):
                add_triple(triples, subject, iri("postcode"), typed(row["postcode"]))
            for source, predicate in [("longitude", "longitude"), ("latitude", "latitude")]:
                converted = decimal(row[source]) if row.get(source) else None
                if converted:
                    add_triple(triples, subject, iri(predicate), converted)
            nil_id = row.get("nil_id", "").strip()
            if nil_id in nil_by_id:
                add_triple(triples, subject, iri("locatedIn"), nil_by_id[nil_id])
                if row.get("municipio"):
                    municipality_by_nil.setdefault(nil_id, set()).add(row["municipio"].strip())
            if extra:
                extra(triples, subject, row)
            key = (entity_type, identifier, "")
            facility_iris[key] = subject

    population("Pharmacy_translated.csv", ",", "Pharmacy", "pharmacy_code", "pharmacy_name")
    population("PublicHealthCentres_translated.csv", ",", "PublicHealthCentre", "facility_code", "facility_name")
    def rsa_extra(triples, subject, row):
        for source, predicate in [
            ("authorised_places", "authorisedPlaces"),
            ("accredited_non_contracted_places", "accreditedNonContractedPlaces"),
        ]:
            converted = integer(row.get(source))
            if converted:
                add_triple(triples, subject, iri(predicate), converted)
    population("rsa_translated.csv", ",", "NursingHome", "facility_code", "facility_name", rsa_extra)

    # Municipalities and municipality membership for NIL areas.
    municipality_iris = {}
    for nil_id, municipality_numbers in municipality_by_nil.items():
        for municipality_number in municipality_numbers:
            municipality = iri("Municipio", municipality_number)
            municipality_iris[municipality_number] = municipality
            add_triple(triples, municipality, "a", iri("Municipio"))
            add_triple(triples, municipality, iri("municipioNumber"), typed(municipality_number))
            add_triple(triples, municipality, iri("partOf"), city)
            add_triple(triples, nil_by_id[nil_id], iri("partOf"), municipality)

    # Agency and routes.
    agency_rows = read_csv(DATA_DIR / "AziendaTransportMilanesi" / "agency.txt")
    agency_subjects = {}
    for row in agency_rows:
        agency_id = row["agency_id"].strip()
        subject = iri("TransportOperator", agency_id)
        agency_subjects[agency_id] = subject
        add_triple(triples, subject, "a", iri("TransportOperator"))
        add_triple(triples, subject, iri("agencyId"), typed(agency_id))
        add_triple(triples, subject, iri("agencyName"), typed(row["agency_name"]))
        add_triple(triples, subject, iri("agencyURL"), typed(row["agency_url"]))
        add_triple(triples, subject, iri("agencyTimezone"), typed(row["agency_timezone"]))

    route_subjects = {}
    route_rows = read_csv(DATA_DIR / "AziendaTransportMilanesi" / "routes.txt")
    route_modes = {"0": "tram", "1": "metro", "3": "bus"}
    for row in route_rows:
        route_id = row["route_id"].strip()
        subject = iri("Route", route_id)
        route_subjects[route_id] = subject
        add_triple(triples, subject, "a", iri("Route"))
        add_triple(triples, subject, iri("routeId"), typed(route_id))
        add_triple(triples, subject, iri("routeShortName"), typed(row["route_short_name"]))
        add_triple(triples, subject, iri("routeLongName"), typed(row["route_long_name"]))
        add_triple(triples, subject, iri("routeMode"), typed(route_modes.get(row["route_type"], "unknown")))
        agency_id = row["agency_id"].strip()
        if agency_id in agency_subjects:
            add_triple(triples, subject, iri("operatedBy"), agency_subjects[agency_id])

    # Stops and optional NIL spatial membership.
    stop_subjects = {}
    with (DATA_DIR / "NIL.geojson").open(encoding="utf-8-sig") as stream:
        geojson = json.load(stream)
    polygons = []
    for feature in geojson["features"]:
        nil_id = str(feature["properties"]["ID_NIL"])
        polygons.append((nil_id, feature["geometry"]))

    stop_rows = read_csv(DATA_DIR / "AziendaTransportMilanesi" / "stops.txt")
    for row in stop_rows:
        stop_id = row["stop_id"].strip()
        subject = iri("Stop", stop_id)
        stop_subjects[stop_id] = subject
        add_triple(triples, subject, "a", iri("Stop"))
        add_triple(triples, subject, iri("stopId"), typed(stop_id))
        add_triple(triples, subject, iri("stopName"), typed(row["stop_name"]))
        add_triple(triples, subject, iri("stopCode"), typed(row["stop_code"]))
        add_triple(triples, subject, iri("wheelchairBoarding"), typed(row["wheelchair_boarding"]))
        longitude = decimal(row["stop_lon"])
        latitude = decimal(row["stop_lat"])
        if longitude:
            add_triple(triples, subject, iri("longitude"), longitude)
        if latitude:
            add_triple(triples, subject, iri("latitude"), latitude)
        if longitude and latitude:
            lon = float(row["stop_lon"])
            lat = float(row["stop_lat"])
            for nil_id, geometry in polygons:
                if polygon_contains(geometry, lon, lat):
                    if nil_id in nil_by_id:
                        add_triple(triples, subject, iri("locatedIn"), nil_by_id[nil_id])
                    break

    # Map accessibility results to entities and stop IRIs.
    nearest = read_csv(PROJECT_DIR / "Computed" / "nearest_stop.csv")
    for row in nearest:
        entity_type = row["entity_type"]
        entity_id = row["entity_id"]
        subcode = row["entity_subcode"].strip()
        identifier = entity_id if not subcode or entity_type != "Hospital" else entity_id + "-" + subcode
        subject = iri(entity_type, identifier)
        stop_subject = stop_subjects.get(row["nearest_stop_id"])
        if stop_subject:
            add_triple(triples, subject, iri("nearStop"), stop_subject)
        distance = decimal(row["nearest_stop_distance_m"])
        if distance:
            add_triple(triples, subject, iri("distanceToNearestStop"), distance)

    near_rows = read_csv(PROJECT_DIR / "Computed" / "near_stop.csv")
    for row in near_rows:
        entity_type = row["entity_type"]
        entity_id = row["entity_id"]
        subcode = row["entity_subcode"].strip()
        identifier = entity_id if not subcode or entity_type != "Hospital" else entity_id + "-" + subcode
        subject = iri(entity_type, identifier)
        stop_subject = stop_subjects.get(row["stop_id"])
        if not stop_subject:
            continue
        add_triple(triples, subject, iri("nearStop"), stop_subject)
        if row["threshold"] == "within_300m":
            add_triple(triples, subject, iri("nearStopWithin300m"), stop_subject)

    # Serialize Turtle.
    lines = [
        "@prefix kg: <" + BASE + "> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]
    for subject, predicate, value in sorted(triples):
        lines.append(subject + " " + predicate + " " + value + " .")
    ttl_path = PHASE4_DIR / "entity_graph.ttl"
    ttl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    mappings_path = PHASE4_DIR / "mappings.json"
    mappings_path.write_text(json.dumps(source_mappings(), indent=2), encoding="utf-8")

    # Validate basic references and report the generated population.
    entity_types = {}
    for subject, predicate, value in triples:
        if predicate == "a":
            entity_types[value] = entity_types.get(value, 0) + 1
    validation = {
        "entity_triples": len(triples),
        "entities_by_class": {
            key.replace(BASE, "").replace("Hospital/", "Hospital:"): count
            for key, count in sorted(entity_types.items())
        },
        "entity_count": sum(
            count for key, count in entity_types.items()
            if key != iri("HealthcareFacility")
        ),
        "source_entity_hospital_records": len(hospitals),
        "source_entity_pharmacies": len(read_csv(DATA_DIR / "Pharmacy_translated.csv")),
        "source_entity_public_health_centres": len(read_csv(DATA_DIR / "PublicHealthCentres_translated.csv")),
        "source_entity_nursing_homes": len(read_csv(DATA_DIR / "rsa_translated.csv")),
        "source_entity_stops": len(stop_subjects),
        "source_entity_routes": len(route_subjects),
        "source_entity_nil": len(nil_by_id),
        "accessibility_nearest_rows": len(nearest),
        "accessibility_threshold_pairs": len(near_rows),
        "accessibility_skipped": len(read_csv(PROJECT_DIR / "Computed" / "skipped_facilities.csv")),
        "missing_route_stop_mapping": "stop_times.txt is absent; no route-stop links were inferred",
        "files": {
            "mappings": str(mappings_path.relative_to(PROJECT_DIR)),
            "entity_graph": str(ttl_path.relative_to(PROJECT_DIR)),
        },
    }
    validation_path = PHASE4_DIR / "entity_validation.json"
    validation_path.write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
