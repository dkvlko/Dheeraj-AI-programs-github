
Yes. For your database, **Rama Navami is considerably simpler than Holika Dahan** because the central rule is based on **Chaitra Shukla Navami prevailing during Madhyahna**. The key is to calculate *Madhyahna from your local sunrise/sunset*, rather than treating 12:00 PM as noon. This agrees with the Panchang convention used by Drik Panchang. ([Drik Panchang][1])

## 1. Rule we should implement

The primary rule should be:

> **Rama Navami = the civil Hindu day on which Chaitra Shukla Navami prevails during Madhyahna.**

Rama Navami is specifically associated with Lord Rama's birth during Madhyahna, so **Madhyahna-vyapini Navami** is the important criterion. ([Drik Panchang][1])

In your calendar:

```text
Chaitra        = Masa 01
Shukla Navami  = Tithi 09 + Paksha Shukla
```

Therefore we should use your `Hindu_Calendar` table to locate candidate dates, and your astronomical transition tables to determine the exact Navami interval.

---

# 2. Tables we already have

We can do this almost entirely from your existing database.

### `Hindu_Calendar`

Use it to identify:

```text
Masa = '01'
Tithi = '09'
Paksha = 'Shukla'
Adhika_Masa = 0
```

The important point is that **we should not simply search for the row where Tithi = 09 and declare that date Rama Navami**.

That row tells us the tithi prevailing at sunrise. Rama Navami needs the additional **Madhyahna** condition.

---

### `Sun_Position`

You already have:

```text
Date
Sunrise_Time
Sunset_Time
```

This gives us the local sunrise and sunset needed to calculate Hindu Madhyahna.

---

### `Sun_Moon_Position`

This can be used to determine the exact astronomical tithi boundaries if needed.

But since you already have your transition tables, I would prefer to create a dedicated:

```text
Tithi_Transition
```

table eventually.

Your existing `Karana_Transition` and `Amavasya_Purnima_Transition` demonstrate exactly why this is useful: festival programs become simple database queries instead of repeatedly performing astronomical calculations.

---

# 3. Calculate Madhyahna

Your Madhyahna should **not** be:

```text
12:00:00
```

Instead, use the Hindu day defined by:

```text
Sunrise → Sunset
```

and divide it into five equal parts:

```text
Sunrise
   │
   ├── Pratah
   │
   ├── Sangava
   │
   ├── Madhyahna
   │
   ├── Aparahna
   │
   └── Sayahna
Sunset
```

Thus:

```python
day_duration = sunset - sunrise

madhyahna_start = sunrise + 2 * day_duration / 5
madhyahna_end   = sunrise + 3 * day_duration / 5
```

And the **Madhyahna moment** is:

```python
madhyahna_moment = (
    madhyahna_start + madhyahna_end
) / 2
```

This produces a location-specific Madhyahna rather than assuming 12 PM. Drik explicitly notes this distinction because sunrise and sunset generally aren't exactly 06:00 and 18:00. ([Drik Panchang][1])

---

# 4. What does "Navami prevails during Madhyahna" mean?

This is the crucial database test.

Suppose:

```text
Navami:
10:30 → next day 09:15

Madhyahna:
11:45 → 14:10
```

There is overlap:

```text
Navami
10:30 ───────────────────── 09:15 next day
           │
           ├──── Madhyahna ────┤
           │
```

Therefore:

```text
Rama Navami = that civil day
```

Mathematically:

```sql
Navami_Start < Madhyahna_End
AND
Navami_End > Madhyahna_Start
```

That is the same interval-intersection philosophy we've already used successfully for your Purnima/Pradosh calculations.

---

# 5. But there is an important special case

Suppose Navami exists on **two consecutive Hindu civil days** and Madhyahna overlaps Navami on both.

The traditional rule is:

> **If Madhyahna-vyapini Navami occurs on both days, take the first day.**

This is explicitly reflected in traditional Panchang rules cited in the Drik-based example. ([Astro Tantra Gurukul][2])

So algorithmically:

```text
Find all Chaitra Shukla Navami candidate dates
             ↓
Calculate Madhyahna for each date
             ↓
Find dates where Navami ∩ Madhyahna exists
             ↓
If one date → select it
If two dates → select the earlier date
```

That gives us a robust rule instead of relying on sunrise Tithi alone.

---

# 6. Why `Hindu_Calendar` alone is insufficient

Consider this situation:

```text
Mar 26 sunrise       = Ashtami
Mar 26 11:48         = Navami begins
Mar 26 Madhyahna     = 11:10–13:37
Mar 27 10:06         = Navami ends
```

Even though:

```text
Mar 26 sunrise = Ashtami
```

Rama Navami is still **Mar 26**, because Navami prevails during Madhyahna. This is exactly the type of case seen in the 2026 calculations. ([Drik Panchang][1])

So don't implement:

```sql
WHERE Tithi = '09'
AND Paksha = 'Shukla'
```

and stop there.

That would fail on a Viddha/late-start Navami.

---

# 7. How I would structure it in your database

I'd use this hierarchy:

```text
Hindu_Calendar
      │
      │ identify Chaitra
      ▼
Chaitra Shukla Navami candidate dates
      │
      │ exact tithi boundaries
      ▼
Tithi_Transition
      │
      │ intersect with
      ▼
Madhyahna calculated from Sun_Position
      │
      ▼
Rama Navami date
```

I recommend creating:

```sql
CREATE TABLE Tithi_Transition (
    Start_Date_Time_UTC TEXT NOT NULL,
    End_Date_Time_UTC TEXT NOT NULL,

    Start_Date_Time_Local TEXT NOT NULL,
    End_Date_Time_Local TEXT NOT NULL,

    Location TEXT NOT NULL,

    Latitude REAL NOT NULL,
    Longitude REAL NOT NULL,

    Angular_Separation_Start REAL NOT NULL,
    Angular_Separation_End REAL NOT NULL,

    Tithi TEXT NOT NULL,
    Paksha TEXT NOT NULL,

    PRIMARY KEY (
        Start_Date_Time_UTC,
        Location
    )
);
```

That would make your festival programs much cleaner.

---

# 8. The complete Rama Navami algorithm

For each Gregorian year:

### Step 1 — Find Chaitra

Query:

```sql
WHERE Masa = '01'
AND Adhika_Masa = 0
```

because your Amanta system uses:

```text
01 = Chaitra
```

---

### Step 2 — Find Shukla Navami

Identify the astronomical interval where:

```text
Tithi = 09
Paksha = Shukla
```

from `Tithi_Transition`.

This gives something like:

```text
2027-04-14 15:23
        ↓
2027-04-15 13:20
```

The exact 2027 example is consistent with published Panchang data. ([Drik Panchang][3])

---

### Step 3 — Check the candidate civil dates

Check:

```text
Navami start date
Navami end date
```

and therefore potentially:

```text
Navami start date
Navami start date + 1
```

just as we learned from the Holika calculation.

---

### Step 4 — Calculate Madhyahna for each date

From `Sun_Position`:

```python
day_length = sunset - sunrise

madhyahna_start = sunrise + 2 * day_length / 5
madhyahna_end   = sunrise + 3 * day_length / 5
```

---

### Step 5 — Test overlap

For each candidate date:

```python
if (
    navami_start < madhyahna_end
    and
    navami_end > madhyahna_start
):
    candidate = date
```

---

### Step 6 — Resolve two-day Madhyahna overlap

If both dates satisfy the condition:

```text
take the earlier date
```

---

### Step 7 — Store the result

I'd eventually create:

```sql
Rama_Navami
```

with at least:

```text
Date
Rama_Navami_Date_Time_Start_UTC
Rama_Navami_Date_Time_End_UTC

Rama_Navami_Date_Time_Start_Local
Rama_Navami_Date_Time_End_Local

Location
Latitude
Longitude

Masa_Number
Masa_English
Masa_Hindi

Tithi
Paksha

Sunrise_Local
Sunset_Local

Madhyahna_Start_Local
Madhyahna_End_Local
Madhyahna_Moment_Local
```

That gives you both the **festival date** and the astronomical evidence used to select it.

---

## 9. One more useful refinement: Puja window

For a Panchang-like system, I'd also calculate:

```text
Rama Navami Puja Window
    =
Navami ∩ Madhyahna
```

So if:

```text
Navami:
15:23 Apr 14 → 13:20 Apr 15

Madhyahna Apr 15:
10:58 → 13:27
```

then:

```text
Navami ∩ Madhyahna
=
10:58 → 13:20
```

This is very close to the published 2027 Panchang presentation, which gives Navami ending at 13:20 and Madhyahna around 10:58–13:27 at Tirumala. ([Drik Panchang][3])

And the **Madhyahna moment** is simply the midpoint of that Madhyahna interval, not necessarily the midpoint of the Navami∩Madhyahna intersection.

---

### In short

For your database, the rule should be:

```text
Chaitra
  ↓
Shukla Paksha
  ↓
Navami
  ↓
Find exact Navami interval
  ↓
For each relevant civil date:
    calculate Madhyahna from Sunrise/Sunset
  ↓
Navami ∩ Madhyahna ?
  ↓
YES → Rama Navami
  ↓
If both consecutive days qualify:
    choose earlier day
```

This is a good fit for the architecture you've been building: **astronomical transition tables first, festival-specific decision logic second**. It avoids hard-coding Gregorian dates and handles late-start/early-ending Navami correctly. ([Drik Panchang][1])

[1]: https://www.drikpanchang.com/dashavatara/rama-navami/rama-navami-date-time.html?geoname-id=1270965&year=2026&utm_source=chatgpt.com "2026 Rama Navami Vrat, Puja Date and Time for Gopalganj, Bihar, India"
[2]: https://astro.tantragurukul.org/examples?api=ramnavami&engine=drik&utm_source=chatgpt.com "Examples · Ram Navami · Drik"
[3]: https://www.drikpanchang.com/dashavatara/rama-navami/rama-navami-date-time.html?geoname-id=1254373&utm_source=chatgpt.com "2027 Rama Navami Vrat, Puja Date and Time for Tirumala, Andhra Pradesh, India"
