
import json
from pathlib import Path


# =========================================================
# JSON file
# =========================================================

JSON_FILE = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/"
    "liv_code/SandasUrineServer/app/modules/newsanddays/"
    "data_up1/rankednews_working.json"
)


# =========================================================
# Read JSON
# =========================================================

with JSON_FILE.open(
    "r",
    encoding="utf-8"
) as f:

    data = json.load(f)


# =========================================================
# Sort by existing Rank Position
# =========================================================

data.sort(
    key=lambda article: int(
        article.get("Rank Position", 999999)
    )
)


# =========================================================
# Renumber Rank Position starting from 1
# =========================================================

for rank_position, article in enumerate(
    data,
    start=1
):
    article["Rank Position"] = rank_position


# =========================================================
# Write sorted and renumbered JSON
# =========================================================

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


# =========================================================
# Report
# =========================================================

print()
print(
    f"JSON sorted and Rank Position renumbered: "
    f"{JSON_FILE}"
)
print(
    f"Total news items: {len(data)}"
)
