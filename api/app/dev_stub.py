SAS_PYTHON = '''import pandas as pd

loans = pd.read_csv("input.csv")

provisions = loans.copy()
provisions["rate"] = (
    provisions["pd"] * provisions["lgd"]
).round(4)
provisions["prov"] = (
    provisions["exposure"] * provisions["rate"]
)

total = provisions["prov"].sum()
'''

VBA_PYTHON = '''import pandas as pd

df = pd.read_csv("input.csv")
df["rate"] = df["pd"] * df["lgd"]
df["prov"] = df["exposure"] * df["rate"]
total = df["prov"].sum()
avg = df["prov"].mean()
result = df
'''

ROUND_HELPER = [
    "def round_half_up(s, n):",
    "    q = 10 ** n",
    "    return np.sign(s) * np.floor(np.abs(s) * q + 0.5 + 1e-9) / q",
]


def statements(lang, source):
    if lang == "sas":
        return max(source.count(";"), 1)
    return max(len([line for line in source.splitlines() if line.strip()]), 1)


def draft(lang):
    return SAS_PYTHON if lang == "sas" else VBA_PYTHON


def find_line(lines, predicate):
    for number, line in enumerate(lines, start=1):
        if predicate(line):
            return number
    return None


def risky_source(lang, source):
    lines = source.splitlines()
    if lang == "sas":
        number = find_line(lines, lambda line: "round(" in line.lower())
        if number is None:
            return []
        return [
            {
                "line": number,
                "tag": "rounding",
                "reason": "SAS rounds a tie away from zero, and pandas rounds a tie to the nearest even digit.",
            }
        ]
    number = find_line(lines, lambda line: line.replace(" ", "").startswith("Cells(i,5)="))
    if number is None:
        return []
    return [
        {
            "line": number,
            "tag": "missing values",
            "reason": "VBA counts a blank cell as zero, and pandas skips it.",
        }
    ]


def flag_python(lang, python):
    lines = python.splitlines()
    if lang == "sas":
        number = find_line(lines, lambda line: line.strip() == ").round(4)")
        if number is None:
            return []
        return [
            {
                "line": number,
                "tag": "rounding",
                "reason": "pandas rounds a tie to the nearest even digit, and SAS rounds it away from zero.",
            }
        ]
    number = find_line(lines, lambda line: line.startswith('df["prov"] =') and "fillna" not in line)
    if number is None:
        return []
    return [
        {
            "line": number,
            "tag": "missing values",
            "reason": "pandas skips a blank cell, and VBA counts it as zero.",
        }
    ]


def rule_patch(lang, python):
    lines = python.splitlines()
    if lang == "sas":
        round_line = find_line(lines, lambda line: line.strip() == ").round(4)")
        import_line = find_line(lines, lambda line: line.strip() == "import pandas as pd")
        read_line = find_line(lines, lambda line: "pd.read_csv" in line)
        if None in (round_line, import_line, read_line):
            return None
        return {
            "summary": "Round half up, the way SAS does.",
            "hunks": [
                {"start": import_line, "remove": [], "add": ["import numpy as np"]},
                {"start": read_line, "remove": [], "add": [""] + ROUND_HELPER + [""]},
                {
                    "start": round_line,
                    "remove": [").round(4)"],
                    "add": [").pipe(round_half_up, 4)"],
                },
            ],
        }
    target = 'df["prov"] = df["exposure"] * df["rate"]'
    number = find_line(lines, lambda line: line.rstrip() == target)
    if number is None:
        return None
    return {
        "summary": "Treat blank cells as zero, the way VBA does.",
        "hunks": [
            {
                "start": number,
                "remove": [target],
                "add": ['df["prov"] = df["exposure"].fillna(0) * df["rate"]'],
            }
        ],
    }
