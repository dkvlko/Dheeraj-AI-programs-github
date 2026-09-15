Maha Shivratri Rules 
Maha-Shivratri
==================
Query a year :
SELECT *
FROM Maha_Shivratri
WHERE Date >= '2029-01-01'
  AND Date <  '2030-01-01';


Yes. Since you want to **audit the database one step at a time**, I would separate the calculation into the astronomical data generation and the festival-selection rule.

For **Maha Shivratri**, the chain we established is essentially:

### Step 1 — Calculate Sun and Moon positions

Using Swiss Ephemeris, we generated periodic records containing:

* Sun longitude
* Moon longitude
* Moon–Sun angular separation

This is the fundamental astronomical data.

Your `Sun_Moon_Position` table contains these observations.

---

### Step 2 — Calculate Tithi from angular separation

The fundamental rule is:

**1 Tithi = 12° of Moon–Sun angular separation.**

Therefore:

| Tithi               | Angular separation |
| ------------------- | -----------------: |
| Shukla Pratipada    |             0°–12° |
| Shukla Dwitiya      |            12°–24° |
| ...                 |                ... |
| Shukla Purnima      |          168°–180° |
| Krishna Pratipada   |          180°–192° |
| ...                 |                ... |
| Krishna Chaturdashi |      **348°–360°** |

So the astronomical definition relevant to Maha Shivratri is:

> **Krishna Chaturdashi = 348° ≤ Moon-Sun separation < 360°.**

This is the first thing I would verify in your database.

---

### Step 3 — Find the exact beginning and ending of Chaturdashi

The 3-hour `Sun_Moon_Position` samples are **not themselves sufficiently precise** for festival boundaries.

We used the samples to find a bracket in which the angular separation crossed a 12° boundary, and then used Swiss Ephemeris/root finding to obtain the exact transition.

Conceptually:

```text
342° ───────── 348° ───────────────── 360°/0°
               ↑                       ↑
          Chaturdashi starts       Chaturdashi ends
```

Thus we need an exact interval:

```text
Chaturdashi_Start
        ↓
348°
        │
        │  Krishna Chaturdashi
        │
360°/0°
        ↓
Chaturdashi_End
```

This is the most important astronomical transition for Shivratri.

---

### Step 4 — Determine the lunar month

Then we determine which Hindu lunar month contains that Krishna Chaturdashi.

For your **Amanta** calendar, the relevant month is:

**Magha**.

This is an important point because Maha Shivratri is described differently by Amanta and Purnimanta calendars.

DrikPanchang explicitly notes that the same observance is called **Magha Krishna Chaturdashi in the Amanta system** and **Phalguna Krishna Chaturdashi in the North Indian Purnimanta system**. ([Drik Panchang][1])

So for your database:

```text
Calendar_System = Amanta
Masa = Magha
Paksha = Krishna
Tithi = Chaturdashi
```

---

### Step 5 — Do NOT simply select the civil day on which Chaturdashi occurs

This is where Maha Shivratri differs from a simple "find Tithi 14" query.

The determining period is **Nishita Kaal**, approximately the middle of the night.

The festival is assigned to the civil date whose night has **Krishna Chaturdashi prevailing at Nishita**. This is why, for example, Maha Shivratri 2026 was February 15 even though Chaturdashi continued until February 16 evening. ([India Today][2])

So the logical test is:

```text
Candidate date
       ↓
Sunset
       ↓
Night
       ↓
Nishita Kaal
       ↓
Is Moon-Sun separation 348°–360°?
       ↓
YES → Maha Shivratri
```

---

### Step 6 — Calculate Hindu midnight/Nishita from sunrise and sunset

We already created `Daily_Time_Periods` and the concept of Hindu midnight.

For a given civil date:

```text
Sunset(date)
        |
        |--------- night ---------|
        |                         |
   sunset                    sunrise(next day)
                 ↑
          Hindu midnight
```

Your Hindu midnight was defined as:

```python
hindu_midnight = sunset_today + (
    sunrise_next_day - sunset_today
) / 2
```

For the traditional **Nishita** calculation, however, we should be careful: Nishita is not necessarily identical to the simple midpoint of sunset and sunrise in every formulation. Traditional Panchanga calculations divide the night into 15 muhurtas and take the 8th as Nishita. Some modern Panchangas provide a Nishita interval around the middle of the night. ([Life Kundali][3])

So **this is one point I recommend we audit before treating our Maha Shivratri algorithm as final.**

---

### Step 7 — Evaluate the Tithi at Nishita

At the calculated Nishita moment, determine:

```text
Moon longitude
Sun longitude
        ↓
Moon − Sun
        ↓
normalize to 0°–360°
        ↓
348° ≤ separation < 360° ?
```

If yes:

```text
Maha Shivratri = that civil date
```

If no:

```text
not Maha Shivratri
```

This is the core festival-selection rule.

---

### Step 8 — Use your `Hindu_Calendar` as a cross-check, not necessarily as the primary calculation

Your `Hindu_Calendar` gives a daily designation such as:

```text
Tithi = 14
Paksha = Krishna
Masa = ...
```

But **the sunrise Tithi alone is insufficient for Maha Shivratri**.

For example, in 2026:

* Chaturdashi began around **17:04 on Feb 15**
* Chaturdashi ended around **17:34 on Feb 16**
* Nishita occurred during the night beginning Feb 15

Therefore Feb 15 is Maha Shivratri even though the sunrise Tithi on Feb 15 was still Trayodashi. ([Drik Panchang][1])

That is precisely why we shouldn't write something like:

```sql
WHERE Tithi = '14'
  AND Paksha = 'Krishna'
```

and assume that row's Gregorian date is automatically Shivratri.

---

## So the complete chain is

```text
Swiss Ephemeris
      ↓
Sun/Moon longitude
      ↓
Moon-Sun angular separation
      ↓
12° Tithi boundaries
      ↓
Exact Krishna Chaturdashi interval
      ↓
Determine lunar month
      ↓
Magha (Amanta)
      ↓
For each possible civil date:
      ↓
Calculate night / Nishita
      ↓
Evaluate Moon-Sun separation at Nishita
      ↓
Is it 348°–360°?
      ↓
YES
      ↓
MAHA SHIVRATRI DATE
```

### The database tables involved

In terms of your existing database, I would audit them in this order:

1. **`Sun_Moon_Position`**
   Are Sun/Moon longitudes correct?

2. **Tithi calculation / boundaries**
   Are the 12° boundaries being calculated correctly?

3. **`Hindu_Calendar`**
   Does it correctly label the resulting Tithi/Paksha/Masa?

4. **`Sun_Position`**
   Are sunrise/sunset values correct?

5. **Night/Nishita calculation**
   Is the selected Nishita period correct?

6. **Maha Shivratri selection rule**
   Does Krishna Chaturdashi actually prevail at Nishita?

7. **Final festival table**
   Only after 1–6 are verified should we store the Maha Shivratri date.

**I suggest we now audit Step 1 only:** take one known year, say **2027**, and verify your `Sun_Moon_Position` data around the expected Maha Shivratri date. Once that is correct, we move to Step 2. This will prevent errors in later festival logic from being hidden by the database.

[1]: https://www.drikpanchang.com/festivals/maha-shivaratri/maha-shivaratri-date-time.html?geoname-id=7279746&year=2026&utm_source=chatgpt.com "2026 Maha Shivaratri | Shivratri Date and Time for Noida, Uttar Pradesh, India"
[2]: https://www.indiatoday.in/information/story/when-is-maha-shivratri-2026-february-15-or-february-16-2865833-2026-02-10?utm_source=chatgpt.com "When is Maha Shivratri 2026: February 15 or February 16? - India Today"
[3]: https://lifekundali.com/pujas/maha-shivaratri.html?utm_source=chatgpt.com "Mahā Śivarātri — the niśītha rule · Darshan"

