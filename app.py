import os
import json
import razorpay
import swisseph as swe
import pytz

from datetime import datetime
from flask import Flask, render_template, request, session

app = Flask(__name__)
app.secret_key = "vedic_secret_key_intl_456"

# Razorpay keys
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Swiss ephemeris settings
swe.set_sid_mode(swe.SIDM_LAHIRI)
swe.set_ephe_path(".")

# Nakshatra list
nakshatras = [
"Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra",
"Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni",
"Uttara Phalguni","Hasta","Chitra","Swati","Vishakha",
"Anuradha","Jyeshtha","Mula","Purva Ashada","Uttara Ashada",
"Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada",
"Uttara Bhadrapada","Revati"
]

# Rasi list
rasi_list = [
"Mesha","Vrishabha","Mithuna","Karka","Simha","Kanya",
"Tula","Vrischika","Dhanu","Makara","Kumbha","Meena"
]

# Vimshottari dasha order
dasha_sequence = [
"Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"
]

dasha_years = {
"Ketu":7,
"Venus":20,
"Sun":6,
"Moon":10,
"Mars":7,
"Rahu":18,
"Jupiter":16,
"Saturn":19,
"Mercury":17
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/details")
def details():

    try:
        with open("world_cities.json") as f:
            world_cities = json.load(f)
    except:
        world_cities = {}

    countries = sorted(world_cities.keys())

    return render_template(
        "details.html",
        world_cities=world_cities,
        countries=countries
    )


@app.route("/payment", methods=["POST"])
def payment():

    session["name"] = request.form.get("name")
    session["day"] = request.form.get("day")
    session["month"] = request.form.get("month")
    session["year"] = request.form.get("year")
    session["tob"] = request.form.get("tob")
    session["country"] = request.form.get("country")
    session["place"] = request.form.get("place")
    session["report_type"] = request.form.get("report_type")

    report_type = request.form.get("report_type")

    if report_type == "detailed":
        amount = 10000
        display = "$100"
    else:
        amount = 1000
        display = "$10"

    order = client.order.create({
        "amount": amount,
        "currency": "USD",
        "payment_capture": 1
    })

    return render_template(
        "payment.html",
        order_id=order["id"],
        key_id=RAZORPAY_KEY_ID,
        amount=amount,
        display=display
    )


@app.route("/result", methods=["POST"])
def result():

    if not request.form.get("razorpay_payment_id"):
        return "Payment required", 403

    name = session.get("name")
    day = int(session.get("day"))
    month = int(session.get("month"))
    year = int(session.get("year"))
    tob = session.get("tob")
    country = session.get("country")
    place = session.get("place")
    report_type = session.get("report_type")

    hour, minute = map(int, tob.split(":"))

    with open("world_cities.json") as f:
        world_cities = json.load(f)

    city_data = world_cities.get(country, {}).get(place, {})

    lat = city_data.get("lat", 0.0)
    lon = city_data.get("lon", 0.0)
    timezone_str = city_data.get("timezone", "UTC")

    dt = datetime(year, month, day, hour, minute)

    tz = pytz.timezone(timezone_str)
    dt_local = tz.localize(dt)
    dt_utc = dt_local.astimezone(pytz.utc)

    jd = swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        dt_utc.hour + dt_utc.minute / 60.0
    )

    moon = swe.calc_ut(
        jd,
        swe.MOON,
        swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    )[0][0] % 360

    saturn = swe.calc_ut(
        jd,
        swe.SATURN,
        swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    )[0][0] % 360

    nak_span = 360 / 27
    nak_index = int(moon / nak_span)

    degrees_into_nak = moon % nak_span

    pada = int(degrees_into_nak / (nak_span / 4)) + 1

    rasi_index = int(moon / 30)

    houses = swe.houses_ex(
        jd,
        lat,
        lon,
        b'P',
        swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    )

    asc = houses[0][0] % 360
    lagna = rasi_list[int(asc / 30)]

    moon_sign_num = int(moon / 30) + 1
    saturn_sign_num = int(saturn / 30) + 1

    house_from_moon = (saturn_sign_num - moon_sign_num) % 12 + 1

    shani_status = "No Gochara Saturn Dosha, but verify Mahadasa also"

    if house_from_moon == 8:
        shani_status = "Ashtama Shani (Saturn in 8th from Moon)"
    elif house_from_moon == 4:
        shani_status = "Kantaka Shani (Saturn in 4th from Moon)"
    elif house_from_moon == 1:
        shani_status = "Janma Shani (Saturn in Moon sign)"
    elif house_from_moon == 12:
        shani_status = "Sade Sati Phase 1 (12th from Moon)"
    elif house_from_moon == 2:
        shani_status = "Sade Sati Phase 3 (2nd from Moon)"

    birth_md_index = nak_index % 9
    birth_md = dasha_sequence[birth_md_index]

    balance_years = (1 - (degrees_into_nak / nak_span)) * dasha_years[birth_md]

    age_years = (datetime.now() - dt).days / 365.25

    if age_years < balance_years:
        running_md = birth_md
    else:
        temp = age_years - balance_years
        idx = (birth_md_index + 1) % 9

        while temp >= dasha_years[dasha_sequence[idx]]:
            temp -= dasha_years[dasha_sequence[idx]]
            idx = (idx + 1) % 9

        running_md = dasha_sequence[idx]

    return render_template(
        "result.html",
        name=name,
        nakshatra=nakshatras[nak_index],
        pada=pada,
        rasi=rasi_list[rasi_index],
        lagna=lagna,
        birth_md=birth_md,
        running_md=running_md,
        shani_status=shani_status,
        report_type=report_type,
        place=place,
        country=country
    )

   @app.route("/ping")
   def ping():
    return "alive"
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
