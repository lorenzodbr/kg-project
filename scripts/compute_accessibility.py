"""Compute healthcare-facility accessibility to ATM stops.

The script reads the translated healthcare CSV files and the ATM GTFS
``stops.txt`` file. It projects WGS84 coordinates to UTM zone 32N, computes
the distance from every facility to every stop, and writes:

* ``nearest_stop.csv``: one row per facility and its nearest stop;
* ``near_stop.csv``: one row for every facility-stop pair within a requested
  threshold.

The source files are not modified. Run from any directory with:

    python scripts/compute_accessibility.py
"""

import argparse
import csv
import math
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "Datasets"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "Computed"


FACILITY_SOURCES = (
    ("Hospital", "beds_translated.csv", "facility_code", "facility_name"),
    ("Pharmacy", "Pharmacy_translated.csv", "pharmacy_code", "pharmacy_name"),
    (
        "PublicHealthCentre",
        "PublicHealthCentres_translated.csv",
        "facility_code",
        "facility_name",
    ),
    ("NursingHome", "rsa_translated.csv", "facility_code", "facility_name"),
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated CSV files.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        action="append",
        dest="thresholds",
        help="Distance threshold in metres; may be supplied more than once.",
    )
    return parser.parse_args()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def require_columns(path, rows, columns):
    if not rows:
        raise ValueError(f"{path} contains no data rows")
    missing = [column for column in columns if column not in rows[0]]
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")


def coordinate(row, path, row_number):
    try:
        longitude = float(row["longitude"])
        latitude = float(row["latitude"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"{path}, row {row_number}: invalid longitude/latitude"
        ) from error
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError(f"{path}, row {row_number}: coordinate outside WGS84")
    return longitude, latitude


def utm32n(longitude, latitude):
    """Project WGS84 coordinates to UTM zone 32N, returning metres.

    This is the standard UTM Transverse Mercator calculation for EPSG:32632.
    Milan lies within UTM zone 32N, so Euclidean distances in this projection
    are appropriate for the local distance comparisons used here.
    """
    semi_major = 6378137.0
    flattening = 1 / 298.257223563
    eccentricity_squared = flattening * (2 - flattening)
    second_eccentricity_squared = eccentricity_squared / (1 - eccentricity_squared)
    scale = 0.9996
    false_easting = 500000.0
    false_northing = 0.0
    central_meridian = math.radians(9.0)

    latitude_radians = math.radians(latitude)
    longitude_radians = math.radians(longitude)
    sine_latitude = math.sin(latitude_radians)
    cosine_latitude = math.cos(latitude_radians)
    tangent_latitude = math.tan(latitude_radians)
    radius_curvature = semi_major / math.sqrt(
        1 - eccentricity_squared * sine_latitude * sine_latitude
    )
    meridional_arc = semi_major * (
        (1 - eccentricity_squared / 4 - 3 * eccentricity_squared**2 / 64
         - 5 * eccentricity_squared**3 / 256) * latitude_radians
        - (3 * eccentricity_squared / 8 + 3 * eccentricity_squared**2 / 32
           + 45 * eccentricity_squared**3 / 1024) * math.sin(2 * latitude_radians)
        + (15 * eccentricity_squared**2 / 256
           + 45 * eccentricity_squared**3 / 1024) * math.sin(4 * latitude_radians)
        - (35 * eccentricity_squared**3 / 3072) * math.sin(6 * latitude_radians)
    )
    central_meridian_arc = semi_major * (
        (1 - eccentricity_squared / 4 - 3 * eccentricity_squared**2 / 64
         - 5 * eccentricity_squared**3 / 256) * central_meridian
        - (3 * eccentricity_squared / 8 + 3 * eccentricity_squared**2 / 32
           + 45 * eccentricity_squared**3 / 1024) * math.sin(2 * central_meridian)
        + (15 * eccentricity_squared**2 / 256
           + 45 * eccentricity_squared**3 / 1024) * math.sin(4 * central_meridian)
        - (35 * eccentricity_squared**3 / 3072) * math.sin(6 * central_meridian)
    )
    difference_longitude = longitude_radians - central_meridian
    parameter_a = difference_longitude * cosine_latitude
    parameter_t = tangent_latitude * tangent_latitude
    parameter_c = second_eccentricity_squared * cosine_latitude * cosine_latitude

    easting = false_easting + scale * radius_curvature * (
        parameter_a
        + (1 - parameter_t + parameter_c) * parameter_a**3 / 6
        + (5 - 18 * parameter_t + parameter_t**2 + 72 * parameter_c
           - 58 * second_eccentricity_squared) * parameter_a**5 / 120
    )
    northing = false_northing + scale * (
        meridional_arc - central_meridian_arc
        + radius_curvature * tangent_latitude * (
            parameter_a**2 / 2
            + (5 - parameter_t + 9 * parameter_c + 4 * parameter_c**2)
            * parameter_a**4 / 24
            + (61 - 58 * parameter_t + parameter_t**2 + 600 * parameter_c
               - 330 * second_eccentricity_squared) * parameter_a**6 / 720
        )
    )
    return easting, northing


def read_facilities():
    facilities = []
    skipped = []
    for entity_type, filename, identifier_column, name_column in FACILITY_SOURCES:
        path = DATA_DIR / filename
        rows = read_csv(path)
        require_columns(
            path,
            rows,
            [identifier_column, name_column, "longitude", "latitude"],
        )

        # The hospital table has one row per specialty and year. Keep only
        # the latest year for the facility-level accessibility calculation.
        if entity_type == "Hospital":
            latest_year = max(int(row["year"]) for row in rows if row["year"])
            rows = [row for row in rows if row["year"] == str(latest_year)]

        seen = set()
        for row_number, row in enumerate(rows, start=2):
            identifier = row[identifier_column].strip()
            if not identifier:
                raise ValueError(f"{path}, row {row_number}: empty identifier")
            key = (entity_type, identifier, row.get("facility_subcode", "").strip())
            if key in seen:
                continue
            seen.add(key)
            if not row.get("longitude", "").strip() or not row.get("latitude", "").strip():
                skipped.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": identifier,
                        "entity_subcode": row.get("facility_subcode", "").strip(),
                        "entity_name": row[name_column].strip(),
                        "source_file": filename,
                        "source_row": row_number,
                        "reason": "missing longitude or latitude",
                    }
                )
                continue
            longitude, latitude = coordinate(row, path, row_number)
            easting, northing = utm32n(longitude, latitude)
            facilities.append(
                {
                    "entity_type": entity_type,
                    "entity_id": identifier,
                    "entity_subcode": row.get("facility_subcode", "").strip(),
                    "entity_name": row[name_column].strip(),
                    "longitude": longitude,
                    "latitude": latitude,
                    "easting": easting,
                    "northing": northing,
                    "nil_id": row.get("nil_id", "").strip(),
                    "nil_name": row.get("nil_name", "").strip(),
                    "source_file": filename,
                }
            )
    return facilities, skipped


def read_stops():
    path = DATA_DIR / "AziendaTransportMilanesi" / "stops.txt"
    rows = read_csv(path)
    required = ["stop_id", "stop_name", "stop_lon", "stop_lat"]
    require_columns(path, rows, required)
    stops = []
    for row_number, row in enumerate(rows, start=2):
        longitude, latitude = coordinate(
            {"longitude": row["stop_lon"], "latitude": row["stop_lat"]},
            path,
            row_number,
        )
        easting, northing = utm32n(longitude, latitude)
        stops.append(
            {
                "stop_id": row["stop_id"].strip(),
                "stop_code": row.get("stop_code", "").strip(),
                "stop_name": row["stop_name"].strip(),
                "longitude": longitude,
                "latitude": latitude,
                "wheelchair_boarding": row.get("wheelchair_boarding", "").strip(),
                "easting": easting,
                "northing": northing,
            }
        )
    return stops


def compute(facilities, stops, thresholds):
    nearest = []
    links = []
    threshold_names = [f"within_{int(threshold)}m" for threshold in thresholds]

    for facility in facilities:
        distances = []
        for stop in stops:
            distance = math.hypot(
                facility["easting"] - stop["easting"],
                facility["northing"] - stop["northing"],
            )
            distances.append((distance, stop))
            for threshold, threshold_name in zip(thresholds, threshold_names):
                if distance <= threshold:
                    links.append(
                        {
                            "entity_type": facility["entity_type"],
                            "entity_id": facility["entity_id"],
                            "entity_subcode": facility["entity_subcode"],
                            "entity_name": facility["entity_name"],
                            "nil_id": facility["nil_id"],
                            "nil_name": facility["nil_name"],
                            "stop_id": stop["stop_id"],
                            "stop_code": stop["stop_code"],
                            "stop_name": stop["stop_name"],
                            "distance_m": f"{distance:.2f}",
                            "threshold": threshold_name,
                            "wheelchair_boarding": stop["wheelchair_boarding"],
                        }
                    )

        distance, stop = min(distances, key=lambda item: item[0])
        row = {
            "entity_type": facility["entity_type"],
            "entity_id": facility["entity_id"],
            "entity_subcode": facility["entity_subcode"],
            "entity_name": facility["entity_name"],
            "nil_id": facility["nil_id"],
            "nil_name": facility["nil_name"],
            "nearest_stop_id": stop["stop_id"],
            "nearest_stop_name": stop["stop_name"],
            "nearest_stop_distance_m": f"{distance:.2f}",
            "nearest_stop_wheelchair_boarding": stop["wheelchair_boarding"],
        }
        for threshold, threshold_name in zip(thresholds, threshold_names):
            row[f"has_stop_{threshold_name}"] = str(distance <= threshold).lower()
        nearest.append(row)
    return nearest, links


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"Refusing to write empty result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    thresholds = sorted(set(args.thresholds or [300.0, 500.0]))
    if any(threshold <= 0 for threshold in thresholds):
        raise ValueError("Distance thresholds must be positive")

    facilities, skipped = read_facilities()
    stops = read_stops()
    nearest, links = compute(facilities, stops, thresholds)
    write_csv(args.output_dir / "nearest_stop.csv", nearest)
    write_csv(args.output_dir / "near_stop.csv", links)
    if skipped:
        write_csv(args.output_dir / "skipped_facilities.csv", skipped)

    print(f"Facilities: {len(facilities)}")
    print(f"Facilities skipped for missing coordinates: {len(skipped)}")
    print(f"Stops: {len(stops)}")
    print(f"Nearest-stop rows: {len(nearest)}")
    print(f"Near-stop rows: {len(links)}")
    print(f"Output directory: {args.output_dir}")


if __name__ == "__main__":
    main()
