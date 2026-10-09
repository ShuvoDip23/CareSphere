"""Demo seed data for local development and the weekly demo.

These doctor records are PLACEHOLDERS. The names, facilities and phone numbers
are invented so that no real practitioner is misrepresented. Replace them with
verified directory data before any public deployment.

Run with:  flask --app wsgi seed
"""

from datetime import date

from .extensions import db
from .models.doctor import Doctor, DoctorAvailability, Specialty
from .models.donor import BloodDonor

SPECIALTIES = [
    ("Cardiologist", "Heart, blood pressure and circulation."),
    ("Dermatologist", "Skin, hair and nail conditions."),
    ("ENT Specialist", "Ear, nose, throat, sinus and hearing."),
    ("Neurologist", "Brain, spine and nervous system."),
    ("Orthopedic", "Bones, joints, muscles and injuries."),
    ("General Physician", "First point of contact for common illness."),
]

# (name, specialty, qualification, hospital, area, phone, fee, rating, reviews, years)
DOCTORS = [
    (
        "Dr. Anwar Hossain",
        "Cardiologist",
        "MBBS, MD (Cardiology)",
        "Padma Heart Centre",
        "Laxmipur, Rajshahi",
        "+8801711000101",
        1500,
        4.8,
        132,
        14,
    ),
    (
        "Dr. Nusrat Jahan",
        "Cardiologist",
        "MBBS, D-Card",
        "Barind Specialised Clinic",
        "Shaheb Bazar, Rajshahi",
        "+8801711000102",
        1200,
        4.6,
        88,
        9,
    ),
    (
        "Dr. Tanvir Ahmed",
        "Dermatologist",
        "MBBS, DDV",
        "Rajshahi Skin Care Centre",
        "Upashahar, Rajshahi",
        "+8801711000103",
        1000,
        4.7,
        154,
        11,
    ),
    (
        "Dr. Farhana Islam",
        "Dermatologist",
        "MBBS, MCPS (Dermatology)",
        "Padma General Hospital",
        "Kazla, Rajshahi",
        "+8801711000104",
        900,
        4.4,
        61,
        6,
    ),
    (
        "Prof. Dr. Mahbubur Rahman",
        "ENT Specialist",
        "MBBS, FCPS (ENT)",
        "Barind Specialised Clinic",
        "Talaimari, Rajshahi",
        "+8801711000105",
        1500,
        4.9,
        210,
        22,
    ),
    (
        "Dr. Sabina Yeasmin",
        "ENT Specialist",
        "MBBS, DLO",
        "Rajshahi Central Medical",
        "Greater Road, Rajshahi",
        "+8801711000106",
        1000,
        4.3,
        47,
        7,
    ),
    (
        "Prof. Dr. Kamrul Hasan",
        "Neurologist",
        "MBBS, FCPS (Medicine), MD (Neurology)",
        "Padma General Hospital",
        "Laxmipur, Rajshahi",
        "+8801711000107",
        1800,
        4.9,
        176,
        19,
    ),
    (
        "Dr. Rezaul Karim",
        "Neurologist",
        "MBBS, MD (Neurology)",
        "Rajshahi Central Medical",
        "Binodpur, Rajshahi",
        "+8801711000108",
        1500,
        4.5,
        73,
        10,
    ),
    (
        "Dr. Shahriar Kabir",
        "Orthopedic",
        "MBBS, MS (Orthopedics)",
        "Barind Orthopedic Centre",
        "Vodra, Rajshahi",
        "+8801711000109",
        1300,
        4.6,
        119,
        13,
    ),
    (
        "Dr. Mahmuda Akter",
        "Orthopedic",
        "MBBS, D-Ortho",
        "Padma General Hospital",
        "New Market, Rajshahi",
        "+8801711000110",
        1000,
        4.2,
        38,
        5,
    ),
    (
        "Dr. Imran Chowdhury",
        "General Physician",
        "MBBS, FCPS (Medicine)",
        "Rajshahi Central Medical",
        "Court, Rajshahi",
        "+8801711000111",
        800,
        4.7,
        240,
        12,
    ),
    (
        "Dr. Ayesha Siddika",
        "General Physician",
        "MBBS, CCD",
        "Kazla Family Health Centre",
        "Kazla, Rajshahi",
        "+8801711000112",
        600,
        4.5,
        165,
        8,
    ),
]

BIO = (
    "{name} consults at {hospital} in {area}. Appointments booked through "
    "CareSphere are confirmed once payment is completed."
)

# Monday=0. Two windows per doctor, staggered so the directory looks realistic.
WINDOWS = [
    [(0, "09:00", "13:00"), (2, "09:00", "13:00"), (4, "16:00", "20:00")],
    [(1, "10:00", "14:00"), (3, "10:00", "14:00"), (5, "09:00", "12:00")],
    [(0, "16:00", "20:00"), (2, "16:00", "20:00"), (6, "10:00", "13:00")],
]


# (name, blood_group, area, hospital_near, phone, last_donation_date, donations_count)
DONORS = [
    (
        "Md. Rafiqul Islam",
        "O+",
        "Laxmipur, Rajshahi",
        "Rajshahi Medical College Hospital",
        "+8801712000001",
        date(2026, 5, 14),
        7,
    ),
    (
        "Sabbir Hossain",
        "A+",
        "Kazla, Rajshahi",
        "RUET Medical Centre area",
        "+8801712000002",
        date(2026, 6, 20),
        4,
    ),
    (
        "Tahmid Rahman",
        "B+",
        "Talaimari, Rajshahi",
        "Barind Specialised Clinic",
        "+8801712000003",
        date(2026, 8, 18),
        9,
    ),
    (
        "Kazi Anisur Rahman",
        "O-",
        "Upashahar, Rajshahi",
        "Padma Heart Centre",
        "+8801712000004",
        date(2026, 2, 5),
        5,
    ),
    (
        "Imtiaz Shafi",
        "AB+",
        "Binodpur, Rajshahi",
        "Kazla Family Health",
        "+8801712000005",
        date(2026, 4, 12),
        3,
    ),
    (
        "Nayeem Abdullah",
        "B-",
        "Shaheb Bazar, Rajshahi",
        "Rajshahi Central Medical",
        "+8801712000006",
        date(2026, 9, 1),
        6,
    ),
    (
        "Zubair Al Mamun",
        "A-",
        "Vodra, Rajshahi",
        "Barind Orthopedic Centre",
        "+8801712000007",
        None,
        0,
    ),
    (
        "Asif Mahmud",
        "AB-",
        "Court, Rajshahi",
        "Padma General Hospital",
        "+8801712000008",
        date(2026, 3, 10),
        8,
    ),
]


def seed_demo_data() -> dict:
    """Idempotent. Safe to run repeatedly - existing rows are left alone."""
    created = {"specialties": 0, "doctors": 0, "windows": 0, "donors": 0}

    by_name: dict[str, Specialty] = {}
    for name, description in SPECIALTIES:
        specialty = Specialty.query.filter_by(name=name).first()
        if specialty is None:
            specialty = Specialty.get_or_create(name)
            specialty.description = description
            created["specialties"] += 1
        by_name[name] = specialty
    db.session.flush()

    for index, row in enumerate(DOCTORS):
        (
            name,
            specialty_name,
            qualification,
            hospital,
            area,
            phone,
            fee,
            rating,
            reviews,
            years,
        ) = row
        if Doctor.query.filter_by(name=name, hospital=hospital).first():
            continue

        doctor = Doctor(
            name=name,
            specialty=by_name[specialty_name],
            qualification=qualification,
            hospital=hospital,
            location=area,
            phone=phone,
            fee=fee,
            rating=rating,
            review_count=reviews,
            experience_years=years,
            bio=BIO.format(name=name, hospital=hospital, area=area),
            approval_status=Doctor.STATUS_APPROVED,
        )
        db.session.add(doctor)
        db.session.flush()
        created["doctors"] += 1

        for day, start, end in WINDOWS[index % len(WINDOWS)]:
            db.session.add(
                DoctorAvailability(
                    doctor_id=doctor.id, day_of_week=day, start_time=start, end_time=end
                )
            )
            created["windows"] += 1

    for row in DONORS:
        name, blood_group, area, hospital_near, phone, last_donation_date, donations_count = row
        if BloodDonor.query.filter_by(phone=phone).first():
            continue

        donor = BloodDonor(
            name=name,
            blood_group=blood_group,
            area=area,
            hospital_near=hospital_near,
            phone=phone,
            last_donation_date=last_donation_date,
            donations_count=donations_count,
            is_available=True,
        )
        db.session.add(donor)
        created["donors"] += 1

    db.session.commit()
    return created
