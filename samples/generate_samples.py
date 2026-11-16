import math
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SEGMENTS = ["retail", "sme", "corporate", "mortgage", "cards", "leasing"]
LGDS = ["0.25", "0.40", "0.45", "0.50", "0.75"]
ROWS = 500
BLANKS = 12
TIES = 16
QUANT = Decimal("0.0001")


def sas_round(x):
    return float(Decimal(repr(round(x, 12))).quantize(QUANT, ROUND_HALF_UP))


def helper_round(x):
    return np.sign(x) * np.floor(np.abs(x) * 10**4 + 0.5 + 1e-9) / 10**4


def tie_candidates():
    found = []
    for k in range(200, 1501):
        pd_text = f"{k / 10000:.4f}"
        for lgd_text in LGDS:
            exact = Decimal(pd_text) * Decimal(lgd_text)
            scaled = exact * 100000
            if scaled != scaled.to_integral_value() or int(scaled) % 10 != 5:
                continue
            x = float(pd_text) * float(lgd_text)
            if float(np.round(x, 4)) != sas_round(x):
                found.append((pd_text, lgd_text))
    return found


def is_tie(pd_text, lgd_text):
    scaled = Decimal(pd_text) * Decimal(lgd_text) * 100000
    return scaled == scaled.to_integral_value() and int(scaled) % 10 == 5


def build_loans(rng):
    candidates = tie_candidates()
    if len(candidates) < 10:
        raise SystemExit("not enough rounding tie candidates")
    rows = []
    for i in range(ROWS):
        exposure = round(math.exp(rng.uniform(math.log(1000), math.log(2500000))), 2)
        balance = round(exposure * rng.uniform(0.2, 0.95), 2)
        pd_text = f"{rng.randint(50, 2500) / 10000:.4f}"
        lgd_text = rng.choice(LGDS)
        while is_tie(pd_text, lgd_text):
            pd_text = f"{rng.randint(50, 2500) / 10000:.4f}"
        rows.append(
            {
                "loan_id": 1001 + i,
                "segment": rng.choice(SEGMENTS),
                "exposure": f"{exposure:.2f}",
                "balance": f"{balance:.2f}",
                "pd": pd_text,
                "lgd": lgd_text,
            }
        )
    positions = list(range(ROWS))
    rng.shuffle(positions)
    tie_rows = positions[:TIES]
    blank_rows = positions[TIES : TIES + BLANKS]
    for idx in tie_rows:
        rows[idx]["pd"], rows[idx]["lgd"] = rng.choice(candidates)
    for idx in blank_rows:
        rows[idx]["exposure"] = ""
    return pd.DataFrame(rows)


def main():
    rng = random.Random(2026)
    loans = build_loans(rng)
    loans.to_csv(ROOT / "loans.csv", index=False)

    data = pd.read_csv(ROOT / "loans.csv")
    assert len(data) == ROWS
    assert int(data["exposure"].isna().sum()) == BLANKS
    assert data["loan_id"].min() == 1001 and data["loan_id"].max() == 1500
    assert 0.005 <= data["pd"].min() and data["pd"].max() <= 0.25
    assert set(data["lgd"].astype(str)) <= {"0.25", "0.4", "0.45", "0.5", "0.75"}

    product = data["pd"] * data["lgd"]
    expected_rate = product.map(sas_round)
    numpy_rate = product.round(4)
    differing = (numpy_rate != expected_rate) & data["exposure"].notna()
    assert int(differing.sum()) >= 10, "too few rounding differences"
    assert int(((numpy_rate != expected_rate) & data["exposure"].isna()).sum()) == 0
    assert (helper_round(product) == expected_rate).all(), "helper does not match"

    sas = data.copy()
    sas["rate"] = expected_rate
    sas["prov"] = sas["exposure"] * sas["rate"]
    sas.to_csv(ROOT / "sas" / "expected" / "provisions.csv", index=False)

    vba = data.copy()
    vba["rate"] = vba["pd"] * vba["lgd"]
    vba["prov"] = vba["exposure"].fillna(0) * vba["rate"]
    vba.to_csv(ROOT / "vba" / "expected" / "result.csv", index=False)

    naive_sas = data.copy()
    naive_sas["rate"] = numpy_rate
    naive_sas["prov"] = naive_sas["exposure"] * naive_sas["rate"]
    assert naive_sas["rate"].min() == sas["rate"].min()
    assert naive_sas["rate"].max() == sas["rate"].max()
    assert naive_sas["prov"].min() == sas["prov"].min()
    assert naive_sas["prov"].max() == sas["prov"].max()
    assert naive_sas["prov"].isna().sum() == sas["prov"].isna().sum()
    assert naive_sas["rate"].sum() != sas["rate"].sum()

    naive_vba = data.copy()
    naive_vba["rate"] = naive_vba["pd"] * naive_vba["lgd"]
    naive_vba["prov"] = naive_vba["exposure"] * naive_vba["rate"]
    assert naive_vba["prov"].sum() == vba["prov"].sum()
    assert naive_vba["prov"].max() == vba["prov"].max()
    assert naive_vba["prov"].min() != vba["prov"].min()

    print(f"loans.csv: {ROWS} rows, {BLANKS} blank exposures")
    print(f"rounding differences: {int(differing.sum())} rows")
    print("sas/expected/provisions.csv and vba/expected/result.csv written")


if __name__ == "__main__":
    main()
