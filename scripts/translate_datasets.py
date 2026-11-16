"""Make English translated copies of the healthcare datasets.

Reads the raw CSVs in Datasets/ (never modifies them) and writes
<name>_translated.csv next to them.

What is translated:
  - column names (to English snake_case, shared names across datasets)
  - Italian categorical values (facility type, discipline, discipline type,
    centre type, RSA programme/type, legal form, ONLUS flag)
What is NOT translated (kept as in the source):
  - proper nouns: facility names, operator names, addresses, NIL names
  - numeric codes whose meaning is not documented (e.g. Tipo Azienda, ABILITAZIONE)

All values are read as text so leading zeros in codes are kept.
If a categorical value appears that has no translation, the script stops,
so the translated files are never silently incomplete.

Usage: python3 scripts/translate_datasets.py
Output: comma-separated, UTF-8.
"""

import csv
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "Datasets"

# ---------------------------------------------------------------- columns

COMMON_COLS = {
    "CAP": "postcode",
    "MUNICIPIO": "municipio",
    "ID_NIL": "nil_id",
    "NIL": "nil_name",
    "Location": "location",
}

BEDS_COLS = {
    "Anno": "year",
    "Codice Azienda": "health_authority_code",
    "Tipo Azienda": "health_authority_type_code",
    "Codice struttura": "facility_code",
    "Subcodice": "facility_subcode",
    "Denominazione Struttura/Stabilimento": "facility_name",
    "Indirizzo": "address",
    "Codice tipo struttura": "facility_type_code",
    "Descrizione tipo struttura": "facility_type",
    "Codice disciplina": "discipline_code",
    "Descrizione disciplina": "discipline",
    "Tipo di Disciplina": "discipline_type",
    "N Reparti": "num_wards",
    "Posti letto degenza ordinaria": "beds_ordinary_stay",
    "Posti letto degenza a pagamento": "beds_paying_stay",
    "Posti letto Day Hospital": "beds_day_hospital",
    "Posti letto Day Surgery": "beds_day_surgery",
    "Totale posti letto": "beds_total",
    "address_MI": "address_geocoded",
    "LONG_X_4326": "longitude",
    "LAT_Y_4326": "latitude",
    **COMMON_COLS,
}

PHARMACY_COLS = {
    "_id": "_id",
    "CODICE_FARMACIA": "pharmacy_code",
    "DESCRIZIONE_FARMACIA": "pharmacy_name",
    "PARTITA_IVA": "vat_number",
    "INDIRIZZO": "address",
    "COMUNE": "city",
    "FRAZIONE": "hamlet",
    "PROVINCIA": "province",
    "CODICE_ISTAT": "istat_city_code",
    "LONGITUDINE": "longitude",
    "LATITUDINE": "latitude",
    **COMMON_COLS,
}

PHC_COLS = {
    "COD_ASL": "local_health_authority_code",
    "COD_STRUTTURA": "facility_code",
    "DENOM_STRUTTURA": "facility_name",
    "INDIRIZZO_UBICAZIONE": "address",
    "COD_ISTAT_COMUNE_UBICAZIONE": "istat_city_code",
    "COMUNE_UBICAZIONE": "city",
    "PROV_COMUNE_UBICAZIONE": "province",
    "COD_GESTORE": "operator_code",
    "DENOM_GESTORE": "operator_name",
    "P_IVA": "vat_number",
    "COD_FISCALE_GESTORE": "operator_tax_code",
    "INDIRIZZO_SEDE_LEGALE": "operator_registered_address",
    "COD_ISTAT_COMUNE_SEDE_LEGALE": "operator_registered_istat_city_code",
    "COMUNE_SEDE_LEGALE": "operator_registered_city",
    "PROV_SEDE_LEGALE": "operator_registered_province",
    "WGS84_Y": "latitude",
    "WGS84_X": "longitude",
    **COMMON_COLS,
}

RSA_COLS = {
    "CD_ENTE": "agency_code",
    "ASL": "local_health_authority_code",
    "MISURA": "care_programme",
    "TIPO_UDO": "service_unit_type",
    "COD_STRUT": "facility_code",
    "DESC_STRUT": "facility_name",
    "INDIRIZZO_UBI": "address",
    "COD_ISTAT_COMUNE": "istat_city_code",
    "NUM_TELEFONO": "phone",
    "NUM_FAX": "fax",
    "POSTI_AUT": "authorised_places",
    "POSTI_ACCR_NO_CONTR": "accredited_non_contracted_places",
    "COD_AMBITO_CAPOFILA": "lead_district_code",
    "DESC_GESTORE": "operator_name",
    "COD_FISCALE": "operator_tax_code",
    "PARTITA_IVA": "vat_number",
    "INDIRIZZO_SEDE_LEGALE": "operator_registered_address",
    "COD_ISTAT_SEDE_LEGALE": "operator_registered_istat_city_code",
    "COMUNE_SEDE_LEGALE": "operator_registered_city",
    "CAP_SEDE_LEGALE": "operator_registered_postcode",
    "PROV_SEDE_LEGALE": "operator_registered_province",
    "NUM_TEL_GESTORE": "operator_phone",
    "NUM_FAX_GESTORE": "operator_fax",
    "NATURA_GIURIDICA_GEST": "operator_legal_form",
    "PUBBLICA_PRIVATA": "public_or_private",
    "ONLUS": "is_onlus",
    "DATA_CONTRATTO": "contract_date",
    "DATA_CHIUSURA": "closure_date",
    "ABILITAZIONE": "enablement_code",
    "ACCREDITAMENTO": "accreditation_code",
    "PARTECIPAZIONE": "participation",
    "PARTEC_ALTRI_PRJ": "participation_other_projects_code",
    "WGS84_Y": "latitude",
    "WGS84_X": "longitude",
    **COMMON_COLS,
}

# ---------------------------------------------------------------- values

FACILITY_TYPE = {
    "Ospedale a gestione diretta": "Directly managed public hospital",
    "Casa di cura privata accreditata": "Accredited private clinic",
    "IRCCS fondazione": "IRCCS foundation (research hospital)",
    "IRCCS privato": "Private IRCCS (research hospital)",
    "Ospedale classificato o assimilato ai sensi dell'art. 1, ultimo comma, della Legge 132/1968":
        "Classified or equivalent hospital (Law 132/1968, art. 1, last paragraph)",
}

DISCIPLINE_TYPE = {
    "ACUTI": "ACUTE CARE",
    "LUNGODEGENZA": "LONG-TERM CARE",
    "RIABILITAZIONE": "REHABILITATION",
}

DISCIPLINE = {
    "ALLERGOLOGIA": "ALLERGOLOGY",
    "ANGIOLOGIA": "ANGIOLOGY",
    "ASTANTERIA": "EMERGENCY OBSERVATION WARD",
    "CARDIOCHIRURGIA": "CARDIAC SURGERY",
    "CARDIOLOGIA": "CARDIOLOGY",
    "CHIRURGIA GENERALE": "GENERAL SURGERY",
    "CHIRURGIA MAXILLO FACCIALE": "MAXILLOFACIAL SURGERY",
    "CHIRURGIA PEDIATRICA": "PAEDIATRIC SURGERY",
    "CHIRURGIA PLASTICA": "PLASTIC SURGERY",
    "CHIRURGIA TORACICA": "THORACIC SURGERY",
    "CHIRURGIA VASCOLARE": "VASCULAR SURGERY",
    "CURE PALLIATIVE": "PALLIATIVE CARE",
    "CURE PALLIATIVE/HOSPICE": "PALLIATIVE CARE/HOSPICE",
    "DAY HOSPITAL": "DAY HOSPITAL",
    "DAY SURGERY": "DAY SURGERY",
    "DERMATOLOGIA": "DERMATOLOGY",
    "EMATOLOGIA": "HAEMATOLOGY",
    "FISIOPATOLOGIA DELLA RIPRODUZIONE UMANA": "HUMAN REPRODUCTIVE PATHOPHYSIOLOGY",
    "GASTROENTEROLOGIA": "GASTROENTEROLOGY",
    "GERIATRIA": "GERIATRICS",
    "GRANDI USTIONATI": "SEVERE BURNS UNIT",
    "IMMUNOLOGIA": "IMMUNOLOGY",
    "LUNGODEGENTI": "LONG-TERM CARE PATIENTS",
    "MALATTIE ENDOCRINE DEL RICAMBIO E NUTRIZ": "ENDOCRINE, METABOLIC AND NUTRITIONAL DISEASES",
    "MALATTIE INFETTIVE E TROPICALI": "INFECTIOUS AND TROPICAL DISEASES",
    "MEDICINA DEL LAVORO": "OCCUPATIONAL MEDICINE",
    "MEDICINA GENERALE": "GENERAL MEDICINE",
    "MEDICINA NUCLEARE": "NUCLEAR MEDICINE",
    "NEFROLOGIA": "NEPHROLOGY",
    "NEFROLOGIA (ABILITATO AL TRAPIANTO RENE)": "NEPHROLOGY (KIDNEY TRANSPLANT CERTIFIED)",
    "NEONATOLOGIA": "NEONATOLOGY",
    "NEURO-RIABILITAZIONE": "NEUROREHABILITATION",
    "NEUROCHIRURGIA": "NEUROSURGERY",
    "NEUROLOGIA": "NEUROLOGY",
    "NEUROPSICHIATRIA INFANTILE": "CHILD NEUROPSYCHIATRY",
    "OCULISTICA": "OPHTHALMOLOGY",
    "ODONTOIATRIA E STOMATOLOGIA": "DENTISTRY AND STOMATOLOGY",
    "ONCOEMATOLOGIA": "ONCO-HAEMATOLOGY",
    "ONCOLOGIA": "ONCOLOGY",
    "ORTOPEDIA E TRAUMATOLOGIA": "ORTHOPAEDICS AND TRAUMATOLOGY",
    "OSTETRICIA E GINECOLOGIA": "OBSTETRICS AND GYNAECOLOGY",
    "OTORINOLARINGOIATRIA": "OTORHINOLARYNGOLOGY (ENT)",
    "PEDIATRIA": "PAEDIATRICS",
    "PENSIONANTI": "PRIVATE PAYING PATIENTS",
    "PNEUMOLOGIA": "PULMONOLOGY",
    "PSICHIATRIA": "PSYCHIATRY",
    "RADIOLOGIA": "RADIOLOGY",
    "RADIOTERAPIA": "RADIOTHERAPY",
    "RECUPERO E RIABILITAZIONE": "RECOVERY AND REHABILITATION",
    "REUMATOLOGIA": "RHEUMATOLOGY",
    "TERAPIA INTENSIVA": "INTENSIVE CARE",
    "TERAPIA INTENSIVA NEONATALE": "NEONATAL INTENSIVE CARE",
    "UNITA` CORONARICA": "CORONARY CARE UNIT",
    "UNITA` SPINALE": "SPINAL UNIT",
    "UROLOGIA": "UROLOGY",
}

# Generic part is translated; the proper name (Villa Marelli) is kept.
PHC_FACILITY_NAME = {
    "CONSULTORIO FAMILIARE PUBBLICO": "PUBLIC FAMILY COUNSELLING CENTRE",
    "CONSULTORIO FAMILIARE VILLA MARELLI": "FAMILY COUNSELLING CENTRE VILLA MARELLI",
}

RSA_PROGRAMME = {"RSA Aperta": "Open RSA (home-based support for older people)"}
RSA_UNIT_TYPE = {"RSA": "Nursing home (RSA)"}

LEGAL_FORM = {
    "": "",
    "Azienda di servizi alla persona": "Public personal-services agency",
    "Ente morale di diritto privato": "Private-law non-profit body",
    "Fondazione": "Foundation",
    "Società a responsabilità limitata": "Limited liability company",
    "Società a responsabilità limitata a socio unico": "Single-member limited liability company",
    "Società cooperativa di solidarietà sociale": "Social solidarity cooperative",
    "Società per azioni": "Joint-stock company",
}

YES_NO = {"S": "Y", "N": "N", "": ""}

# ---------------------------------------------------------------- engine

DATASETS = [
    # (input file, delimiter, column map, {source column: value map})
    ("beds.csv", ";", BEDS_COLS, {
        "Descrizione tipo struttura": FACILITY_TYPE,
        "Descrizione disciplina": DISCIPLINE,
        "Tipo di Disciplina": DISCIPLINE_TYPE,
    }),
    ("Pharmacy.csv", ",", PHARMACY_COLS, {}),
    ("PublicHealthCentres.csv", ";", PHC_COLS, {
        "DENOM_STRUTTURA": PHC_FACILITY_NAME,
    }),
    ("rsa.csv", ";", RSA_COLS, {
        "MISURA": RSA_PROGRAMME,
        "TIPO_UDO": RSA_UNIT_TYPE,
        "NATURA_GIURIDICA_GEST": LEGAL_FORM,
        "ONLUS": YES_NO,
    }),
]


def translate(fname, delim, col_map, value_maps):
    src = DATA_DIR / fname
    dst = DATA_DIR / f"{src.stem}_translated.csv"

    with open(src, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        in_cols = reader.fieldnames
        rows = list(reader)

    missing_cols = [c for c in in_cols if c not in col_map]
    if missing_cols:
        sys.exit(f"{fname}: no English name for columns {missing_cols}")

    unmapped = {}
    for col, vmap in value_maps.items():
        bad = sorted({r[col] for r in rows} - vmap.keys())
        if bad:
            unmapped[col] = bad
    if unmapped:
        sys.exit(f"{fname}: untranslated values {unmapped}")

    out_cols = [col_map[c] for c in in_cols]
    with open(dst, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(out_cols)
        for r in rows:
            writer.writerow([value_maps[c][r[c]] if c in value_maps else r[c] for c in in_cols])

    print(f"{fname:26} -> {dst.name:36} rows {len(rows):5}  cols {len(in_cols):3}"
          f"  translated value columns: {list(value_maps) or 'none'}")


if __name__ == "__main__":
    for args in DATASETS:
        translate(*args)
