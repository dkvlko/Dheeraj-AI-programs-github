
Yes. For **Holika Dahan**, we built a somewhat more complicated chain than for Maha Shivratri. Since you want to check the data one by one, I would regard the following as the exact sequence we worked through.

## Holika Dahan — steps we completed

### Step 1 — Calculate Sun/Moon astronomical positions

We started from your Swiss Ephemeris calculations of:

* Sun longitude
* Moon longitude
* Moon–Sun angular separation

stored in `Sun_Moon_Position`.

This is the underlying astronomical data.

---

### Step 2 — Calculate Tithi boundaries

We established:

**1 Tithi = 12° of Moon–Sun angular separation.**

Therefore:

```text
Purnima = 168° → 180°
```

and

```text
Amavasya = 348° → 360°/0°
```

We then created/rebuilt `Amavasya_Purnima_Transition`.

For Holika Dahan, the important interval is:

```text
Phalguna Purnima
168° ───────────────────→ 180°
```

This was an important correction in our work: **180° is the end of Purnima, not its beginning.**

We validated the transition table and found no bad Purnima intervals.

---

### Step 3 — Identify Phalguna Purnima

Your calendar is **Amanta**, so we looked for:

```text
Masa = 12
Adhika_Masa = 0
Phase = Purnima
```

In your numbering:

```text
12 = Phalguna
```

We joined `Amavasya_Purnima_Transition` with `Hindu_Calendar` to establish that the Purnima belongs to regular Phalguna.

For example, 2027:

```text
2027-03-21 18:22:02
        ↓
Purnima begins
        ↓
2027-03-22 16:13:48
        ↓
Purnima ends
```

---

### Step 4 — Calculate Pradosh

We then used your `Daily_Time_Periods` table.

Your definition of Pradosh is:

```text
Pradosh_Start = Sunset
Pradosh_End   = Sunset + 144 minutes
```

So:

```text
Sunset
  │
  ├────────────── 144 minutes ──────────────┤
  │                                         │
Pradosh_Start                           Pradosh_End
```

For example, 2027:

```text
Sunset / Pradosh start = 18:17:29
Pradosh end            = 20:41:29
```

---

### Step 5 — Find where Phalguna Purnima overlaps Pradosh

This is the first actual **Holika candidate**.

We used:

```sql
Purnima_Start < Pradosh_End
AND
Purnima_End > Pradosh_Start
```

Mathematically:

```text
Purnima
       ├─────────────────────────────┤
       │                             │
       │       overlap               │
       │       ├───────────┤         │
       │       │           │         │
───────┼───────┼───────────┼─────────┼────
     Pradosh_Start       Pradosh_End
```

If there is no overlap, that date cannot be Holika Dahan under this rule.

---

### Step 6 — Calculate Bhadra

We established that:

> **Vishti Karana = Bhadra.**

Your `Karana_Transition` table already identifies it with:

```text
Is_Bhadra = 1
```

and therefore we could obtain the **complete Bhadra interval** directly.

For example, 2027:

```text
Bhadra:
2027-03-21 18:22:02
        →
2027-03-22 05:15:30
```

This is important because Bhadra is not a separate astronomical phenomenon—we derive it from the appropriate **Vishti Karana**.

---

### Step 7 — Split Bhadra into Bhadra Puccha and Bhadra Mukha

We then created `Bhadra_Transition`.

It divides a complete Bhadra interval into:

```text
Bhadra
   │
   ├── Bhadra
   ├── Bhadra_Puccha
   ├── Bhadra_Mukha
   └── Bhadra
```

We calculated the Puccha/Mukha positions from the relevant Tithi/Paksha rule.

We also verified the resulting timings against published Panchang timings.

For 2027, for example:

```text
Bhadra Puccha
01:26:47 → 02:32:08

Bhadra Mukha
02:32:08 → 04:21:03
```

External Panchang data likewise puts the 2027 Puccha around 01:26–02:31 and Mukha around 02:31–04:20. ([Drik Panchang][1])

---

### Step 8 — Calculate Hindu midnight

We then needed a special definition of midnight.

We did **not** use 00:00:00.

Instead:

```text
Hindu Midnight =
midpoint between today's sunset
and tomorrow's sunrise
```

So:

```text
Sunset
   │
   │       night
   │──────────────────────────────│
                                  │
                              Next sunrise

                 ↑
          Hindu Midnight
```

This is important because the Holika rule refers to **Hindu midnight**, not ordinary clock midnight. DrikPanchang explicitly makes this distinction. ([Drik Panchang][1])

---

## Step 9 — Examine Bhadra relative to the Holika candidate

This is where our algorithm became conditional.

We had:

```text
Candidate = Purnima ∩ Pradosh
```

Then we compared Bhadra against that candidate.

There are several possible situations.

### Case A — No Bhadra overlap

```text
Pradosh:
       ├───────────────────┤

Bhadra:
   ├──────┤
```

Then:

```text
Holika Dahan = complete candidate
```

This is the simplest case.

---

### Case B — Bhadra ends during Pradosh/candidate

Example:

```text
Candidate:
├───────────────────────────┤

Bhadra:
├──────────────┤
               ↑
          Bhadra ends
```

Then we selected:

```text
Bhadra_End → Candidate_End
```

So the ritual begins as soon as Bhadra ends.

This produced, for example, the very narrow 2028 interval we saw.

---

### Case C — Bhadra completely covers the candidate

Example:

```text
Candidate:
       ├───────────────────┤
       │                   │
Bhadra:
├───────────────────────────────────────┤
```

Now there is no ordinary Bhadra-free portion of Pradosh.

This is where we introduced **Bhadra Puccha**.

Our chosen logic was:

```text
Search Bhadra_Puccha
        ↓
Does Puccha overlap candidate?
        ↓
YES → use that overlap
```

We deliberately **do not use Bhadra Mukha**.

That differs slightly from merely saying "avoid Bhadra": the traditional rule gives Puccha a special fallback role when Bhadra extends beyond midnight. Published Panchang rules describe Puccha as the preferred portion in that situation and explicitly exclude Mukha. ([Drik Panchang][1])

---

### Case D — Bhadra covers candidate but Puccha is unavailable

Our custom rule then became:

```text
No usable Puccha
        ↓
"No proper timing"
        ↓
use the complete
Purnima + Pradosh candidate
```

This was an explicit decision we made for your database rather than silently inventing another interval.

---

## Step 10 — Determine the final Holika Dahan interval

So our decision tree became approximately:

```text
Phalguna Purnima
       ↓
Does it overlap Pradosh?
       │
       ├── NO → no Holika candidate
       │
       └── YES
             ↓
        Check Bhadra
             │
     ┌───────┼───────────────┐
     │       │               │
   None   Ends during    Covers candidate
     │       candidate          │
     │          │               │
     ↓          ↓               ↓
 candidate   after Bhadra   Search Puccha
                             │
                     ┌───────┴───────┐
                     │               │
                   found          not found
                     │               │
                     ↓               ↓
                Puccha overlap    whole candidate
```

---

## Step 11 — Determine Holi date

Once Holika Dahan is determined, we assigned:

```text
Holi_Date = next civil day
```

So, for example:

```text
Holika Dahan
21 March 2027 evening
        ↓
Holi
22 March 2027
```

Published 2027 Panchang data also gives Holika Dahan on March 21 and Rangwali Holi on March 22. ([Drik Panchang][1])

---

## Step 12 — Store everything in `Holika_Holi`

Finally we created the `Holika_Holi` table containing not merely the answer but the intermediate information needed to audit it:

* Holika Dahan date
* UTC start/end
* Local start/end
* Holi date
* Location
* latitude/longitude
* Masa
* Tithi
* Paksha
* Purnima start/end
* Sunset
* Pradosh start/end
* Bhadra start/end
* later, your `Descrption` column

The important distinction is that **the final date is derived from the astronomical transitions and time-period tables**, rather than being hard-coded.

---

# The whole Holika calculation in one chain

```text
Sun + Moon longitude
        ↓
Moon-Sun angular separation
        ↓
12° Tithi boundaries
        ↓
168° → 180°
        ↓
Purnima
        ↓
Identify Masa = 12 (Phalguna)
        ↓
Calculate local sunset
        ↓
Pradosh = sunset → sunset + 144 min
        ↓
Purnima ∩ Pradosh
        ↓
Holika candidate
        ↓
Check Vishti Karana
        ↓
Bhadra
        ↓
Check Bhadra relative to candidate
        ↓
 ┌────────────────────────────────┐
 │ No Bhadra → candidate          │
 │ Bhadra ends → after Bhadra     │
 │ Bhadra covers → search Puccha  │
 │ no Puccha → candidate fallback │
 └────────────────────────────────┘
        ↓
Holika Dahan interval
        ↓
Next civil day
        ↓
Holi date
```

### One important audit point

There are **two separate questions** that we should keep apart:

1. **Astronomical calculation:**
   Is our Purnima, Pradosh, Karana/Bhadra and Puccha data correct?

2. **Festival-selection convention:**
   Given those intervals, did we choose the correct Holika Dahan date/time?

We have already found that these can diverge. **2026 is the clearest example:** your astronomical Purnima begins on March 2 at about 17:56, while published Panchang calendars assign Holika Dahan to March 3 evening. Drik explicitly describes the 2026 observance as March 3, with Purnima beginning March 2 and ending March 3. ([Drik Panchang][2])

So if we're auditing your database **one item at a time**, I would next check **Step 3: whether our identification of Phalguna Purnima is correct for each year**. Only after that should we examine the Holika-specific selection rule.

[1]: https://www.drikpanchang.com/festivals/holi/festivals-holika-dahan-timings.html?geoname-id=1260909&utm_source=chatgpt.com "2027 Holika Dahan, Holi Puja Timings for Padrauna, Uttar Pradesh, India"
[2]: https://www.drikpanchang.com/festivals/holi/festivals-holika-dahan-timings.html?geoname-id=1269843&year=2026&utm_source=chatgpt.com "2026 Holika Dahan, Holi Puja Timings for Hyderabad, Telangana, India"
