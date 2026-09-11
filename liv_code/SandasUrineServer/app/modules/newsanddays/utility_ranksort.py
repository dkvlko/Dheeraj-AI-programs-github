import json
from pathlib import Path


JSON_FILE = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/"
    "liv_code/SandasUrineServer/app/modules/newsanddays/"
    "data_up1/rankednews_working.json"
)


# ---------------------------------------------------------
# Read JSON
# ---------------------------------------------------------

with JSON_FILE.open(
    "r",
    encoding="utf-8"
) as f:

    data = json.load(f)


# ---------------------------------------------------------
# Sort by Rank Position
# ---------------------------------------------------------

data.sort(
    key=lambda article: int(
        article.get("Rank Position", 999999)
    )
)


# ---------------------------------------------------------
# Write sorted JSON back to same file
# ---------------------------------------------------------

with JSON_FILE.open(
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        data,
        f,
        ensure_ascii=False,
        indent=4
    )


print(
    f"JSON sorted by Rank Position: {JSON_FILE}"
)
